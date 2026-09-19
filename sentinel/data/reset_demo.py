"""
data/reset_demo.py
--------------------
Resets SRV-002 back to a critical-load state (CPU 88.5%, MEM 92.3%) so you
can re-run `python main.py demo` and see the full Monitor -> Diagnose ->
Remediate -> Verify cycle again, instead of getting HEALTHY because a
previous demo run already fixed it.

Run from the sentinel/ folder:
    py data/reset_demo.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "system_telemetry.db"

conn = sqlite3.connect(DB_PATH)
conn.execute(
    "UPDATE servers SET cpu_usage_percent = 88.5, memory_usage_percent = 92.3 "
    "WHERE server_id = 'SRV-002'"
)
conn.commit()
conn.close()

print("SRV-002 reset to critical load (CPU 88.5%, MEM 92.3%). Run 'py main.py demo' now.")
