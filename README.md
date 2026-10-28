# Origin-Python-Control

Python scripts that drive a running OriginPro session. They were written on 28 October 2026 for the open project D114, and they use the `originpro` package the same way [Python-Origin-Graph](https://github.com/Craig-Venables/Python-Origin-Graph) does: `import originpro as op`, then create books and fill columns with `wks.from_list`, including long names and units.

This repository is local only. It has not been pushed.

## What the project does

The source data is already inside D114, in Project Explorer folder `/D114/B/all/`. That folder holds 17 sweep workbooks. Each book is one text file imported as three columns: Voltage (V), Current (A), and Time (T).

The scripts, in the order they were run:

1. List those workbooks.
2. Copy all 17 into one new workbook, `allcombined`, without changing the originals.
3. Copy them again into two workbooks split by sweep voltage: `v1p0` (1.0 V) and `v1p5` (1.5 V). Voltage columns in those two books are X columns. Each new column's comment is the first two characters of the source filename.
4. Add an Absolute Current column beside every Current column in those three combined books.
5. Draw one graph per combined book. Every sweep in that book is a line on the same axes: voltage on X, absolute current on Y.

Nothing here saves `D114.opju` or closes Origin. Save from Origin when the new books and graphs should be kept on disk.

## Prerequisites

- Windows, with OriginPro already running and D114.opju open. These scripts attach to that process. They do not start Origin.
- OriginPro 2026b, installed at `C:\Program Files\OriginLab\Origin2026b\`. The process name is `Origin64`.
- Python 3.10: `C:\Users\craig\AppData\Local\Programs\Python\Python310\python.exe` (`py -3` on this PC).
- The `originpro` package:

```
py -3 -m pip install originpro
```

The files in `connection-probes\` also need `pywin32` (`pip install pywin32`). The main scripts do not.

## How a script connects

Every main script starts like this, and `op.attach()` has to be the first originpro call:

```python
import originpro as op
op.attach()
op.set_show(True)
```

`op.attach()` uses Origin's single-instance COM object, so the call joins the OriginPro window that is already open. If you skip it, the package builds `Origin.Application()`, which starts a second Origin and will not see the open D114 project.

`op.set_show(True)` keeps that window visible. Do not call `op.exit()`. When the script ends, originpro drops the link and leaves Origin running.

The scripts then move Project Explorer to `/D114/B/all/` and refuse to write if that is not the active folder.

## Names inside D114

The project file is:

`C:\Users\craig\OneDrive - The University of Nottingham\Documents\Phd\1) Projects\1) Memristors\Graphs (origin)\D114.opju`

Project Explorer path used by every script: `/D114/B/all/`

That is project D114, folder B, subfolder `all`. The 17 sweep books live directly in `all`, not in a further subfolder.

Each sweep book's long name is the text filename. The shape is:

`b22-FS-1.0v-0.05sv-0.05sd-Py-Simple_1.5V-.txt`

Read it as:

| Piece | Example | Meaning |
| --- | --- | --- |
| First two characters | `b2` | Written into the column comment by the grouping script. `b115-FS-...` gives `b1`. Case stays as in the filename. |
| Device token | `b22` | The bit before `-FS-`. |
| Sweep voltage | `1.0` in `-FS-1.0v` | The first `-<number>v` token. This is the group: 1.0 V or 1.5 V. |
| Later tokens | `0.05sv`, `0.05sd` | Step and delay. Not used for grouping. |
| Trailing `_1.5V` | on many names | Not the group. It appears on both 1.0 V and 1.5 V files. |

Books created by the scripts, all in `/D114/B/all/`:

| Short name | Long name | What it is |
| --- | --- | --- |
| `allcombined` | all combined | All 17 sweeps side by side. The script asked for `all_combined`; Origin dropped the underscore. |
| `v1p0` | combined 1.0v | The eight 1.0 V files. `p` stands for the decimal point. |
| `v1p5` | combined 1.5v | The nine 1.5 V files. |
| `gAbsAll` | allcombined \|I\| vs V | One graph, 17 lines, from `allcombined`. |
| `gAbs10` | combined 1.0v \|I\| vs V | One graph, 8 lines, from `v1p0`. |
| `gAbs15` | combined 1.5v \|I\| vs V | One graph, 9 lines, from `v1p5`. |

Column order in the three combined books, repeated once per source file: Voltage, Current, Absolute Current, Time. Long names and units on Voltage, Current, and Time are copies of the source. Absolute Current is in amps (A).

## Repository layout

```
Origin-Python-Control/
  README.md
  list_folder_workbooks.py              read-only inventory of /D114/B/all/
  combine_all_workbooks.py              build allcombined
  group_by_sweep_voltage.py             build v1p0 and v1p5
  add_absolute_current.py               add |I| beside each current column
  plot_voltage_vs_absolute_current.py   one overlaid graph per combined book
  check_column_types.py                 print GetType() for Book35 and v1p0
  check_absolute_current.py             print a sample |I| pair from each combined book
  connection-probes/                    early COM experiments, not needed to repeat the jobs
