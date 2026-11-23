"""Fit the D114 B8 pristine spectrum in the open Origin session.

Rs in series with Rp parallel to a constant-phase element. The fit is
Origin's NLFit, not a Python optimizer. Python only chooses the starting
values and draws the figure.

Origin must already be open on D114. The books and the graph are written
to /D114/B/8/Cf/cf_cursor/ and the project is not saved.

    py -3 scripts/fit_pristine_eis.py
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
import originpro as op
from originpro.utils import get_lt_str, lt_exec, lt_float, set_lt_str
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
FDF = ROOT / "fitfunc" / "RsRpCPE.fdf"
DATA = Path(
    r"C:\Users\craig\OneDrive - The University of Nottingham\Documents"
    r"\Data_folder\D114\B\8\Solartron_1260"
    r"\1-device_only_Pristine_20260811_113130"
    r"\origin_data\D114_Pristine_VBp0.000.csv"
)
FUNC = "RsRpCPE"
BOOK = "cfPrist"
GRAPH = "gCfPrist"
FOLDER_NAME = "cf_cursor"

DATA_COLOR = "#1f4e79"
FIT_COLOR = "#c45c26"
GUIDE_COLOR = "#b7b7b7"


def fail(message):
    raise SystemExit(message)


def load_spectrum(path: Path):
    if not path.exists():
        fail(f"missing {path}")
    freq, zreal, zimag, phase, zmag = [], [], [], [], []
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            f = float(row["Frequency_Hz"])
            zr = float(row["Z_Real_Ohms"])
            zi = float(row["Z_Imag_Ohms"])
            mag = float(row["Z_Magnitude_Ohms"])
            ph = float(row["Phase_deg"])
            if min(f, mag) <= 0 or not all(map(math.isfinite, (f, zr, zi, mag, ph))):
                continue
            freq.append(f)
            zreal.append(zr)
            zimag.append(zi)
            phase.append(ph)
            zmag.append(mag)
    if len(freq) < 10:
        fail(f"{path.name} has {len(freq)} usable rows")
    return (
        np.asarray(freq),
        np.asarray(zreal),
        np.asarray(zimag),
        np.asarray(phase),
        np.asarray(zmag),
    )


def z_model(freq, rs, rp, q, alpha):
    """Z' and -Z''. omega = 2 pi f, Zcpe = 1 / (Q (j omega)^alpha)."""
    omega = 2 * math.pi * freq
    qw = q * np.power(omega, alpha)
    angle = alpha * math.pi / 2
    real_y = 1.0 / rp + qw * math.cos(angle)
    imag_y = qw * math.sin(angle)
    denom = real_y * real_y + imag_y * imag_y
    return rs + real_y / denom, imag_y / denom


def modulus_residual(packed, freq, zreal, zimag):
    rs, rp, log_q, alpha = packed
    model_r, model_i = z_model(freq, rs, rp, 10 ** log_q, alpha)
    scale = np.hypot(zreal, zimag)
    return np.concatenate(((zreal - model_r) / scale, (zimag - model_i) / scale))


def starting_point(freq, zreal, zimag):
    high = int(np.argmax(freq))
    rs0 = max(float(zreal[high]), 1.0)
    rp0 = max(float(2 * np.max(zimag)), float(np.max(zreal) - rs0), 1e3)
    peak = int(np.argmax(zimag))
    cap = 1.0 / (2 * math.pi * float(freq[peak]) * rp0)
    cap = min(max(cap, 1e-13), 1e-8)
    return np.array([rs0, rp0, math.log10(cap), 0.95])


