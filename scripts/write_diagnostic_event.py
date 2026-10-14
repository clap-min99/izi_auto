"""Shutdown-script lifecycle logging, without Django or external services."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'backend'))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    from pianos.automation.diagnostics import Diagnostics
    collector = Diagnostics()
    collector.event(sys.argv[1], source='stop_script')
    collector._write(collector.events.get_nowait())
except Exception:
    # Diagnostics must not prevent shutdown.
    pass
