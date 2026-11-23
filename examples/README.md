# Examples

None of these save the Origin project.

## D114 B9

Origin has to be open on the D114 project first.

`b9_eis.py` fits the B9 Solartron spectra with `scripts/fit_cf_all.py` and `sets/d114_b9.json`. Graphs land in `/D114/B/9/CF/cf_cursor/`.

`b9_pulses.py` plots the three endurance runs and the two timed-retention runs with `scripts/pulse_origin.py`. Graphs land in `/D114/B/9/Pulse/`. The same two jobs are in `gui.py`.

```
py -3 examples/b9_eis.py
py -3 examples/b9_pulses.py
```

## Zn-Cu-In-S yield review

`yield_review/plot_yield_origin.py` draws the three same-stack yield figures in the Origin session that is already open. It does not need the D114 project. Books and graphs go in a Project Explorer folder named `yield review`. The tables are in `yield_review/data/`.

D60 is left out unless `--keep-d60` is set. Each axis is fitted to the rows that are plotted.

```
py -3 examples/yield_review/plot_yield_origin.py
py -3 examples/yield_review/plot_yield_origin.py --keep-d60
```