def prefit(freq, zreal, zimag):
    """Modulus-weighted start for NLFit. Origin does the reported fit."""
    guess = starting_point(freq, zreal, zimag)
    lower = np.array([1.0, 1.0, -15.0, 0.4])
    upper = np.array([1e6, 1e9, -6.0, 1.0])
    # A single outlier can push the heuristic past the box. The start has to
    # lie inside it or least_squares refuses to run.
    guess = np.minimum(np.maximum(np.asarray(guess, dtype=float), lower), upper)
    fitted = least_squares(
        modulus_residual,
        guess,
        args=(freq, zreal, zimag),
        bounds=(lower, upper),
        xtol=1e-12,
        ftol=1e-12,
        max_nfev=400,
    )
    rs, rp, log_q, alpha = (float(v) for v in fitted.x)
    q = 10 ** log_q
    cost = float(np.sum(modulus_residual(fitted.x, freq, zreal, zimag) ** 2))
    print(
        "PYTHON START",
        f"Rs={rs:.6g}",
        f"Rp={rp:.6g}",
        f"Q={q:.6g}",
        f"n={alpha:.6g}",
        f"ss={cost:.6g}",
        f"ok={fitted.success}",
    )
    return rs, rp, q, alpha


def scores(freq, zreal, zimag, rs, rp, q, alpha):
    model_r, model_i = z_model(freq, rs, rp, q, alpha)
    scale = np.hypot(zreal, zimag)
    residual = np.concatenate(((zreal - model_r) / scale, (zimag - model_i) / scale))
    measured = np.concatenate((zreal / scale, zimag / scale))
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((measured - np.mean(measured)) ** 2))
    count = residual.size
    return {
        "ss": ss_res,
        "chi_red": ss_res / (count - 4),
        "r2": 1.0 - ss_res / ss_tot,
        "n_obs": count,
        "model_r": model_r,
        "model_i": model_i,
    }


def ceff(rp, q, alpha):
    tau = (rp * q) ** (1.0 / alpha)
    return tau / rp, tau, 1.0 / (2 * math.pi * tau)


def enter_folder():
    op.attach()
    op.set_show(True)
    op.pe.cd("/D114/B/8/Cf/cf_cursor/")
    active = op.pe.active_folder().path
    if not active.replace("\\", "/").rstrip("/").lower().endswith(FOLDER_NAME):
        fail(f"refusing to write, active folder is {active!r}")
    print("FOLDER", active)
    return active


def drop_named(name):
    located = op.pe.search(name, 0) or ""
    if not located:
        return
    if FOLDER_NAME not in located.replace("\\", "/").lower():
        fail(f"{name} already exists in {located}")
    page = op.find_book("w", name)
    if page is None:
        page = op.find_graph(name)
    if page is not None:
        page.obj.Destroy()


def page_names():
    return {page.name for page in op.pe.active_folder().pages()}


def drop_new(before, keep):
    for page in list(op.pe.active_folder().pages()):
        if page.name in before or page.name in keep:
            continue
        print("DROP", page.name)
        page.obj.Destroy()


def install_function():
    posix = FDF.as_posix()
    lt_exec(f'run.section(dofile, OnUnInstallFDF, "{posix}")')
    lt_exec(f'run.section(dofile, OnInstallFDF, "{posix}")')
    xml = get_lt_str(f'GetFDFAsXML("{FUNC}")$') or ""
    if FUNC not in xml or "QpF" not in xml:
        fail(f"could not install {FUNC}")
    print("FUNCTION", FUNC, "xml", len(xml))


def as_list(values):
    return [float(value) for value in values]


def fill(sheet, columns):
    for index, (values, long_name, units, axis) in enumerate(columns):
        sheet.from_list(index, as_list(values), lname=long_name, units=units, axis=axis)


