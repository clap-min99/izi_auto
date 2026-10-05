"""
모니터 콘솔 출력을 날짜별 로그 파일에도 저장 (콘솔 출력은 그대로 유지)

- 저장 위치: .env 의 IZI_LOG_DIR (없으면 backend/logs)
  → 구글드라이브/원드라이브 동기화 폴더로 지정하면 원격에서 바로 확인 가능
- 파일명: monitor_YYYY-MM-DD.log (자정 지나면 자동으로 새 파일)
- 각 줄 앞에 [HH:MM:SS] 시각을 붙임
- ❌/⚠️ 줄과 Traceback 은 errors_YYYY-MM-DD.log 에도 따로 모음 (문제 확인용)
- KEEP_DAYS 지난 로그는 시작 시 삭제
"""
import os
import sys
import threading
from datetime import datetime, timedelta

KEEP_DAYS = 30

# 이 표시가 들어간 줄은 errors_YYYY-MM-DD.log 에도 따로 저장
ERROR_MARKS = ("❌", "⚠")

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_log_dir() -> str:
    log_dir = os.getenv("IZI_LOG_DIR") or os.path.join(_BACKEND_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_debug_dir() -> str:
    """스크린샷/HTML 등 장애 증거 저장 폴더"""
    d = os.path.join(get_log_dir(), "debug", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(d, exist_ok=True)
    return d


class _DailyFileTee:
    def __init__(self, stream, log_dir: str, lock: threading.Lock):
        self._stream = stream
        self._log_dir = log_dir
        self._lock = lock
        self._at_line_start = True
        self._line_buf = ""        # 에러 판별용: 아직 줄바꿈 안 된 현재 줄
        self._in_traceback = False

    def _file_path(self) -> str:
        return os.path.join(self._log_dir, f"monitor_{datetime.now():%Y-%m-%d}.log")

    def _error_file_path(self) -> str:
        return os.path.join(self._log_dir, f"errors_{datetime.now():%Y-%m-%d}.log")

    def _is_error_line(self, line: str) -> bool:
        """❌/⚠️ 줄, 그리고 Traceback 블록 전체(마지막 예외 줄까지)를 에러로 판단"""
        body = line[11:] if line.startswith("[") else line  # "[HH:MM:SS] " 제거
        if body.startswith("Traceback"):
            self._in_traceback = True
            return True
        if self._in_traceback:
            # 들여쓴 줄(파일/코드 위치)은 계속, 들여쓰기 없는 줄이 마지막 예외 메시지
            if not body[:1].isspace():
                self._in_traceback = False
            return True
        return any(mark in body for mark in ERROR_MARKS)

    def write(self, s):
        try:
            self._stream.write(s)
        except Exception:
            pass

        if not s:
            return 0

        try:
            with self._lock:
                stamp = f"[{datetime.now():%H:%M:%S}] "
                out = []
                errors = []
                for chunk in s.splitlines(keepends=True):
                    if self._at_line_start:
                        out.append(stamp)
                        self._line_buf = stamp
                    out.append(chunk)
                    self._line_buf += chunk
                    self._at_line_start = chunk.endswith("\n")
                    if self._at_line_start:
                        if self._is_error_line(self._line_buf):
                            errors.append(self._line_buf)
                        self._line_buf = ""
                with open(self._file_path(), "a", encoding="utf-8") as f:
                    f.write("".join(out))
                if errors:
                    with open(self._error_file_path(), "a", encoding="utf-8") as f:
                        f.write("".join(errors))
        except Exception:
            # 로그 저장 실패가 자동화를 멈추면 안 됨
            pass
        return len(s)

    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _cleanup_old_logs(log_dir: str):
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    for root, _dirs, files in os.walk(log_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                    os.remove(path)
            except Exception:
                pass


def install():
    """stdout/stderr 를 콘솔 + 날짜별 파일로 동시에 출력"""
    log_dir = get_log_dir()
    _cleanup_old_logs(log_dir)

    lock = threading.Lock()
    sys.stdout = _DailyFileTee(sys.stdout, log_dir, lock)
    sys.stderr = _DailyFileTee(sys.stderr, log_dir, lock)
    print(f"📝 로그 파일 저장 위치: {log_dir}")
    return log_dir
