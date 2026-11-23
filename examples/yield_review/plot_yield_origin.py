"""Draw the Zn-Cu-In-S yield figures in the Origin session that is already open.

Does not save the project. Replaces the yield-review books and graphs if they
are already in the yield review folder.

    py -3 examples/yield_review/plot_yield_origin.py
    py -3 examples/yield_review/plot_yield_origin.py --keep-d60
    py -3 examples/yield_review/plot_yield_origin.py --data path\\to\\yield_review

The default leaves D60 out and fits each axis to the rows that remain.
--keep-d60 plots every sample in the tables, including D60.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
GREEN = "#2ca02c"
BLUE = "#1f77b4"
ORANGE = "#ff7f0e"
SWEEP = "#8eafc8"
GRAY = "#b3b3b3"
GOLD = "#f0a202"
STACK_BLUE = "#4c78a8"


def read_table(path, drop_d60):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < len(header):
            parts += [""] * (len(header) - len(parts))
        row = {}
        for key, raw in zip(header, parts):
            text = raw.strip()
            if text == "":
                row[key] = None
                continue
            try:
                number = float(text)
            except ValueError:
                row[key] = text
                continue
            row[key] = int(number) if number.is_integer() else number
        if drop_d60 and row.get("sample_id") == "D60":
            continue
        rows.append(row)
    if not rows:
        raise SystemExit(f"{path.name} has no rows to plot")
    return rows


def xtick(row):
    conc = f"{float(row['concentration_mgml']):g} mg/ml"
    return f"{row['sample_id']}\n{conc}\nn={int(row['n_devices'])}"


def nice_top(values, step, floor):
    finite = [float(value) for value in values if value is not None]
    peak = max(finite) if finite else floor
    top = max(floor, step * math.ceil((peak * 1.12) / step))
    return top, step


def lt(target, command):
    ok = target.LT_execute(command)
    if not ok:
        print("LT FAIL", command)
    return ok


def enter_folder(op):
    op.pe.cd("/")
    made = op.pe.mkdir("yield review", True)
    op.pe.cd(made)
    active = op.pe.active_folder().path
    print("FOLDER", active)
    if "yield review" not in active.lower():
        raise SystemExit(f"refusing to write, active folder is {active!r}")
    return active


def drop(op, short):
    located = op.pe.search(short, 0) or ""
    if not located:
        return
    if "yield review" not in located.lower():
        raise SystemExit(f"{short} already exists in {located}")
    page = op.find_book("w", short)
    if page is None:
        page = op.find_graph(short)
    if page is not None:
        page.obj.Destroy()


def put_text(sheet, index, values, long_name, axis):
    if sheet.obj.Cols <= index:
        sheet.obj.Cols = index + 1
    text = ["" if value is None else str(value) for value in values]
    column = sheet.obj.Columns(index)
    column.SetDataFormat(1)
    sheet.from_list(index, text, lname=long_name, axis=axis)
    column.SetDataFormat(1)
    column.SetData(text)


def put_num(sheet, index, values, long_name, axis):
    if sheet.obj.Cols <= index:
        sheet.obj.Cols = index + 1
    sheet.from_list(
        index,
        [0.0 if value is None else float(value) for value in values],
        lname=long_name,
        axis=axis,
    )
    for row, value in enumerate(values, start=1):
        if value is None:
            lt(sheet.obj, f"wks.col{index + 1}[{row}] = NANUM;")


def new_sheet(op, short, long_name):
    drop(op, short)
    book = op.new_book("w", long_name)
    book.name = short
    book.lname = long_name
    return book[0]


def paint(plots, colors):
    for plot, color in zip(plots, colors):
        plot.color = color
    print("COLORS", [plot.color for plot in plots])


def plotxy(op, sheet, iy, template, plot_id, name, long_name):
    drop(op, name)
    command = (
        f"plotxy iy:={sheet.lt_range()}!{iy} plot:={plot_id} "
        f"ogl:=[<new template:={template} name:={name}>];"
    )
    print("PLOTXY", lt(sheet.obj, command))
    graph = op.find_graph(name)
    if graph is None:
        raise SystemExit(f"Origin did not create {name}")
    graph.lname = long_name
    lt(graph.obj, "page.lock = 0;")
    lt(graph.obj, "page.width = 9600;")
    lt(graph.obj, "page.height = 7000;")
    return graph


def place(graph, layer_number, left, top, width, height):
    lt(graph.obj, f"page.active = {layer_number};")
    lt(graph.obj, "layer.unit = 0;")
    lt(graph.obj, f"layer.left = {left};")
    lt(graph.obj, f"layer.top = {top};")
    lt(graph.obj, f"layer.width = {width};")
    lt(graph.obj, f"layer.height = {height};")


def style_y(layer, title, y0, y1, step):
    layer.axis("y").title = title
    layer.axis("x").title = ""
    lt(layer.obj, "layer.x.label.pt = 16;")
    lt(layer.obj, "layer.y.label.pt = 18;")
    lt(layer.obj, "layer.x.ticklabel.pt = 12;")
    lt(layer.obj, "layer.y.ticklabel.pt = 14;")
    layer.rescale()
    lt(layer.obj, f"layer.y.from = {y0};")
    lt(layer.obj, f"layer.y.to = {y1};")
    lt(layer.obj, f"layer.y.inc = {step};")
    print("LIMITS", layer.xlim, layer.ylim)


def write_legend(layer, lines, size, x, y):
    from originpro.utils import set_lt_str

    set_lt_str("py_leg", "\n".join(lines))
    lt(layer.obj, "legend -r;")
    lt(layer.obj, "legend.text$ = py_leg$;")
    lt(layer.obj, f"legend.fsize = {int(size)};")
    lt(layer.obj, "legend.background = 1;")
    for obj in layer.obj.GraphObjects:
        if obj.GetName() == "Legend":
            obj.SetX(x)
            obj.SetY(y)
            obj.SetShow(True)


def yield_sheet(op, short, long_name, rows):
    sheet = new_sheet(op, short, long_name)
    put_text(sheet, 0, [xtick(row) for row in rows], "Sample", "X")
    for offset, (key, name) in enumerate((("yield_ge4", "≥4"), ("yield_ge10", "≥10"), ("yield_ge20", "≥20"))):
        put_num(sheet, 1 + offset * 2, [row[key] for row in rows], name, "Y")
    put_num(sheet, 7, [row["n_memristive_sweeps"] for row in rows], "Weighted memristive sweeps", "Y")
    return sheet


def finish_yield(op, rows, book, graph_name, long_name):
    sheet = yield_sheet(op, book, long_name, rows)
    graph = plotxy(op, sheet, "((1,2),(1,4),(1,6))", "COLUMN", 203, graph_name, long_name)
    graph.add_layer(0)
    place(graph, 1, 14, 12, 78, 46)
    place(graph, 2, 14, 60, 78, 30)
    yields = [row[key] for row in rows for key in ("yield_ge4", "yield_ge10", "yield_ge20")]
    y_top, y_step = nice_top(yields, 0.2, 1)
    top = graph[0]
    paint(top.plot_list(), [GREEN, BLUE, ORANGE])
    style_y(top, "Device yield (fraction)", 0, y_top, y_step)
    write_legend(
        top,
        ["Loop-score gate", r"\l(1) ≥4", r"\l(2) ≥10", r"\l(3) ≥20"],
        13,
        max(1.6, len(rows) * 0.5),
        y_top * 0.9,
    )
    sweeps_top, sweeps_step = nice_top([row["n_memristive_sweeps"] for row in rows], 100, 100)
    bottom = graph[1]
    sweeps = bottom.add_plot(sheet, coly=7, colx=0, type="c")
    sweeps.color = SWEEP
    style_y(bottom, "Weighted memristive sweeps", 0, sweeps_top, sweeps_step)
    graph.activate()
    print("GRAPH", graph.name, long_name)
    return graph


def finish_stack(op, rows):
    sheet = new_sheet(op, "wYield20", "Reached 20 only when run that long")
    put_text(sheet, 0, [xtick(row) for row in rows], "Sample", "X")
    series = (
        ("n_never_4", "Did not reach 4 memristive sweeps"),
        ("n_stopped_before_20", "Memristive, test stopped before 20 sweeps"),
        ("n_swept_20_but_under", "Swept at least 20 times, score stayed under 20"),
        ("n_reached_20", "Memristive score reached 20"),
    )
    for index, (key, name) in enumerate(series, start=1):
        put_num(sheet, index, [row[key] or 0 for row in rows], name, "Y")
    percents = [
        None if row["n_run_long_enough"] in (None, 0) else row["yield_among_run_long_pct"]
        for row in rows
    ]
    put_num(sheet, 5, percents, "Reached 20 among devices run that long", "Y")
    graph = plotxy(op, sheet, "(1,2:5)", "StackColumn", 213, "gYield20", "Reached 20 only when run that long")
    graph.add_layer(0)
    place(graph, 1, 14, 14, 78, 44)
    place(graph, 2, 14, 60, 78, 30)
    totals = [
        sum(row[key] or 0 for key, _name in series)
        for row in rows
    ]
    device_top, device_step = nice_top(totals, 5, 10)
    top = graph[0]
    paint(top.plot_list(), [GRAY, GOLD, STACK_BLUE, GREEN])
    style_y(top, "Devices", 0, device_top, device_step)
    write_legend(
        top,
        [
            r"\l(1) Did not reach 4 memristive sweeps",
            r"\l(2) Memristive, test stopped before 20 sweeps",
            r"\l(3) Swept at least 20 times, score stayed under 20",
            r"\l(4) Memristive score reached 20",
        ],
        11,
        max(1.4, len(rows) * 0.35),
        device_top * 0.9,
    )
    percent_top, percent_step = nice_top(percents, 20, 100)
    bottom = graph[1]
    bars = bottom.add_plot(sheet, coly=5, colx=0, type="c")
    bars.color = GREEN
    style_y(bottom, "Reached 20, among devices that were run that long (%)", 0, percent_top, percent_step)
    graph.activate()
    print("GRAPH", graph.name)
    return graph


def main():
    parser = argparse.ArgumentParser(description="Plot the yield-review figures in the open Origin session.")
    parser.add_argument("--data", type=Path, default=DATA, help="Folder of the three origin_*.txt tables.")
    parser.add_argument("--keep-d60", action="store_true", help="Plot D60 as well as the other samples.")
    args = parser.parse_args()
    import originpro as op

    op.attach()
    op.set_show(True)
    enter_folder(op)
    drop_d60 = not args.keep_d60
    reviewed = read_table(args.data / "origin_same_stack_yield_reviewed.txt", drop_d60)
    long_enough = read_table(args.data / "origin_same_stack_yield_run_long_enough.txt", drop_d60)
    reached = read_table(args.data / "origin_yield_20_only_when_run_that_long.txt", drop_d60)
    print("REVIEWED", [row["sample_id"] for row in reviewed])
    print("LONG", [row["sample_id"] for row in long_enough])
    print("REACHED", [row["sample_id"] for row in reached])
    finish_yield(op, reviewed, "wYieldRev", "gYieldRev", "Same-stack yield, reviewed")
    finish_yield(op, long_enough, "wYieldLong", "gYieldLong", "Same-stack yield, run long enough")
    finish_stack(op, reached)
    print("DONE")


if __name__ == "__main__":
    main()