def run_fit(sheet, rs, rp, q, alpha):
    """NLFit session. Parameters are read after nlfit and before nlend.

    Origin stores the standard errors on the same tree as e_Rs, e_Rp,
    e_QpF and e_alpha. nlend writes the report and clears that session.
    """
    sheet.activate()
    tree = "eisfit"
    lt_exec(f"del -vt {tree}")
    command = f"nlbeginr {sheet.lt_range()}!(1,2,3,4) {FUNC} {tree}"
    if not lt_exec(command):
        fail(f"nlbegin failed: {command}")
    lt_exec(f"{tree}.Rs = {float(rs)}")
    lt_exec(f"{tree}.Rp = {float(rp)}")
    lt_exec(f"{tree}.QpF = {float(q) * 1e12}")
    lt_exec(f"{tree}.alpha = {float(alpha)}")
    print(
        "ORIGIN START",
        lt_float(f"{tree}.Rs"),
        lt_float(f"{tree}.Rp"),
        lt_float(f"{tree}.QpF"),
        lt_float(f"{tree}.alpha"),
    )
    if not lt_exec("nlfit"):
        fail("nlfit failed")
    fitted = {
        name: lt_float(f"{tree}.{name}")
        for name in (
            "Rs",
            "Rp",
            "QpF",
            "alpha",
            "e_Rs",
            "e_Rp",
            "e_QpF",
            "e_alpha",
            "chisqr",
            "niter",
        )
    }
    print(
        "ORIGIN END",
        f"Rs={fitted['Rs']:.6g}",
        f"Rp={fitted['Rp']:.6g}",
        f"QpF={fitted['QpF']:.6g}",
        f"n={fitted['alpha']:.6g}",
        f"iter={fitted['niter']}",
    )
    held = lt_float("@NLFS")
    lt_exec("@NLFS = 0")
    if not lt_exec("nlend 1"):
        fail("nlend failed")
    lt_exec(f"@NLFS = {held}")
    report = get_lt_str("__REPORT")
    curve = get_lt_str("__FITCURVE")
    print("REPORT", report)
    print("CURVE", curve)
    return fitted, report, curve


def walk(node, prefix=""):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            found.extend(walk(value, child))
    else:
        found.append((prefix, node))
    return found


def param_from(tree, name):
    """Match a parameter by path segment, so 'Rs' does not hit 'Parameters'."""
    value = error = None
    wanted = name.lower()
    for key, item in walk(tree):
        parts = [part.lower() for part in key.split(".")]
        if wanted not in parts:
            continue
        leaf = parts[-1]
        number = float(item)
        if leaf == wanted and value is None:
            value = number
        elif leaf in {"value", "param"} and value is None:
            value = number
        elif "error" in leaf or leaf in {"stderr", "se"}:
            if error is None:
                error = number
    return value, error


def check_synthetic():
    freq = np.logspace(0, 6, 30)
    rs, rp, q, alpha = 8000.0, 2.5e7, 1.8e-11, 0.93
    zreal, zimag = z_model(freq, rs, rp, q, alpha)
    zmag = np.hypot(zreal, zimag)
    drop_named("cfSyn")
    before = page_names()
    book = op.new_book("w", "synthetic RsRpCPE")
    book.name = "cfSyn"
    sheet = book[0]
    fill(
        sheet,
        (
            (freq, "f", "Hz", "X"),
            (zmag, "zm", "Ohm", "X"),
            (zreal / zmag, "yr", "", "Y"),
            (zimag / zmag, "yi", "", "Y"),
        ),
    )
    fitted, _, _ = run_fit(sheet, 5000.0, 1.2e7, 5e-11, 0.8)
    drop_new(before, set())
    drop_named("cfSyn")
    got_rs = fitted["Rs"]
    got_rp = fitted["Rp"]
    got_q = fitted["QpF"]
    got_n = fitted["alpha"]
    if not all(map(math.isfinite, (got_rs, got_rp, got_q, got_n))):
        fail(f"synthetic fit did not return parameters: {fitted}")
    checks = {
        "Rs": abs(got_rs - rs) / rs,
        "Rp": abs(got_rp - rp) / rp,
        "Q": abs(got_q * 1e-12 - q) / q,
        "n": abs(got_n - alpha),
    }
    print("SYN ERROR", checks)
    if max(checks["Rs"], checks["Rp"], checks["Q"]) > 0.02 or checks["n"] > 0.01:
        fail(f"synthetic recovery failed: {checks}")


def text_column(sheet, index, header, rows):
    sheet.from_list(index, [0] * len(rows), lname=header, axis="L")
    for row, text in enumerate(rows, start=1):
        safe = text.replace('"', "'")
        sheet.obj.LT_execute(f'col({index + 1})[{row}]$ = "{safe}";')


