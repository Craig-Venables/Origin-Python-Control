# Examples

Origin has to be open on the D114 project first. None of these save it.

`b9_eis.py` fits the B9 Solartron spectra with `scripts/fit_cf_all.py` and `sets/d114_b9.json`. Graphs land in `/D114/B/9/CF/cf_cursor/`.

`b9_pulses.py` plots the three endurance runs and the two timed-retention runs with `scripts/pulse_origin.py`. Graphs land in `/D114/B/9/Pulse/`. The same two jobs are in `gui.py`.

```
py -3 examples/b9_eis.py
py -3 examples/b9_pulses.py
```
