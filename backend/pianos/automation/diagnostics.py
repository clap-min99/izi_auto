"""Bounded, best-effort diagnostics. Never accesses Selenium or reservation data."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from datetime import datetime
from urllib.request import build_opener, ProxyHandler
from urllib.parse import urlparse

from .log_tee import get_log_dir

_active = None
INTERVAL = 900
KEEP_DAYS = 30
MAX_BYTES = 50 * 1024 * 1024


def event(name, **values):
    if _active is not None:
        _active.event(name, **values)


class Diagnostics:
    def __init__(self, directory=None):
        self.directory = Path(directory or get_log_dir()) / 'diagnostics'
        self.events = queue.Queue(maxsize=256)
        self.stopping = threading.Event()
        self.previous = {}
        self.thread = threading.Thread(target=self._run, name='izi-diagnostics', daemon=True)

    def start(self):
        global _active
        _active = self
        self.event('monitor_started')
        self.thread.start()

    def event(self, name, **values):
        try:
            self.events.put_nowait(dict(timestamp=datetime.now().astimezone().isoformat(),
                                        pid=os.getpid(), event=name, **values))
        except queue.Full:
            pass

    def stop(self):
        global _active
        self.stopping.set()
        self.thread.join(timeout=26)
        _active = None

    def _write(self, record):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            files = sorted(self.directory.glob('diagnostics_*.jsonl'), key=lambda p: p.stat().st_mtime)
            now = time.time()
            for path in list(files):
                if now - path.stat().st_mtime > KEEP_DAYS * 86400:
                    path.unlink()
                    files.remove(path)
            line = json.dumps(record, ensure_ascii=False) + '\n'
            size = len(line.encode('utf-8'))
            if size > MAX_BYTES:
                return
            total = sum(p.stat().st_size for p in files)
            # Delete only this collector's files, including today's if the cap is reached.
            while files and total + size > MAX_BYTES:
                path = files.pop(0)
                total -= path.stat().st_size
                path.unlink()
            with (self.directory / f'diagnostics_{datetime.now():%Y-%m-%d}.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(line)
        except Exception:
            pass

    def _snapshot(self):
        # Command lines, paths, URLs and window titles are deliberately never queried.
        script = r'''
$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem -OperationTimeoutSec 5
$cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'" -OperationTimeoutSec 5
$items = @(Get-Process -Name chrome,chromedriver,python,pythonw,electron -ErrorAction SilentlyContinue | ForEach-Object {
    $seconds = $null
    $started = $null
    try { $seconds = $_.CPU; $started = $_.StartTime.ToUniversalTime().Ticks } catch {}
    [pscustomobject]@{name=$_.ProcessName; pid=$_.Id; memory_bytes=$_.WorkingSet64; cpu_seconds=$seconds; started=$started}
})
@{memory_total_bytes=[long]$os.TotalVisibleMemorySize*1024; memory_available_bytes=[long]$os.FreePhysicalMemory*1024; cpu_percent=$cpu.PercentProcessorTime; processes=$items} | ConvertTo-Json -Depth 4 -Compress
'''
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, timeout=15,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('system_collection_failed')
        data = json.loads(result.stdout.decode('utf-8-sig'))
        now = time.monotonic()
        previous = self.previous
        self.previous = {}
        for proc in data['processes']:
            key = (proc['pid'], proc['started'])
            seconds = proc.get('cpu_seconds')
            old = previous.get(key)
            proc['cpu_percent'] = (round(max(0, seconds - old[1]) / (now - old[0]) * 100 / (os.cpu_count() or 1), 2)
                                   if old and now > old[0] and seconds is not None and old[1] is not None else None)
            self.previous[key] = (now, seconds)
            proc['scope'] = 'monitor' if proc['pid'] == os.getpid() else 'all_pc_unclassified'
        data['process_counts'] = {name: sum(p['name'] == name for p in data['processes'])
                                  for name in ('chrome', 'chromedriver', 'python', 'pythonw', 'electron')}
        data['memory_used_bytes'] = data['memory_total_bytes'] - data['memory_available_bytes']
        try:
            # Read only target counts from the local debug endpoint; no driver calls.
            with build_opener(ProxyHandler({})).open('http://127.0.0.1:9222/json/list', timeout=2) as response:
                targets = json.load(response)
            data['debug_chrome_page_targets'] = sum(t.get('type') == 'page' for t in targets)
            try:
                data['debug_chrome_windows'] = self._window_count(targets)
            except Exception as exc:
                data['debug_chrome_windows'] = None
                data['window_collection_error'] = type(exc).__name__
        except Exception as exc:
            data['browser_collection_error'] = type(exc).__name__
        self._write(dict(timestamp=datetime.now().astimezone().isoformat(), pid=os.getpid(),
                         event='resource_sample', **data))

    def _window_count(self, targets):
        # CDP only reads window IDs, never navigates or modifies the browser.
        import websocket
        with build_opener(ProxyHandler({})).open('http://127.0.0.1:9222/json/version', timeout=2) as response:
            address = json.load(response)['webSocketDebuggerUrl']
        parsed = urlparse(address)
        if parsed.scheme != 'ws' or parsed.hostname != '127.0.0.1' or parsed.port != 9222:
            raise ValueError('unexpected_debug_endpoint')
        connection = websocket.create_connection(address, timeout=2, suppress_origin=True, http_no_proxy=['127.0.0.1'])
        deadline = time.monotonic() + 2
        try:
            windows = set()
            for index, target in enumerate(t for t in targets if t.get('type') == 'page'):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('window_count_timeout')
                connection.settimeout(remaining)
                connection.send(json.dumps({'id': index + 1, 'method': 'Browser.getWindowForTarget',
                                            'params': {'targetId': target['id']}}))
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('window_count_timeout')
                    connection.settimeout(remaining)
                    reply = json.loads(connection.recv())
                    if reply.get('id') == index + 1:
                        windows.add(reply['result']['windowId'])
                        break
            return len(windows)
        finally:
            connection.close(timeout=0)

    def _run(self):
        next_sample = 0
        while True:
            try:
                while True:
                    self._write(self.events.get_nowait())
            except queue.Empty:
                pass
            if self.stopping.is_set():
                return
            if time.monotonic() >= next_sample:
                try:
                    self._snapshot()
                except Exception as exc:
                    self._write(dict(timestamp=datetime.now().astimezone().isoformat(), pid=os.getpid(),
                                     event='collection_failed', error=type(exc).__name__))
                next_sample = time.monotonic() + INTERVAL
            self.stopping.wait(0.2)
