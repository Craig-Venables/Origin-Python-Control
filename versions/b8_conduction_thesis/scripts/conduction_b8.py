"""Conduction-mechanism pages for D114 B8 sweeps, in the open Origin session.

SCLC, Schottky, Poole-Frenkel and Fowler-Nordheim. A voltage break is
drawn only when the plotted form actually changes, and the note names
that break (V_tr, V_TFL, or the high-field threshold of that mechanism).

Each sweep gets three pages: both polarities, positive only, and
negative only. The single-polarity pages use their own axis scales.
Only the last cycle is drawn. Circles are outward and triangles are
the return. Solid lines fit the outward sweep and dashed lines fit
the return. Every SCLC piece is labelled with its gradient and R2.

    py -3 scripts/conduction_b8.py
    py -3 scripts/conduction_b8.py "C:\\path\\to\\sweep.txt"

Origin must already be open on D114. Books and graphs go to
/D114/B/8/conduction/. The project is not saved.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import originpro as op
from originpro.utils import lt_exec, lt_float, set_lt_str

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fit_conduction_mechanisms import (  # noqa: E402
    cycle_slices,
    high_field_window,
    load_iv,
    polarity_legs,
    sclc_regions,
)

FOLDER = "/D114/B/8/conduction/"
FOLDER_NAME = "conduction"

# Earlier cycles are gray. The last cycle is coloured and is the one fitted.
EARLIER = "#b0b0b0"
POS = "#1f4e79"
POS_BACK = "#5b8fc7"
NEG = "#9c2f2f"
NEG_BACK = "#d07a6a"

DEFAULTS = (
    Path(
        r"C:\Users\craig\OneDrive - The University of Nottingham\Documents"
        r"\Data_folder\D114\B\8\12-FS-1.5v-0.05sv-0.05sd-Py-3.txt"
    ),
    Path(
        r"C:\Users\craig\OneDrive - The University of Nottingham\Documents"
        r"\Data_folder\D114\B\8\4-FS-1.5v-0.05sv-0.05sd-Py-Simple_1.5V-.txt"
    ),
)

MECHS = ("sclc", "sch", "pf", "fn")


def fail(message):
    raise SystemExit(message)


def as_list(values):
    out = []
    for value in values:
        number = float(value)
        out.append(number if math.isfinite(number) else None)
    return out


def coordinates(voltage, current):
    voltage = np.abs(np.asarray(voltage, dtype=float))
    current = np.abs(np.asarray(current, dtype=float))
    ok = (voltage > 0) & (current > 0) & np.isfinite(voltage) & np.isfinite(current)
    voltage = voltage[ok]
    current = current[ok]
    return {
        "sclc": (voltage, current),
        "sch": (np.sqrt(voltage), np.log(current)),
        "pf": (np.sqrt(voltage), np.log(current / voltage)),
        "fn": (1.0 / voltage, np.log(current / voltage ** 2)),
        "v": voltage,
    }


def analyse_leg(voltage, current):
    coords = coordinates(voltage, current)
    voltage = coords["v"]
    sclc = sclc_regions(coords["sclc"][0], coords["sclc"][1])
    windows = {
        "sch": high_field_window(coords["sch"][0], coords["sch"][1], voltage, 0.98, 0.95),
        "pf": high_field_window(coords["pf"][0], coords["pf"][1], voltage, 0.98, 0.95),
        "fn": high_field_window(coords["fn"][0], coords["fn"][1], voltage, 0.90, 0.85),
    }
    fn = windows["fn"]
    if fn.get("ok") and fn["slope"] >= 0:
        fn["ok"] = False
        fn["wrong_sign"] = True
    return {"coords": coords, "sclc": sclc, "windows": windows}


def analyse(path: Path):
    voltage, current = load_iv(path)
    slices = cycle_slices(voltage)
    cycles = []
    for start, stop in slices:
        legs = {
            "+ out": polarity_legs(voltage[start:stop], current[start:stop], True)[0],
            "+ back": polarity_legs(voltage[start:stop], current[start:stop], True)[1],
            "- out": polarity_legs(voltage[start:stop], current[start:stop], False)[0],
            "- back": polarity_legs(voltage[start:stop], current[start:stop], False)[1],
        }
        cycles.append(
            {
                label: None if branch is None else analyse_leg(*branch)
                for label, branch in legs.items()
            }
        )
    return {"path": path, "cycles": len(slices), "legs": cycles}


def sclc_lines(prefix, regions):
    """Each power-law piece: the gradient n and its R²."""
    if not regions:
        return [f"{prefix}  no fit"]
    if len(regions) == 1:
        region = regions[0]
        return [f"{prefix}  n = {region['slope']:.2f}    R² = {region['r2']:.3f}"]
    lower, upper = regions
    kind = upper.get("kind") or "break"
    return [
        f"{prefix}  n = {lower['slope']:.2f}    R² = {lower['r2']:.3f}",
        f"       n = {upper['slope']:.2f}    R² = {upper['r2']:.3f}    {kind} {upper['v_th']:.2f} V",
    ]


def window_lines(prefix, window):
    if window.get("wrong_sign"):
        return [f"{prefix}  not this mechanism"]
    r2 = window.get("r2")
    score = "" if r2 is None or not math.isfinite(r2) else f"R² = {r2:.3f}"
    if not window.get("ok"):
        return [f"{prefix}  not linear    {score}".rstrip()]
    where = "whole sweep" if window["across"] else f"above {window['v_th']:.2f} V"
    weak = "    weak" if window["grade"] == "weak" else ""
    return [f"{prefix}  {score}    {where}{weak}".rstrip()]


def notes_for(record, sign=None):
    """sign is '+' or '-' when the page shows only that polarity.

    Out and back are both listed. SCLC reports every gradient.
    """
    last = record["legs"][-1]
    signs = ("+", "-") if sign is None else (sign,)
    out = {}
    sclc_rows = ["SCLC"]
    for item in signs:
        tag = "" if sign is not None else f"{item} "
        for way in ("out", "back"):
            sclc_rows.extend(sclc_lines(f"{tag}{way}", last[f"{item} {way}"]["sclc"]))
    out["sclc"] = "\n".join(sclc_rows)
    titles = {"sch": "Schottky", "pf": "Poole-Frenkel", "fn": "Fowler-Nordheim"}
    for key, title in titles.items():
        rows = [title]
        for item in signs:
            tag = "" if sign is not None else f"{item} "
            for way in ("out", "back"):
                rows.extend(window_lines(f"{tag}{way}", last[f"{item} {way}"]["windows"][key]))
        out[key] = "\n".join(rows)
    return out


def names_for(path: Path):
    """Book, combined graph, positive graph, negative graph, title."""
    stem = path.name
    if stem.startswith("12-"):
        return "b8iv12", "gB8iv12", "gB8p12", "gB8n12", "B8 sweep 12"
    if stem.startswith("4-"):
        return "b8iv04", "gB8iv04", "gB8p04", "gB8n04", "B8 sweep 4"
    token = "".join(ch for ch in path.stem if ch.isalnum())[:5] or "sweep"
    return "b8" + token[:4], "gB8" + token[:4], "gP" + token[:5], "gN" + token[:5], path.stem[:24]


def enter_folder():
    op.attach()
    op.set_show(True)
    op.pe.cd("/D114/B/8/")
    op.pe.mkdir(FOLDER_NAME, True)
    op.pe.cd(FOLDER)
    active = op.pe.active_folder().path
    print("FOLDER", active)
    if not active.lower().rstrip("/").endswith("/b/8/conduction"):
        fail(f"refusing to write, active folder is {active!r}")


def drop_named(name):
    located = op.pe.search(name, 0) or ""
    if not located:
        return
    if FOLDER_NAME not in located.lower() or "/b/8/" not in located.lower():
        fail(f"{name} already exists in {located}")
    page = op.find_book("w", name) or op.find_graph(name)
    if page is not None:
        page.obj.Destroy()


def put(sheet, column, data, long_name, units=""):
    sheet.from_list(column, as_list(data), lname=long_name, units=units)
    return column


def mark_x(sheet, column):
    sheet.obj[column].SetType(3)


def add_pair(sheet, column, x_data, y_data, x_name, y_name, x_units, ids, key):
    put(sheet, column, x_data, x_name, x_units)
    put(sheet, column + 1, y_data, y_name)
    mark_x(sheet, column)
    ids[key] = (column, column + 1)
    return column + 2


def write_book(record, book_name):
    drop_named(book_name)
    book = op.new_book("w", record["path"].name)
    book.name = book_name
    sheet = book[0]
    sheet.name = "Curves"
    column = 0
    ids = {}
    last_index = len(record["legs"]) - 1
    for index, cycle in enumerate(record["legs"]):
        for label, leg in cycle.items():
            if leg is None:
                continue
            token = f"c{index} {label}"
            for mech, (x_data, y_data) in (
                ("sclc", leg["coords"]["sclc"]),
                ("sch", leg["coords"]["sch"]),
                ("pf", leg["coords"]["pf"]),
                ("fn", leg["coords"]["fn"]),
            ):
                units = "V" if mech == "sclc" else ""
                column = add_pair(
                    sheet,
                    column,
                    x_data,
                    y_data,
                    f"{mech} x {token}",
                    f"{mech} y {token}",
                    units,
                    ids,
                    f"{mech} {token}",
                )
            if index != last_index:
                continue
            pol = "pos" if label.startswith("+") else "neg"
            way = "out" if label.endswith("out") else "back"
            for region_index, region in enumerate(leg["sclc"]):
                column = add_pair(
                    sheet,
                    column,
                    region["x"],
                    region["y"],
                    f"sclc fit x {pol} {way} {region_index}",
                    f"sclc fit y {pol} {way} {region_index}",
                    "V",
                    ids,
                    f"sclc fit {pol} {way} {region_index}",
                )
            for mech in ("sch", "pf", "fn"):
                window = leg["windows"][mech]
                if not window.get("ok"):
                    continue
                column = add_pair(
                    sheet,
                    column,
                    window["x"],
                    window["y"],
                    f"{mech} fit x {pol} {way}",
                    f"{mech} fit y {pol} {way}",
                    "",
                    ids,
                    f"{mech} fit {pol} {way}",
                )
    write_table(book, record)
    return book, sheet, ids


def add_thresholds(sheet, column, ids, sign, leg):
    """A two-point line at each interior threshold. Y is filled later."""
    return column


def write_table(book, record):
    sheet = book.add_sheet("Thresholds")
    last = record["legs"][-1]
    rows = []
    for sign in ("+", "-"):
        for way in ("out", "back"):
            leg = last[f"{sign} {way}"]
            regions = leg["sclc"]
            leg_name = f"{sign} {way}"
            if len(regions) == 1:
                region = regions[0]
                rows.append(
                    (
                        "SCLC",
                        leg_name,
                        "none",
                        region["name"],
                        f"{region['slope']:.3f}",
                        f"{region['r2']:.3f}",
                    )
                )
            else:
                lower, upper = regions
                rows.append(
                    (
                        "SCLC",
                        leg_name,
                        f"{upper['kind']} = {upper['v_th']:.3f} V",
                        f"below {lower['name']}, above {upper['name']}",
                        f"{lower['slope']:.3f} / {upper['slope']:.3f}",
                        f"{lower['r2']:.3f} / {upper['r2']:.3f}",
                    )
                )
            for mech, title in (
                ("sch", "Schottky"),
                ("pf", "Poole-Frenkel"),
                ("fn", "Fowler-Nordheim"),
            ):
                window = leg["windows"][mech]
                if window.get("wrong_sign"):
                    where = "not this mechanism, slope is positive"
                elif not window.get("ok"):
                    where = "not linear"
                elif window["across"]:
                    where = "linear across the sweep"
                else:
                    where = f"above {window['v_th']:.3f} V"
                r2 = window.get("r2")
                rows.append(
                    (
                        title,
                        leg_name,
                        where,
                        title,
                        "" if not math.isfinite(window.get("slope", float("nan"))) else f"{window['slope']:.4g}",
                        "" if r2 is None or not math.isfinite(r2) else f"{r2:.3f}",
                    )
                )
    headers = ("Mechanism", "Leg", "Threshold", "What it is", "Slope or n", "R2")
    for col, header in enumerate(headers):
        texts = [row[col] for row in rows]
        sheet.from_list(col, [0] * len(texts), lname=header)
        for row_index, text in enumerate(texts):
            safe = text.replace('"', "'")
            sheet.obj.LT_execute(f'col({col + 1})[{row_index + 1}]$ = "{safe}";')
    print("TABLE", record["path"].name)
    for row in rows:
        print("   ", " | ".join(row))


def hide_legend():
    if math.isfinite(lt_float("legend.x")):
        lt_exec("legend.show = 0")


def style_symbol(plot, color, kind, interior, size):
    plot.color = color
    plot.symbol_kind = kind
    plot.symbol_size = size
    plot.symbol_interior = interior


def style_line(plot, color, width, dash=0):
    plot.color = color
    plot.set_cmd(f"-d {dash}", f"-w {width}")


def add_curve(layer, sheet, ids, key, kind):
    pair = ids.get(key)
    if pair is None:
        return None
    return layer.add_plot(sheet, coly=pair[1], colx=pair[0], type=kind)


def set_limits(graph, index, x0, x1, y0, y1):
    graph.obj.LT_execute(f"page.active = {index}")
    graph.obj.LT_execute(f"layer.x.from = {float(x0):.8g}")
    graph.obj.LT_execute(f"layer.x.to = {float(x1):.8g}")
    graph.obj.LT_execute(f"layer.y.from = {float(y0):.8g}")
    graph.obj.LT_execute(f"layer.y.to = {float(y1):.8g}")


def padded(values, log, headroom):
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if log:
        vals = vals[vals > 0]
    lo, hi = float(np.min(vals)), float(np.max(vals))
    if lo == hi:
        lo, hi = lo * 0.8, hi * 1.2
    if log:
        left, right = math.log10(lo), math.log10(hi)
        span = max(right - left, 0.3)
        return 10 ** (left - 0.06 * span), 10 ** (right + headroom * span)
    span = max(hi - lo, 1e-9)
    return lo - 0.06 * span, hi + headroom * span


def fraction(lo, hi, frac, log):
    if log:
        left, right = math.log10(lo), math.log10(hi)
        return 10 ** (left + frac * (right - left))
    return lo + frac * (hi - lo)


def collect(record, mech, include_fits, sign=None):
    """Axis limits from the last cycle only. Earlier cycles are not drawn."""
    xs, ys = [], []
    last = record["legs"][-1]
    for label, leg in last.items():
        if leg is None or (sign is not None and not label.startswith(sign)):
            continue
        x_data, y_data = leg["coords"][mech]
        xs.append(x_data)
        ys.append(y_data)
    if include_fits:
        signs = ("+", "-") if sign is None else (sign,)
        for item in signs:
            for way in ("out", "back"):
                leg = last[f"{item} {way}"]
                if mech == "sclc":
                    for region in leg["sclc"]:
                        xs.append(region["x"])
                        ys.append(region["y"])
                else:
                    window = leg["windows"][mech]
                    if window.get("ok"):
                        xs.append(window["x"])
                        ys.append(window["y"])
    return np.concatenate(xs), np.concatenate(ys)


def place(graph, index, left, top, width, height):
    graph.obj.LT_execute(f"page.active = {index}")
    graph.obj.LT_execute("layer -u 1")
    graph.obj.LT_execute(f"layer {width:.3f} {height:.3f} {left:.3f} {top:.3f}")


def write_note(graph, name, text, x_pos, y_pos, size=9):
    set_lt_str("py_note", text)
    graph.obj.LT_execute(f"label -r {name}")
    graph.obj.LT_execute(f'label -s -n {name} "fit";')
    graph.obj.LT_execute(f"{name}.text$ = py_note$")
    graph.obj.LT_execute(
        f"{name}.attach = 2; {name}.fsize = {size}; {name}.background = 1; "
        f"{name}.x = {x_pos:.8g}; {name}.y = {y_pos:.8g};"
    )


def place_gradients(graph, record, sign, x0, x1, y0, y1):
    """Put each SCLC gradient on its own fit segment."""
    last = record["legs"][-1]
    items = ("+", "-") if sign is None else (sign,)
    graph.obj.LT_execute("page.active = 1")
    count = 0
    for item in items:
        for way in ("out", "back"):
            leg = last[f"{item} {way}"]
            if leg is None:
                continue
            for region in leg["sclc"]:
                xs = region["x"]
                ys = region["y"]
                mid = len(xs) // 2
                x_pos = float(xs[mid])
                y_pos = float(ys[mid]) * (2.4 if way == "out" else 0.42)
                if not (x0 < x_pos < x1 and y0 < y_pos < y1):
                    continue
                name = f"g{count}"
                count += 1
                label = f"n = {region['slope']:.2f}"
                if sign is None:
                    label = f"{item} {way}  {label}"
                set_lt_str("py_note", label)
                graph.obj.LT_execute(f"label -r {name}")
                graph.obj.LT_execute(f'label -s -n {name} "n";')
                graph.obj.LT_execute(f"{name}.text$ = py_note$")
                graph.obj.LT_execute(
                    f"{name}.attach = 2; {name}.fsize = 10; {name}.background = 1; "
                    f"{name}.x = {x_pos:.8g}; {name}.y = {y_pos:.8g};"
                )


def draw_panel(graph, layer_index, sheet, ids, record, mech, sign=None):
    graph.obj.LT_execute(f"page.active = {layer_index}")
    layer = graph[layer_index - 1]
    last = len(record["legs"]) - 1
    for label, color, kind, interior in (
        ("+ out", POS, 2, 1),
        ("+ back", POS_BACK, 3, 2),
        ("- out", NEG, 2, 1),
        ("- back", NEG_BACK, 3, 2),
    ):
        if sign is not None and not label.startswith(sign):
            continue
        plot = add_curve(layer, sheet, ids, f"{mech} c{last} {label}", "s")
        if plot is not None:
            style_symbol(plot, color, kind, interior, 8)
    fit_signs = (("pos", POS), ("neg", NEG))
    if sign == "+":
        fit_signs = (("pos", POS),)
    elif sign == "-":
        fit_signs = (("neg", NEG),)
    for token, color in fit_signs:
        for way, dash, width in (("out", 0, 2.4), ("back", 1, 2.0)):
            if mech == "sclc":
                for region_index in (0, 1, 2):
                    plot = add_curve(
                        layer, sheet, ids, f"sclc fit {token} {way} {region_index}", "l"
                    )
                    if plot is not None:
                        style_line(plot, color, width, dash)
            else:
                plot = add_curve(layer, sheet, ids, f"{mech} fit {token} {way}", "l")
                if plot is not None:
                    style_line(plot, color, width, dash)
    logx = mech == "sclc"
    logy = mech == "sclc"
    if logx:
        layer.xscale = "log10"
        layer.obj.LT_execute("layer.x.inc = 1")
    if logy:
        layer.yscale = "log10"
        layer.obj.LT_execute("layer.y.inc = 1")
    x_values, y_values = collect(record, mech, include_fits=True, sign=sign)
    headroom = 0.95 if mech == "sclc" else 0.55
    x0, x1 = padded(x_values, logx, 0.08)
    y0, y1 = padded(y_values, logy, headroom)
    titles = {
        "sclc": ("|Voltage| (V)", "|Current| (A)"),
        "sch": ("sqrt(|V|)", "ln(|I|)"),
        "pf": ("sqrt(|V|)", "ln(|I| / |V|)"),
        "fn": ("1/|V|", "ln(|I| / V^2)"),
    }
    layer.axis("x").title = titles[mech][0]
    layer.axis("y").title = titles[mech][1]
    for axis in ("x", "y"):
        layer.obj.LT_execute(f"layer.{axis}.label.pt = 14")
        layer.obj.LT_execute(f"layer.{axis}.ticklabel.pt = 11")
        layer.obj.LT_execute(f"layer.{axis}.ticks.dir = 2")
    hide_legend()
    set_limits(graph, layer_index, x0, x1, y0, y1)
    # The anchor sits just above the data. The text grows upward into the headroom.
    x_frac = 0.48 if mech == "fn" else 0.12
    y_frac = 0.78 if mech == "sclc" else 0.64
    write_note(
        graph,
        f"n{layer_index}",
        notes_for(record, sign)[mech],
        fraction(x0, x1, x_frac, logx),
        fraction(y0, y1, y_frac, logy),
        8 if mech == "sclc" and sign is None else 9,
    )
    # On the both-polarity page the corner note already lists every gradient.
    # Labels on the lines only fit cleanly when one polarity is drawn.
    if mech == "sclc" and sign is not None:
        place_gradients(graph, record, sign, x0, x1, y0, y1)
    return x0, x1, y0, y1


def add_threshold_lines(graph, sheet, ids, record, limits, sign=None, tag="all"):
    """Vertical lines at interior thresholds, one colour per polarity.

    Drawn after the axes exist so the line crosses the panel. tag keeps
    the combined page and the polarity pages from sharing one line.
    """
    last = record["legs"][-1]
    column = sheet.cols
    specs = []
    marks = (("+", POS), ("-", NEG))
    if sign is not None:
        marks = tuple(item for item in marks if item[0] == sign)
    for mech, (x0, x1, y0, y1) in limits.items():
        for item, color in marks:
            leg = last[f"{item} out"]
            x_th = None
            if mech == "sclc" and len(leg["sclc"]) == 2:
                x_th = leg["sclc"][1]["v_th"]
            elif mech != "sclc":
                window = leg["windows"][mech]
                if window.get("ok") and not window["across"]:
                    if mech == "sch" or mech == "pf":
                        x_th = math.sqrt(window["v_th"])
                    else:
                        x_th = 1.0 / window["v_th"]
            if x_th is None or not (x0 < x_th < x1):
                continue
            key = f"mark {tag} {mech} {item}"
            column = add_pair(
                sheet,
                column,
                [x_th, x_th],
                [y0, y1],
                f"{key} x",
                f"{key} y",
                "",
                ids,
                key,
            )
            specs.append((mech, key, color))
    layer_of = {"sclc": 1, "sch": 2, "pf": 3, "fn": 4}
    for mech, key, color in specs:
        graph.obj.LT_execute(f"page.active = {layer_of[mech]}")
        plot = add_curve(graph[layer_of[mech] - 1], sheet, ids, key, "l")
        if plot is not None:
            style_line(plot, color, 1.0, 2)


def build_graph(record, graph_name, title, sheet, ids, sign=None):
    drop_named(graph_name)
    side = {None: "both", "+": "positive", "-": "negative"}[sign]
    graph = op.new_graph(f"{title}, {side}")
    graph.name = graph_name
    graph.obj.LT_execute("page.lock = 0")
    graph.obj.LT_execute("page.width = 7200")
    for _ in range(3):
        graph.add_layer()
    boxes = (
        (8.0, 12.0, 40.0, 36.0),
        (54.0, 12.0, 40.0, 36.0),
        (8.0, 54.0, 40.0, 38.0),
        (54.0, 54.0, 40.0, 38.0),
    )
    for index, box in enumerate(boxes):
        place(graph, index + 1, *box)
    limits = {}
    for index, mech in enumerate(MECHS):
        limits[mech] = draw_panel(graph, index + 1, sheet, ids, record, mech, sign)
    tag = {None: "all", "+": "pos", "-": "neg"}[sign]
    add_threshold_lines(graph, sheet, ids, record, limits, sign, tag)
    # Limits again, after the threshold lines, so they stay put.
    for index, mech in enumerate(MECHS):
        set_limits(graph, index + 1, *limits[mech])
        graph.obj.LT_execute(f"page.active = {index + 1}")
        hide_legend()
    graph.obj.LT_execute("page.active = 1")
    caption = f"{title}, {side}    circles out, triangles back    solid out, dashed back"
    set_lt_str("py_note", caption)
    graph.obj.LT_execute("label -r caption")
    graph.obj.LT_execute('label -s -n caption "fit";')
    graph.obj.LT_execute("caption.text$ = py_note$")
    # The page is in its own units (about 7200 by 5100), not percent.
    lt_exec("double eis_w = page.width")
    lt_exec("double eis_h = page.height")
    width = lt_float("eis_w")
    height = lt_float("eis_h")
    if not (math.isfinite(width) and math.isfinite(height) and height > 100):
        width, height = 7200.0, 5104.0
    graph.obj.LT_execute(
        "caption.attach = 0; caption.fsize = 16; caption.color = 1; "
        f"caption.x = {0.50 * width:.4f}; caption.y = {0.105 * height:.4f};"
    )
    graph.activate()
    lt_exec(f"win -a {graph_name}")
    lt_exec("win -z")
    print("GRAPH", graph.name, graph.lname, "folder", op.pe.search(graph.name, 0))
    return graph


def main():
    parser = argparse.ArgumentParser(description="B8 conduction pages in Origin.")
    parser.add_argument("files", nargs="*", help="IV text files. Omit for the two B8 sweeps.")
    args = parser.parse_args()
    paths = [Path(item) for item in args.files] or list(DEFAULTS)
    records = []
    for path in paths:
        if not path.exists():
            fail(f"missing {path}")
        record = analyse(path)
        print("FILE", path.name, "cycles", record["cycles"])
        for mech, text in notes_for(record).items():
            print(f"--- {mech}")
            print(text)
        records.append(record)
    enter_folder()
    for record in records:
        book_name, combined, positive, negative, title = names_for(record["path"])
        book, sheet, ids = write_book(record, book_name)
        print("BOOK", book.name, "cols", sheet.cols, "rows", sheet.rows)
        build_graph(record, combined, title, sheet, ids, None)
        build_graph(record, positive, title, sheet, ids, "+")
        build_graph(record, negative, title, sheet, ids, "-")
    print("DONE")


if __name__ == "__main__":
    main()