def superscript(exp):
    table = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(exp).translate(table)


def scientific(value):
    if not math.isfinite(value) or value == 0:
        return "0"
    exp = int(math.floor(math.log10(abs(value))))
    mant = value / 10 ** exp
    return f"{mant:.3f}×10{superscript(exp)}"


def prefixed(value, unit):
    prefixes = (
        (1e6, "M"),
        (1e3, "k"),
        (1.0, ""),
        (1e-3, "m"),
        (1e-6, "µ"),
        (1e-9, "n"),
        (1e-12, "p"),
    )
    scale, prefix = 1.0, ""
    for threshold, name in prefixes:
        if abs(value) >= threshold:
            scale, prefix = threshold, name
            break
    number = value / scale
    digits = 3 if abs(number) >= 100 else 2 if abs(number) >= 10 else 3
    return f"{number:.{digits}f} {prefix}{unit}".replace("  ", " ")


def same_unit(value, error, unit):
    """Value and standard error in one prefix, so 6.83 ± 0.37 kΩ."""
    prefixes = (
        (1e6, "M"),
        (1e3, "k"),
        (1.0, ""),
        (1e-3, "m"),
        (1e-6, "µ"),
        (1e-9, "n"),
        (1e-12, "p"),
    )
    scale, prefix = 1.0, ""
    for threshold, name in prefixes:
        if abs(value) >= threshold:
            scale, prefix = threshold, name
            break
    shown = value / scale
    usable = error is not None and math.isfinite(error) and 0 < error < abs(value)
    if not usable:
        return f"{shown:.4g} {prefix}{unit}".strip()
    err = error / scale
    decimals = max(0, -int(math.floor(math.log10(err))) + 1)
    return f"{shown:.{decimals}f} ± {err:.{decimals}f} {prefix}{unit}".strip()


def sci_pm(value, error):
    exp = int(math.floor(math.log10(abs(value))))
    mant = value / 10 ** exp
    usable = error is not None and math.isfinite(error) and error > 0
    if not usable:
        return f"{mant:.3f}×10{superscript(exp)}"
    err = error / 10 ** exp
    return f"({mant:.3f} ± {err:.3f})×10{superscript(exp)}"


def write_parameters(book, rows):
    sheet = book.add_sheet("Parameters")
    text_column(sheet, 0, "Parameter", [row[0] for row in rows])
    text_column(sheet, 1, "Value", [row[1] for row in rows])
    text_column(sheet, 2, "Meaning", [row[2] for row in rows])
    return sheet


def page_size(graph):
    graph.activate()
    graph.obj.LT_execute("double py_w = page.width")
    graph.obj.LT_execute("double py_h = page.height")
    return lt_float("py_w"), lt_float("py_h")


def place(graph, index, left, top, width, height):
    graph.obj.LT_execute(f"page.active = {index + 1}")
    graph.obj.LT_execute("layer -u 1")
    graph.obj.LT_execute(f"layer {width:.3f} {height:.3f} {left:.3f} {top:.3f}")


def style_frame(layer):
    layer.obj.LT_execute("layer.x.label.pt = 20")
    layer.obj.LT_execute("layer.y.label.pt = 20")
    layer.obj.LT_execute("layer.x.ticklabel.pt = 16")
    layer.obj.LT_execute("layer.y.ticklabel.pt = 16")
    layer.obj.LT_execute("layer.x.ticks.dir = 2")
    layer.obj.LT_execute("layer.y.ticks.dir = 2")


def add_scatter(layer, sheet, y_index, x_index):
    plot = layer.add_plot(sheet, coly=y_index, colx=x_index, type="s")
    plot.color = DATA_COLOR
    plot.symbol_kind = 2
    plot.symbol_size = 8
    plot.symbol_interior = 2
    return plot


def add_line(layer, sheet, y_index, x_index, color, width):
    plot = layer.add_plot(sheet, coly=y_index, colx=x_index, type="l")
    plot.color = color
    plot.set_cmd(f"-w {width}")
    return plot


