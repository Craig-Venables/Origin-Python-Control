"""Fit the D114 B9 Solartron spectra in the open Origin project.

Origin must already be open on D114. Books and graphs go to
/D114/B/9/CF/cf_cursor/. The project is not saved.

    py -3 examples/b9_eis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fit_cf_all

SET = ROOT / "sets" / "d114_b9.json"


def main():
    sys.argv = [str(Path(fit_cf_all.__file__)), str(SET)]
    return fit_cf_all.main()


if __name__ == "__main__":
    sys.exit(main() or 0)
