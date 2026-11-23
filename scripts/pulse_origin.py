"""Endurance and retention graphs in the open Origin session.

Does not save the project.

    py -3 scripts/pulse_origin.py endurance /D114/B/9/Pulse/ file1.txt file2.txt
    py -3 scripts/pulse_origin.py retention /D114/B/9/Pulse/ file1.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui_logic import pulse_names, read_pulse, same_folder

FILE_COLORS = ("#1f4e79", "#0f7b6c", "#c45c26", "#6c5480", "#9b2226")
SET_COLOR = "#1f4e79"
RESET_COLOR = "#c45c26"
BASELINE_COLOR = "#9a7209"
POST_COLOR = "#9b2226"
LINE_COLOR = "#1f4e79"


def _op():
    import originpro as op

    return op


def fail(message):
    raise SystemExit(message)


def drop_named(name, folder):
    op = _op()
    located = op.pe.search(name, 0) or ""
    if not located:
        return
    if not same_folder(located, folder):
        fail(f"{name} already exists in {located}")
    page = op.find_book("w", name)
    if page is None:
        page = op.find_graph(name)
    if page is not None:
        page.obj.Destroy()


def fill(sheet, columns):
    for index, (values, long_name, units, axis) in enumerate(columns):
        sheet.from_list(index, list(values), lname=long_name, units=units, axis=axis)


def style_frame(layer):
    layer.obj.LT_execute("layer.x.label.pt = 20")
    layer.obj.LT_execute("layer.y.label.pt = 20")
    layer.obj.LT_execute("layer.x.ticklabel.pt = 16")
    layer.obj.LT_execute("layer.y.ticklabel.pt = 16")
    layer.obj.LT_execute("layer.x.ticks.dir = 2")
    layer.obj.LT_execute("layer.y.ticks.dir = 2")


def write_legend(layer, entries, size=14):
    from originpro.utils import set_lt_str

    text = "\n".join(rf"\l({index}) {name}" for index, name in entries)
    set_lt_str("py_leg", text)
    layer.obj.LT_execute("legend -r")
    layer.obj.LT_execute("legend.text$ = py_leg$")
    layer.obj.LT_execute(f"legend.fsize = {int(size)}")
    layer.obj.LT_execute("legend.background = 1")


def new_graph(short, long_name, folder):
    op = _op()
    drop_named(short, folder)
    graph = op.new_graph(long_name)
    graph.name = short
    graph.obj.LT_execute("page.lock = 0")
    graph.obj.LT_execute("page.width = 6400")
    graph.obj.LT_execute("page.height = 4200")
    return graph


def add_line(layer, sheet, y_index, x_index, color, dash, width=1.6):
    plot = layer.add_plot(sheet, coly=y_index, colx=x_index, type="l")
    plot.color = color
    plot.set_cmd(f"-d {int(dash)}", f"-w {width}")
    return plot


def add_point(layer, sheet, y_index, x_index, color, kind):
    plot = layer.add_plot(sheet, coly=y_index, colx=x_index, type="s")
    plot.color = color
    plot.symbol_kind = kind
    plot.symbol_size = 14
    plot.symbol_interior = 1
    return plot


def set_limits(graph, x0, x1, y0, y1, log_x=False):
    graph.obj.LT_execute("page.active = 1")
    if log_x:
        graph.obj.LT_execute("layer.x.type = 2")
        graph.obj.LT_execute("layer.x.inc = 1")
    graph.obj.LT_execute(f"layer.x.from = {float(x0):.8g}")
    graph.obj.LT_execute(f"layer.x.to = {float(x1):.8g}")
    graph.obj.LT_execute(f"layer.y.from = {float(y0):.8g}")
    graph.obj.LT_execute(f"layer.y.to = {float(y1):.8g}")


def span(values, pad=0.08, floor_at_zero=False):
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        hi = lo + 1.0
    extra = pad * (hi - lo)
    if floor_at_zero and lo >= 0:
        lo = 0.0
    else:
        lo -= extra
    return lo, hi + extra


def log_span(values):
    positive = [value for value in values if value > 0]
    if len(positive) < 2:
        fail("log axis needs positive values")
    lo, hi = min(positive), max(positive)
    return lo / 1.6, hi * 1.4


def stamp(graph, text):
    safe = text.replace('"', "'")
    graph.obj.LT_execute("page.active = 1")
    graph.obj.LT_execute("label -r runtitle")
    graph.obj.LT_execute(f'label -s -n runtitle "{safe}";')
    graph.obj.LT_execute("runtitle.fsize = 16; runtitle.x = 50; runtitle.y = 3;")


def finish(graph, layer, x0, x1, y0, y1, x_title, log_x, legend, legend_size):
    layer.axis("x").title = x_title
    layer.axis("y").title = "Resistance (Ω)"
    style_frame(layer)
    if log_x:
        layer.xscale = "log10"
    set_limits(graph, x0, x1, y0, y1, log_x)
    write_legend(layer, legend, legend_size)
    graph.activate()


def endurance_columns(record):
    groups = record["groups"]
    columns = []
    plotted = []
    for operation, color in (("SET", SET_COLOR), ("RESET", RESET_COLOR)):
        group = groups[operation]
        columns.append((group["cycle"], f"Cycle {operation}", "", "X"))
        columns.append((group["resistance"], f"R {operation}", "Ω", "Y"))
        plotted.append((operation, color, 0))
    return columns, plotted


def retention_columns(record):
    """Retention reads are the line. Baseline and the post-pulse read stay points.

    A two-point segment joins those two reads. It does not continue to the
    first retention read, which is a minute later and would look like data.
    """
    groups = record["groups"]
    hold = groups["retention"]
    columns = [
        (hold["time"], "Time", "s", "X"),
        (hold["resistance"], "Resistance", "Ω", "Y"),
    ]
    if "baseline" in groups and "post_pulse" in groups:
        columns.append((groups["baseline"]["time"] + groups["post_pulse"]["time"], "Time pulse", "s", "X"))
        columns.append(
            (groups["baseline"]["resistance"] + groups["post_pulse"]["resistance"], "R pulse", "Ω", "Y")
        )
    if "baseline" in groups:
        columns.append((groups["baseline"]["time"], "Time baseline", "s", "X"))
        columns.append((groups["baseline"]["resistance"], "R baseline", "Ω", "Y"))
    if "post_pulse" in groups:
        columns.append((groups["post_pulse"]["time"], "Time after pulse", "s", "X"))
        columns.append((groups["post_pulse"]["resistance"], "R after pulse", "Ω", "Y"))
    return columns


def plot_endurance(record, book_name, graph_name, folder):
    op = _op()
    drop_named(book_name, folder)
    book = op.new_book("w", record["name"])
    book.name = book_name
    columns, _plotted = endurance_columns(record)
    fill(book[0], columns)
    graph = new_graph(graph_name, record["label"], folder)
    layer = graph[0]
    add_line(layer, book[0], 1, 0, SET_COLOR, 0)
    add_line(layer, book[0], 3, 2, RESET_COLOR, 0)
    cycles = record["groups"]["SET"]["cycle"] + record["groups"]["RESET"]["cycle"]
    resist = record["groups"]["SET"]["resistance"] + record["groups"]["RESET"]["resistance"]
    x0, x1 = span(cycles, floor_at_zero=True)
    y0, y1 = span(resist)
    stamp(graph, record["label"])
    finish(
        graph,
        layer,
        x0,
        x1,
        y0,
        y1,
        "Cycle",
        False,
        ((1, "SET"), (2, "RESET")),
        14,
    )
    print("GRAPH", graph_name, record["label"], f"R {y0:.4g}..{y1:.4g}")
    return graph


def plot_retention(record, book_name, graph_name, folder):
    op = _op()
    drop_named(book_name, folder)
    book = op.new_book("w", record["name"])
    book.name = book_name
    columns = retention_columns(record)
    fill(book[0], columns)
    graph = new_graph(graph_name, record["label"], folder)
    layer = graph[0]
    sheet = book[0]
    add_line(layer, sheet, 1, 0, LINE_COLOR, 0)
    legend = [(1, "Retention")]
    plot_number = 1
    next_col = 2
    if "baseline" in record["groups"] and "post_pulse" in record["groups"]:
        add_line(layer, sheet, next_col + 1, next_col, LINE_COLOR, 0, 1.2)
        plot_number += 1
        next_col += 2
    if "baseline" in record["groups"]:
        add_point(layer, sheet, next_col + 1, next_col, BASELINE_COLOR, 2)
        plot_number += 1
        legend.append((plot_number, "Baseline"))
        next_col += 2
    if "post_pulse" in record["groups"]:
        add_point(layer, sheet, next_col + 1, next_col, POST_COLOR, 3)
        plot_number += 1
        legend.append((plot_number, "After pulse"))
    times = [value for group in record["groups"].values() for value in group["time"]]
    resist = [value for group in record["groups"].values() for value in group["resistance"]]
    x0, x1 = log_span(times)
    y0, y1 = span(resist)
    stamp(graph, record["label"])
    finish(graph, layer, x0, x1, y0, y1, "Time (s)", True, tuple(legend), 14)
    print("GRAPH", graph_name, record["label"], f"t {x0:.4g}..{x1:.4g}", f"R {y0:.4g}..{y1:.4g}")
    return graph


def plot_endurance_overlay(records, book_name, graph_name, folder):
    op = _op()
    drop_named(book_name, folder)
    drop_named(graph_name, folder)
    book = op.new_book("w", "Endurance comparison")
    book.name = book_name
    columns = []
    legend = []
    for index, record in enumerate(records):
        color = FILE_COLORS[index % len(FILE_COLORS)]
        for operation, dash in (("SET", 0), ("RESET", 1)):
            group = record["groups"][operation]
            columns.append((group["cycle"], f"Cycle {record['label']} {operation}", "", "X"))
            columns.append((group["resistance"], f"R {record['label']} {operation}", "Ω", "Y"))
            legend.append((len(legend) + 1, f"{record['label']} {operation}"))
        record["_color"] = color
    fill(book[0], columns)
    graph = new_graph(graph_name, "Endurance comparison", folder)
    layer = graph[0]
    cycles, resist = [], []
    plot_index = 0
    for record in records:
        color = record["_color"]
        for dash in (0, 1):
            add_line(layer, book[0], plot_index * 2 + 1, plot_index * 2, color, dash)
            plot_index += 1
        for operation in ("SET", "RESET"):
            cycles.extend(record["groups"][operation]["cycle"])
            resist.extend(record["groups"][operation]["resistance"])
    x0, x1 = span(cycles, floor_at_zero=True)
    y0, y1 = span(resist)
    stamp(graph, "Endurance")
    finish(graph, layer, x0, x1, y0, y1, "Cycle", False, tuple(legend), 11)
    print("GRAPH", graph_name, "overlay", len(records))
    return graph


def plot_retention_overlay(records, book_name, graph_name, folder):
    op = _op()
    drop_named(book_name, folder)
    drop_named(graph_name, folder)
    book = op.new_book("w", "Retention comparison")
    book.name = book_name
    columns = []
    legend = []
    series = []
    for record in records:
        hold = record["groups"]["retention"]
        columns.append((hold["time"], f"Time {record['label']}", "s", "X"))
        columns.append((hold["resistance"], f"R {record['label']}", "Ω", "Y"))
        bridge_t = record["groups"].get("baseline", {}).get("time", []) + record["groups"].get("post_pulse", {}).get("time", [])
        bridge_r = record["groups"].get("baseline", {}).get("resistance", []) + record["groups"].get("post_pulse", {}).get(
            "resistance", []
        )
        columns.append((bridge_t, f"Time pulse {record['label']}", "s", "X"))
        columns.append((bridge_r, f"R pulse {record['label']}", "Ω", "Y"))
        base = record["groups"].get("baseline")
        post = record["groups"].get("post_pulse")
        columns.append((base["time"] if base else [], f"Time baseline {record['label']}", "s", "X"))
        columns.append((base["resistance"] if base else [], f"R baseline {record['label']}", "Ω", "Y"))
        columns.append((post["time"] if post else [], f"Time after {record['label']}", "s", "X"))
        columns.append((post["resistance"] if post else [], f"R after {record['label']}", "Ω", "Y"))
        legend.append(record["label"])
        series.append((hold["time"], hold["resistance"], bridge_t, bridge_r))
    fill(book[0], columns)
    graph = new_graph(graph_name, "Retention comparison", folder)
    layer = graph[0]
    times, resist = [], []
    entries = []
    plot_number = 0
    for index, record in enumerate(records):
        color = FILE_COLORS[index % len(FILE_COLORS)]
        origin = index * 8
        add_line(layer, book[0], origin + 1, origin, color, 0)
        plot_number += 1
        entries.append((plot_number, legend[index]))
        if series[index][2]:
            add_line(layer, book[0], origin + 3, origin + 2, color, 0, 1.2)
            plot_number += 1
            add_point(layer, book[0], origin + 5, origin + 4, color, 2)
            plot_number += 1
            add_point(layer, book[0], origin + 7, origin + 6, color, 3)
            plot_number += 1
        times.extend(series[index][0])
        times.extend(series[index][2])
        resist.extend(series[index][1])
        resist.extend(series[index][3])
    x0, x1 = log_span(times)
    y0, y1 = span(resist)
    stamp(graph, "Retention")
    finish(graph, layer, x0, x1, y0, y1, "Time (s)", True, tuple(entries), 14)
    print("GRAPH", graph_name, "overlay", len(records))
    return graph


def run(paths, folder, kind):
    """Plot endurance or retention files. Origin is already connected."""
    from origin_session import enter_folder

    if kind not in {"endurance", "retention"}:
        fail("kind must be endurance or retention")
    paths = [Path(item) for item in paths]
    if not paths:
        fail("Add at least one file.")
    records = [read_pulse(path) for path in paths]
    for record in records:
        if record["kind"] != kind:
            fail(f"{record['name']} is a {record['kind']} file")
        print("FILE", record["name"], record["label"])
    active = enter_folder(folder)
    pairs, compare_book, compare_graph = pulse_names([path.stem for path in paths], kind)
    plot = plot_endurance if kind == "endurance" else plot_retention
    for record, (book_name, graph_name) in zip(records, pairs):
        plot(record, book_name, graph_name, active)
    if len(records) >= 2:
        overlay = plot_endurance_overlay if kind == "endurance" else plot_retention_overlay
        overlay(records, compare_book, compare_graph, active)
    print("DONE")
    return records


def main():
    parser = argparse.ArgumentParser(description="Endurance and retention graphs in Origin.")
    parser.add_argument("kind", choices=("endurance", "retention"))
    parser.add_argument("folder")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    from origin_session import connect

    connect("attach")
    run(args.files, args.folder, args.kind)


if __name__ == "__main__":
    sys.exit(main() or 0)