```

Run them from a command prompt with Origin already open on D114. The order below is the order that built the books. Later scripts expect the books from the earlier ones.

```
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\list_folder_workbooks.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\combine_all_workbooks.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\group_by_sweep_voltage.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\add_absolute_current.py"
py -3 "C:\Users\craig\OneDrive\Documents\GitHub\Origin-Python-Control\plot_voltage_vs_absolute_current.py"
```

## What each script does

### `list_folder_workbooks.py`

Input: the open project. It looks up the workbook short name `Book51` and changes to that book's folder, which is `/D114/B/all/`.

Output: printed lines only. For each workbook in the folder it prints the short name, the long name (the txt filename), the column count, the row count, and the long name and units of the first columns. The run that started this work found 17 books, each with Voltage (V), Current (A), and Time (T). It does not create or edit anything.

### `combine_all_workbooks.py`

Input: every workbook currently in `/D114/B/all/`.

Steps:

1. Attach, show Origin, and go to `/D114/B/all/`. Stop if the active folder is anything else.
2. Read each workbook's columns: values, long name, units, comments, row count, and the first and last value.
3. Create a workbook with long name `all combined` and ask for short name `all_combined`. Origin stored the short name as `allcombined`.
4. Write the columns in folder order so each file's voltage, current, and time stay together. Long names and units are copied as they were. 17 books times 3 columns made 51 columns.
5. Set a user-parameter row named Source to the source book's long name, so the repeated Voltage / Current / Time headers can be told apart. That row is not the long name and not the units.
6. Read the source books again and compare labels and endpoints. The run reported no mismatches.

This script does not set plot designation. On a new sheet the first column stays X and later columns stay Y, so in `allcombined` only the first Voltage column is an X column.

Do not run it again to "refresh" the book. The guard looks for the short name `all_combined`, which is not the name Origin kept, so a second run creates another workbook.

### `group_by_sweep_voltage.py`

Input: workbooks in `/D114/B/all/` whose long name matches `b22-FS-1.0v-...`. `allcombined` does not match, so it is skipped.

The group key is the first `-<number>v` token (`1.0` or `1.5`), not the `_1.5V` near the end of a name.

Groups from the session:

- 1.0 V, 8 files: b22, b32, b42, b52, b62, b82, b960, b1059.
- 1.5 V, 9 files: b24, b115, b34, b44, b54, b84, b962, b1061, b64.

Steps:

1. Same attach and folder check.
2. Create `v1p0` / `combined 1.0v` and `v1p5` / `combined 1.5v` in `/D114/B/all/`.
3. Copy voltage, current, and time with the original long names and units.
4. Put the first two filename characters in the comment of each of that file's columns.
5. For a column whose long name is Voltage, call `from_list` with `axis='X'`.

Before the absolute-current step these books had 24 and 27 columns. The script stops if `v1p0` or `v1p5` already exist.

`from_list(..., axis='X')` calls `SetColDesignations('X', 0, thatColumn, thatColumn)`. The arguments are designation, repeat flag, first column, last column, so only that one column becomes X.

Check plot type with the column object's `GetType()`, not LabTalk `wks.col.type`. On these sheets `wks.col.type` returned 4, which is the old code for a label column and is the wrong reading. `GetType()` matches the original sweeps: voltage is 3 (X), current and time are 0 (Y). `check_column_types.py` prints the first columns of `Book35` and `v1p0`. After grouping, every voltage column in `v1p0` and `v1p5` was type 3.

### `add_absolute_current.py`

Input: the three combined books `allcombined`, `v1p0`, and `v1p5`. It does not write the original sweep books. `Book35` stayed at 3 columns.

A column counts as current when its long name is `Current`, or its unit is A, amp, or amps. A long name that already contains "absolute" is ignored, so a second run does not insert another copy when Absolute Current is already beside Current.

Immediately to the right of each match it inserts:

- Long name `Absolute Current`, unit `A`.
- The absolute value of that current. Empty cells stay empty.
- The same comment and Source parameter as the current column, when those were set.
- Plot type Y. Existing columns keep the type they already had.

Sizes after this step: `allcombined` 68 columns (17 new), `v1p0` 32 (8 new), `v1p5` 36 (9 new). A value such as `-6.93e-10` became `6.93e-10`. `check_absolute_current.py` prints one such pair from each book.

### `plot_voltage_vs_absolute_current.py`

Input: the three combined books, after absolute current exists. It does not change worksheet columns.

One graph per workbook. Every sweep in that book is a line on that one graph. There is not a separate graph per sweep.

Python-Origin-Graph plots with `wks.plot_cloneable` and a cloneable template (`LOG+IV_v3.otpu` or `Electron_transport_Final.otpu`). Those templates expect one sweep in a fixed set of columns, including transport calculations, so they were not used on these side-by-side sheets. This script still plots through originpro: `op.new_graph` opens Origin's line template, then `layer.add_plot(..., type='l')` adds one line per sweep. X and Y are set explicitly, so a voltage column that is still marked Y in `allcombined` is still the X of its line.

Steps:

1. Attach and require `/D114/B/all/`.
2. Pair each Voltage column with the Absolute Current column that follows it.
3. Add every pair as a line, rescale, and title the axes `Voltage (V)` and `Absolute Current (A)`.
4. Legend text is the Source filename when that row is set (`allcombined`), otherwise the two-character comment.

The script stops if `gAbsAll`, `gAbs10`, or `gAbs15` already exist.

## Templates for a single sweep

Python-Origin-Graph and the copy under Pandas_test `Graph/Origin/` each keep the same three files: `Electron_transport_Final.otpu` (transport curves), `LOG+IV_v3.otpu` (IV and log IV), and `MasterTemplate_v2.ogwu` (a workbook template, not a graph style). Those graph templates expect one sweep laid out in fixed columns.

On this PC there is also a user-defined cloneable template for plotting an individual IV sweep later:

`C:\Users\craig\Documents\OriginLab\User Files\IV+LOGIV(INDEX).otpu`

The name on disk is `IV+LOGIV(INDEX).otpu`. Use it with `wks.plot_cloneable` on a single-sweep sheet, the same way Python-Origin-Graph uses `LOG+IV_v3.otpu`. It is not wired into the scripts in this repo.

## Highlighting the first sweep

For a plot with 20 or more sweeps, and especially 50 or more, highlight the first sweep in red so it can be seen among the others.

Do it this way:

1. Work out the voltage trace and how many loops it contains.
2. Divide the trace by that number of loops so the first sweep is a block of points on its own.
3. Put just that first sweep into a new column. Leave the other sweeps as they are.
4. Draw that new column in red, with a slightly thicker line.
5. Give both the red trace and the other traces a little transparency.

None of the scripts here do this yet. It is the preference for the next large multi-sweep plot.

### Check scripts

`check_column_types.py` prints `GetType()` and the first three labels for `Book35` and `v1p0`. It only reads.

`check_absolute_current.py` prints the column count of `allcombined`, `v1p0`, and `v1p5`, and one negative current next to its absolute value. It only reads.

## Connection probes

`connection-probes\` holds the first attempts, made with `win32com` and `Origin.ApplicationSI` before the jobs switched to `originpro`. They print the active page, COM method names, or column labels. They are not part of the combine or plot sequence. Several of them call `BeginSession` and `EndSession`; run those only if you mean to poke at the live session.
