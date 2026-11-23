"""Plot the D114 B9 endurance and retention files in the open Origin project.

Origin must already be open. Books and graphs go to /D114/B/9/Pulse/.
The project is not saved.

    py -3 examples/b9_pulses.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from origin_session import connect
import pulse_origin

DATA = Path(
    r"C:\Users\craig\OneDrive - The University of Nottingham\Documents"
    r"\Data_folder\D114\B\9\Pulse_measurements"
)
FOLDER = "/D114/B/9/Pulse/"
ENDURANCE = (
    "13-Endurance-2.5V_1ms_10000cyc-20260811_155116.txt",
    "26-Endurance-2.5V_1ms_10000cyc-20260811_161717.txt",
    "28-Endurance-2.5V_10ms_10000cyc-20260811_162720.txt",
)
RETENTION = (
    "52-Timed_Retention-2.8V_10ms-20260814_210533.txt",
    "53-Timed_Retention-2.8V_10ms-20260817_045011.txt",
)


def main():
    connect("attach")
    pulse_origin.run([DATA / name for name in ENDURANCE], FOLDER, "endurance")
    pulse_origin.run([DATA / name for name in RETENTION], FOLDER, "retention")


if __name__ == "__main__":
    main()