def write_legend(layer, entries):
    text = "\n".join(rf"\l({index}) {name}" for index, name in entries)
    set_lt_str("py_leg", text)
    layer.obj.LT_execute("legend -r")
    layer.obj.LT_execute("legend.text$ = py_leg$")
    layer.obj.LT_execute("legend.fsize = 14;")


def equal_limits(x0, x1, y0, y1, aspect):
    """Expand the shorter span so one data unit has the same length on both axes."""
    dx = x1 - x0
    dy = y1 - y0
    if dx <= 0 or dy <= 0:
        fail(f"empty Nyquist limits x {x0}..{x1} y {y0}..{y1}")
    if dx / dy < aspect:
        extra = aspect * dy - dx
        x0 -= extra * 0.08
        x1 += extra * 0.92
    else:
        extra = dx / aspect - dy
        y0 -= extra * 0.18
        y1 += extra * 0.82
    return x0, x1, y0, y1


def build_graph(sheet, note):
    """Spectrum sheet columns, in order:

    0 f data, 1 Z', 2 phase, 3 Z' MΩ, 4 −Z'' MΩ, 5 |Z|,
    6 f fit, 7 Z' fit MΩ, 8 −Z'' fit MΩ, 9 |Z| fit, 10 phase fit,
    11 guide x, 12 guide y.
    """
    drop_named(GRAPH)
    graph = op.new_graph("D114 B8 pristine, 0 V")
    graph.name = GRAPH
    width, height = page_size(graph)
    print("PAGE", width, height)
    if height >= width:
        graph.obj.LT_execute(f"page.width = {height * 1.65:.4f}")
        width, height = page_size(graph)
        print("PAGE", width, height)
    boxes = ((5, 6, 50, 58), (68, 6, 28, 42), (68, 54, 28, 40))
    aspect = (boxes[0][2] / 100 * width) / (boxes[0][3] / 100 * height)
    x = np.asarray(sheet.to_list(3), dtype=float)
    y = np.asarray(sheet.to_list(4), dtype=float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    x0, x1 = float(np.min(x)), float(np.max(x))
    y0, y1 = min(0.0, float(np.min(y))), float(np.max(y))
    span = max(x1 - x0, y1 - y0)
    pad = 0.04 * span
    x0, x1, y0, y1 = equal_limits(x0 - pad, x1 + pad, y0 - pad, y1 + pad, aspect)
    sheet.from_list(11, [x0, x1], lname="guide x", units="MΩ", axis="X")
    sheet.from_list(12, [0.0, 0.0], lname="guide y", units="MΩ", axis="Y")

    layer = graph[0]
    add_line(layer, sheet, 12, 11, GUIDE_COLOR, 0.8)
    add_scatter(layer, sheet, 4, 3)
    add_line(layer, sheet, 8, 7, FIT_COLOR, 2.4)
    bode = graph.add_layer()
    phase = graph.add_layer()
    mag_data = bode.add_plot(sheet, coly=5, colx=0, type="s")
    mag_data.color = DATA_COLOR
    mag_data.symbol_kind = 2
    mag_data.symbol_size = 6
    mag_data.symbol_interior = 2
    add_line(bode, sheet, 9, 6, FIT_COLOR, 2.2)
    ph_data = phase.add_plot(sheet, coly=2, colx=0, type="s")
    ph_data.color = DATA_COLOR
    ph_data.symbol_kind = 2
    ph_data.symbol_size = 6
    ph_data.symbol_interior = 2
    add_line(phase, sheet, 10, 6, FIT_COLOR, 2.2)

    for index, box in enumerate(boxes):
        place(graph, index, *box)
    layer.xlim = [x0, x1]
    layer.ylim = [y0, y1]
    layer.axis("x").title = "Z' (MΩ)"
    layer.axis("y").title = "−Z'' (MΩ)"
    write_legend(layer, ((2, "measured"), (3, "Rs–(Rp ∥ CPE)")))
    layer.obj.LT_execute("legend.x = 62; legend.y = 4;")

    bode.xscale = "log10"
    bode.yscale = "log10"
    bode.xlim = [1, 1e6]
    bode.rescale()
    bode.xlim = [1, 1e6]
    bode.axis("x").title = "Frequency (Hz)"
    bode.axis("y").title = "|Z| (Ω)"
    phase.xscale = "log10"
    phase.xlim = [1, 1e6]
    phase.rescale()
    phase.xlim = [1, 1e6]
    phase.axis("x").title = "Frequency (Hz)"
    phase.axis("y").title = "Phase (°)"

    for host in (layer, bode, phase):
        style_frame(host)
    for host in (bode, phase):
        host.obj.LT_execute("layer.x.from = 1")
        host.obj.LT_execute("layer.x.to = 1e6")
        host.obj.LT_execute("layer.x.inc = 2")
        host.obj.LT_execute("layer.x.ticklabel.pt = 12")
        host.obj.LT_execute("layer.y.ticklabel.pt = 12")
        host.obj.LT_execute("layer.x.label.pt = 16")
        host.obj.LT_execute("layer.y.label.pt = 16")
        host.obj.LT_execute("legend.show = 0")
    graph.obj.LT_execute("page.active = 1")
    set_lt_str("py_note", note)
    graph.obj.LT_execute("label -r fitnote")
    graph.obj.LT_execute('label -s -n fitnote "fit";')
    graph.obj.LT_execute("fitnote.text$ = py_note$")
    graph.obj.LT_execute(
        "fitnote.attach = 1; fitnote.fsize = 11; "
        "fitnote.x = 8; fitnote.y = 1; fitnote.background = 1;"
    )
    graph.obj.LT_execute("legend.show = 0")
    graph.activate()
    lt_exec(f"win -a {GRAPH}")
    lt_exec("win -z")
    return graph


def main():
    freq, zreal, zimag, phase, zmag = load_spectrum(DATA)
    print("POINTS", len(freq), "f", float(freq.min()), float(freq.max()))
    rs0, rp0, q0, n0 = prefit(freq, zreal, zimag)
    enter_folder()
    install_function()
    old = lt_float("@NLFS")
    lt_exec("@NLFS = 0")
    try:
        check_synthetic()
        rs, rp, q, alpha = rs0, rp0, q0, n0
        before = page_names()
        drop_named(BOOK)
        drop_named(GRAPH)
        book = op.new_book("w", "D114 B8 pristine Rs-Rp-CPE")
        book.name = BOOK
        fit_sheet = book[0]
        fit_sheet.name = "FitInput"
        fill(
            fit_sheet,
            (
                (freq, "f", "Hz", "X"),
                (zmag, "zm", "Ohm", "X"),
                (zreal / zmag, "yr", "", "Y"),
                (zimag / zmag, "yi", "", "Y"),
            ),
        )
        fitted, report, curve = run_fit(fit_sheet, rs, rp, q, alpha)
        origin_rs, err_rs = fitted["Rs"], fitted["e_Rs"]
        origin_rp, err_rp = fitted["Rp"], fitted["e_Rp"]
        origin_qpf, err_qpf = fitted["QpF"], fitted["e_QpF"]
        origin_n, err_n = fitted["alpha"], fitted["e_alpha"]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in (origin_rs, origin_rp, origin_qpf, origin_n)):
            fail(f"Origin fit did not return parameters: {fitted}")
        q = origin_qpf * 1e-12
        err_q = None if err_qpf is None else err_qpf * 1e-12
        fit = scores(freq, zreal, zimag, origin_rs, origin_rp, q, origin_n)
        cap, tau, f_char = ceff(origin_rp, q, origin_n)
        print(
            "ORIGIN FIT",
            f"Rs={origin_rs:.6g}",
            f"Rp={origin_rp:.6g}",
            f"Q={q:.6g}",
            f"n={origin_n:.6g}±{err_n:.3g}",
            f"eRs={err_rs:.4g}",
            f"eRp={err_rp:.4g}",
            f"eQ={err_q:.4g}",
            f"R2={fit['r2']:.4f}",
            f"chi={fit['chi_red']:.4g}",
            f"Ceff={cap:.6g}",
        )
        if fit["r2"] < 0.9:
            fail(f"modulus R2 is only {fit['r2']:.3f}")

        dense = np.logspace(math.log10(float(freq.min())), math.log10(float(freq.max())), 400)
        model_r, model_i = z_model(dense, origin_rs, origin_rp, q, origin_n)
        model_mag = np.hypot(model_r, model_i)
        model_phase = np.degrees(np.arctan2(-model_i, model_r))
        data = book.add_sheet("Spectrum")
        million = 1e6
        fill(
            data,
            (
                (freq, "Frequency", "Hz", "X"),
                (zreal, "Z'", "Ω", "Y"),
                (phase, "Phase", "°", "Y"),
                (zreal / million, "Z'", "MΩ", "Y"),
                (zimag / million, "−Z''", "MΩ", "Y"),
                (zmag, "|Z|", "Ω", "Y"),
                (dense, "Frequency fit", "Hz", "X"),
                (model_r / million, "Z' fit", "MΩ", "Y"),
                (model_i / million, "−Z'' fit", "MΩ", "Y"),
                (model_mag, "|Z| fit", "Ω", "Y"),
                (model_phase, "Phase fit", "°", "Y"),
                ([0.0, 1.0], "guide x", "MΩ", "X"),
                ([0.0, 0.0], "guide y", "MΩ", "Y"),
            ),
        )

        rows = [
            ("Circuit", "Rs–(Rp ∥ CPE)", "series Rs, then Rp parallel to a CPE"),
            ("Weighting", "modulus |Z|", "residual of Z' and −Z'' divided by |Z|"),
            ("Points", str(len(freq)), "1 Hz to 1 MHz, 0.00 V, AC 0.1 V"),
            ("Rs", same_unit(origin_rs, err_rs, "Ω"), "high-frequency resistance"),
            ("Rp", same_unit(origin_rp, err_rp, "Ω"), "parallel resistance, arc diameter"),
            ("Q", sci_pm(q, err_q) + " S·sⁿ", "CPE coefficient"),
            ("n", f"{origin_n:.4f} ± {err_n:.4f}", "CPE exponent"),
            ("C_eff", prefixed(cap, "F"), "τ/Rp with τ = (Rp Q)^(1/n)"),
            ("τ", scientific(tau) + " s", "characteristic time"),
            ("f_char", prefixed(f_char, "Hz"), "1/(2πτ)"),
            ("Modulus R²", f"{fit['r2']:.4f}", "weighted real and imaginary parts"),
            ("Reduced χ²", f"{fit['chi_red']:.4g}", f"{fit['n_obs']} observations, 4 parameters"),
            ("Origin report", report or "", "NLFit report range"),
            ("Fit curve", curve or "", "NLFit curve range"),
        ]
        write_parameters(book, rows)
        note = "\n".join(
            (
                "Pristine, 0.00 V    Rs–(Rp ∥ CPE)",
                f"Rs = {same_unit(origin_rs, err_rs, 'Ω')}     Rp = {same_unit(origin_rp, err_rp, 'Ω')}",
                f"Q = {sci_pm(q, err_q)}     n = {origin_n:.4f} ± {err_n:.4f}",
                f"Ceff = {prefixed(cap, 'F')}     R² = {fit['r2']:.3f}",
            )
        )
        # Plot from the spectrum sheet. Move it to the front so book[0] is not required.
        build_graph(data, note)
        for page in list(op.pe.active_folder().pages("g")):
            if page.name in before or page.name == GRAPH:
                continue
            print("DROP GRAPH", page.name)
            page.obj.Destroy()
        located = op.pe.search(GRAPH, 0)
        print("GRAPH FOLDER", located)
        if not located or FOLDER_NAME not in located.replace("\\", "/").lower():
            fail(f"graph landed in {located!r}")
        print("DONE")
    finally:
        lt_exec(f"@NLFS = {old}")


if __name__ == "__main__":
    sys.exit(main())
