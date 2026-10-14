import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from pianos.automation.diagnostics import Diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_window_count_deduplicates_tabs_in_same_window(self):
        with tempfile.TemporaryDirectory() as directory:
            collector = Diagnostics(directory)
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b'{"webSocketDebuggerUrl":"ws://127.0.0.1:9222/devtools/browser/test"}'
            socket = MagicMock()
            socket.recv.side_effect = [json.dumps({'id': 1, 'result': {'windowId': 10}}),
                                       json.dumps({'id': 2, 'result': {'windowId': 10}}),
                                       json.dumps({'id': 3, 'result': {'windowId': 20}})]
            with patch('pianos.automation.diagnostics.build_opener') as opener, patch(
                    'websocket.create_connection', return_value=socket):
                opener.return_value.open.return_value = response
                self.assertEqual(collector._window_count([
                    {'id': 'a', 'type': 'page'}, {'id': 'b', 'type': 'page'},
                    {'id': 'c', 'type': 'page'}, {'id': 'd', 'type': 'worker'}]), 2)
            socket.close.assert_called_once()

    def test_resource_sample_does_not_store_browser_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            collector = Diagnostics(directory)
            sample = {'memory_total_bytes': 1000, 'memory_available_bytes': 250,
                      'cpu_percent': 10, 'processes': [
                          {'name': 'python', 'pid': os.getpid(), 'started': 1,
                           'memory_bytes': 100, 'cpu_seconds': 2}]}
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b'[{"type":"page","url":"PRIVATE_URL","title":"PRIVATE_NAME"}]'
            with patch('pianos.automation.diagnostics.subprocess.run', return_value=MagicMock(
                    returncode=0, stdout=json.dumps(sample).encode())), patch(
                    'pianos.automation.diagnostics.build_opener') as opener, patch.object(
                    collector, '_window_count', return_value=1):
                opener.return_value.open.return_value = response
                collector._snapshot()
                sample['processes'][0]['cpu_seconds'] = 3
                collector._snapshot()
            contents = next(collector.directory.glob('*.jsonl')).read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE', contents)
            records = [json.loads(line) for line in contents.splitlines()]
            self.assertEqual(records[0]['memory_used_bytes'], 750)
            self.assertEqual(records[0]['debug_chrome_page_targets'], 1)
            self.assertEqual(records[0]['debug_chrome_windows'], 1)
            self.assertIsNone(records[0]['processes'][0]['cpu_percent'])
            self.assertEqual(records[0]['processes'][0]['scope'], 'monitor')

    def test_timeout_records_failure_and_keeps_lifecycle_events(self):
        with tempfile.TemporaryDirectory() as directory:
            collector = Diagnostics(directory)
            def timeout(*args, **kwargs):
                collector.event('shutdown_requested')
                collector.stopping.set()
                raise subprocess.TimeoutExpired('test', 15)
            with patch('pianos.automation.diagnostics.subprocess.run', side_effect=timeout):
                collector._run()
            contents = next(collector.directory.glob('*.jsonl')).read_text(encoding='utf-8')
            self.assertIn('collection_failed', contents)
            self.assertIn('shutdown_requested', contents)

    def test_retention_and_size_cap_only_remove_diagnostic_files(self):
        with tempfile.TemporaryDirectory() as directory:
            collector = Diagnostics(directory)
            collector.directory.mkdir()
            unrelated = collector.directory / 'keep.txt'
            unrelated.write_text('keep')
            old = collector.directory / 'diagnostics_2000-01-01.jsonl'
            old.write_text('old')
            os.utime(old, (0, 0))
            collector._write({'event': 'first'})
            self.assertFalse(old.exists())
            with patch('pianos.automation.diagnostics.MAX_BYTES', 40):
                for _ in range(10):
                    collector._write({'event': 'bounded'})
            self.assertLessEqual(sum(p.stat().st_size for p in collector.directory.glob('*.jsonl')), 40)
            self.assertTrue(unrelated.exists())

    def test_unwritable_storage_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            collector = Diagnostics(directory)
            collector.directory.write_text('blocked')
            collector._write({'event': 'test'})
