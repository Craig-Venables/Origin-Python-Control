# OriginPro scripts for D114, folder B, subfolder all

These are the scripts used on 28 October 2026 against the OriginPro session that already had D114.opju open. Python-Origin-Graph (https://github.com/Craig-Venables/Python-Origin-Graph) is the older plotting repo and was not cloned on this PC, so this folder, Origin-Python-Control, is the local copy next to the other GitHub folders.

None of these scripts save the project or close Origin. The new workbooks are in the open session until D114.opju is saved from Origin.

## Paths

- Project file: `C:\Users\craig\OneDrive - The University of Nottingham\Documents\Phd\1) Projects\1) Memristors\Graphs (origin)\D114.opju`
- Project Explorer folder used for every job: `/D114/B/all/`
- Origin program: `C:\Program Files\OriginLab\Origin2026b\Origin64.exe` (OriginPro 2026b, process Origin64)
- Python: `C:\Users\craig\AppData\Local\Programs\Python\Python310\python.exe`
- Package: `originpro`, installed with `py -3 -m pip install originpro`

The same approach as Python-Origin-Graph: `import originpro as op`, then `op.new_book` and `wks.from_list` to write columns, including the long name and units.

## Connecting without starting a second Origin

1. OriginPro must already be open with D114.
2. In the script, call `op.attach()` before any other originpro call. That uses Origin's single-instance COM object and attaches to the running process.
3. Call `op.set_show(True)` so the window stays visible.
4. Do not call `op.exit()`. When the script finishes, originpro only releases the link.

Skipping `op.attach()` is the workaround that matters. The package would otherwise construct `Origin.Application()`, which starts a second Origin instead of using the one already open.

`list_folder_workbooks.py` was the inventory step. It finds Book51, changes to that book's folder (`/D114/B/all/`), and prints each workbook's long name and the long name and units of its columns. That run showed 17 sweep books, each with Voltage (V), Current (A), and Time (T).

The files in `connection-probes\` were earlier experiments (listing COM methods and LabTalk strings). They are not needed to repeat the jobs.

## 1. One workbook for all 17 sweeps — `combine_all_workbooks.py`

Run only if you want another full copy. The short-name guard looks for `all_combined`, but Origin stored the book as `allcombined`, so running this again will not see the existing book and will create a second one.

What it does:

1. Goes to `/D114/B/all/` and stops if that is not the active folder.
2. Reads every workbook in that folder: values, long name, units, and comments.
3. Creates a book with long name `all combined`. The script asks for short name `all_combined`. Origin saved the short name as `allcombined` (the underscore was dropped).
4. Writes the columns in folder order so each file's voltage, current, and time stay together. Long names and units are copied as they were. 17 books times 3 columns is 51 columns.
5. Sets a user-parameter row named Source to the source book's long name (the txt filename). That does not change the long name or the units. It is there so repeated Voltage / Current / Time headers can be told apart.
6. Reads the source books again and compares labels and the first and last value in each column. The run reported no mismatches.

This script does not set column plot type. On a new sheet the first column stays X and the columns added after it stay Y. That is why, in `allcombined`, only the first Voltage column is an X column. The later Voltage columns were left as they were.

## 2. Separate 1.0 V and 1.5 V books — `group_by_sweep_voltage.py`

Filename shape: `b22-FS-1.0v-0.05sv-0.05sd-Py-Simple_1.5V-.txt`

The group is the first `-<number>v` token. For that example it is `1.0`. The `_1.5V` near the end of many names is not the group. `allcombined` does not match the pattern, so it was skipped.

Groups found:

- 1.0 V, 8 files: b22, b32, b42, b52, b62, b82, b960, b1059. All of these names continue `-FS-1.0v-...`.
- 1.5 V, 9 files: b24, b115, b34, b44, b54, b84, b962, b1061, b64.

What it does:

1. Same attach and folder check as the first script.
2. Creates two books in `/D114/B/all/`.
   - Short name `v1p0`, long name `combined 1.0v` (24 columns). `p` stands for the decimal point, because the short name cannot keep a dot.
   - Short name `v1p5`, long name `combined 1.5v` (27 columns).
3. Copies voltage, current, and time with the original long names and units.
4. Writes the first two characters of the source filename into the comment of each of that file's columns. `b22-FS-...` gives comment `b2`. `b115-FS-...` gives `b1`. The characters keep the filename's own case.
5. For a column whose long name is Voltage, `from_list` is called with `axis='X'`.

If `v1p0` or `v1p5` already exist, the script stops and does not write.

### Column type

`SetColDesignations` on a worksheet is `(designation, repeat, firstColumn, lastColumn)`. `from_list(..., axis='X')` calls it as `SetColDesignations('X', 0, thatColumn, thatColumn)`, which sets only that column to X.

Do not trust LabTalk `wks.col.type` for this check. On these sheets it returned 4 for the voltage columns, and 4 is the old code for a label column, which is the wrong reading. The column object's `GetType()` matches the original sweep books: voltage is 3 (X) and current and time are 0 (Y). `check_column_types.py` prints that. After the grouped books were built, every voltage column in `v1p0` and `v1p5` had `GetType()` 3.

## 3. Absolute current — `add_absolute_current.py`

Adds a column immediately after every current column in the three combined books only: `allcombined`, `v1p0`, and `v1p5`. Original sweep books are not opened for writing. Book35 stayed at 3 columns.

A column counts as current if its long name is `Current`, or its unit is A / amp / amps. Columns whose long name already contains "absolute" are ignored, so a second run does not add another copy when Absolute Current already sits beside Current.

For each match it inserts, immediately to the right:

- Long name: `Absolute Current`
- Unit: `A`
- Values: the absolute value of that current column. Empty cells stay empty.
- Comment and Source parameter, if the current column had them, are copied onto the new column. In `v1p0` and `v1p5` the comment is still the two-character filename prefix (`b2`, `b3`, and so on). In `allcombined` the Source row still carries the txt filename.
- Plot type of the new column is Y. Existing columns keep the plot type they already had, including X on the voltage columns in `v1p0` and `v1p5`.

Resulting sizes:

- `allcombined`: 51 columns before, 17 absolute-current columns added, 68 after
- `v1p0`: 24 before, 8 added, 32 after
- `v1p5`: 27 before, 9 added, 36 after

Column order in each group is Voltage, Current, Absolute Current, Time. A negative current such as `-6.93e-10` became `6.93e-10` in the new column. `check_absolute_current.py` prints a sample pair from each book.

## 4. One overlaid plot per workbook — `plot_voltage_vs_absolute_current.py`

One graph for each combined workbook. Every sweep in that book is a line on the same graph. Voltage is X. Absolute current is Y. There is not a separate graph per sweep.

The Python-Origin-Graph repo plots with `wks.plot_cloneable` and a cloneable template (`LOG+IV_v3.otpu` or `Electron_transport_Final.otpu`). Those templates expect one sweep laid out in fixed columns, including calculated transport columns, so they were not used on these side-by-side sheets. The plot still goes through originpro: `op.new_graph` uses Origin's line template, then `layer.add_plot(..., type='l')` adds one line per sweep.

What it does:

1. Same attach, and it works in `/D114/B/all/`.
2. In each of `allcombined`, `v1p0`, and `v1p5`, pairs every Voltage column with the Absolute Current column that follows it.
3. Creates one graph and adds every pair as a line. The X and Y of each line are set explicitly, so a voltage column that is still marked Y in `allcombined` is still used as X on the graph.
4. Rescales the axes. X title is `Voltage (V)`. Y title is `Absolute Current (A)`.
5. The legend uses the Source filename when that row is set (`allcombined`), otherwise the two-character comment (`b2`, `b3`, and so on).

Graphs, all in `/D114/B/all/`:

| Workbook | Graph short name | Long name | Traces |
| --- | --- | --- | --- |
| allcombined | gAbsAll | allcombined \|I\| vs V | 17 |
| v1p0 | gAbs10 | combined 1.0v \|I\| vs V | 8 |
| v1p5 | gAbs15 | combined 1.5v \|I\| vs V | 9 |

The script stops if one of those short names already exists. It does not change the worksheet columns.

## Run them

From a command prompt, with Origin already open on D114:

```
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\list_folder_workbooks.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\combine_all_workbooks.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\group_by_sweep_voltage.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\add_absolute_current.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\plot_voltage_vs_absolute_current.py"
```

Save D114.opju from Origin when the new books should be kept on disk. These scripts do not save it.
