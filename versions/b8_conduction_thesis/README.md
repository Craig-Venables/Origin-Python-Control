# B8 conduction, thesis version

Frozen copy of the D114 device B8 conduction pages, 31 October 2026.
The live scripts stay in `scripts/` and `fit_conduction_mechanisms.py`.
This folder is the version that was checked on screen.

Last cycle only. Circles are the outward sweep and triangles are the return.
Solid lines fit the outward sweep and dashed lines fit the return.
Earlier cycles are not drawn. SCLC labels every gradient with its R², for
both the outward and the return sweep. Schottky, Poole–Frenkel and
Fowler–Nordheim each get a fit and an R² on both legs.

Run from the repository root, with Origin already open on D114:

```
py -3 versions/b8_conduction_thesis/scripts/conduction_b8.py
py -3 versions/b8_conduction_thesis/scripts/conduction_b8_python.py
```

Origin pages go to `/D114/B/8/conduction/`. The project is not saved.
The Python figures in `plots/b8_conduction/` are the six pages for sweeps 4 and 12.
