"""Fit capacitive spectra in Origin, one graph each, plus a comparison.

Open Origin on the project first. The script does not save it.

    py -3 scripts/fit_cf_all.py
    py -3 scripts/fit_cf_all.py sets/d114_b8.json

With no arguments every JSON file in sets/ is fitted. Copy
sets/d114_b8.json to add another device: point origin at that device's
Project Explorer folder, point data_root at its Solartron folder, and give
every spectrum its own book and graph short name. model is "rcpe" or
"lrcpe". Short names have to be unique in the whole project.
"hold_qn_from" names another spectrum in the same file: that spectrum's
Q and n are held fixed, and only L, Rs and Rp are fitted.

On lrcpe spectra the capacitive arc is often outside 1 Hz–1 MHz, so Rs,
Rp, L and Q trade off. The note still lists every component and its
standard error. Rs+Rp is the stable resistance.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import fit_pristine_eis as base
from originpro.utils import get_lt_str, lt_exec, lt_float, set_lt_str
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SET_DIR = ROOT / "sets"
FDFS = {
    "RsRpCPE": ROOT / "fitfunc" / "RsRpCPE.fdf",
    "LRsRpCPE": ROOT / "fitfunc" / "LRsRpCPE.fdf",
}
DATA_ROOT = SET_DIR
GRAPH = ""
COMPARE = ""
SET_TITLE = ""
FOLDER_NAME = ""
SPECS = []


def drop_named(name):
    located = base.op.pe.search(name, 0) or ""
    if not located:
        return
    if FOLDER_NAME.lower() not in located.replace("\\", "/").lower():
        base.fail(f"{name} already exists in {located}")
    page = base.op.find_book("w", name)
    if page is None:
        page = base.op.find_graph(name)
    if page is not None:
        page.obj.Destroy()


def enter_origin(path):
    base.op.attach()
    base.op.set_show(True)
    base.op.pe.cd(path)
    active = base.op.pe.active_folder().path.replace("\\", "/").rstrip("/")
    if not active.lower().endswith(FOLDER_NAME.lower()):
        base.fail(f"refusing to write, active folder is {active!r}")
    print("FOLDER", active)


def load_sets(arguments):
    paths = [Path(item) for item in arguments] or sorted(SET_DIR.glob("*.json"))
    if not paths:
        base.fail(f"no set files in {SET_DIR}")
    groups = []
    for path in paths:
        group = json.loads(path.read_text(encoding="utf-8"))
        context = group.get("context", group["name"])
        for spec in group["spectra"]:
            spec["context"] = context
            spec.setdefault("long", f"{group['name']} {spec['title']}")
            if spec["model"] not in {"rcpe", "lrcpe"}:
                base.fail(f"{spec['title']} model must be rcpe or lrcpe")
            for field in ("book", "graph", "folder", "file", "color", "title"):
                if not spec.get(field):
                    base.fail(f"{path.name} spectrum is missing {field}")
        groups.append(group)
    return groups


def spectrum_path(spec):
    if spec.get("path"):
        return Path(spec["path"])
    return DATA_ROOT / spec["folder"] / "origin_data" / spec["file"]


def z_lrcpe(freq, ind, rs, rp, q, alpha):
    zreal, zimag = base.z_model(freq, rs, rp, q, alpha)
    return zreal, zimag - (2 * math.pi * freq) * ind


def install_functions():
    for name, path in FDFS.items():
        posix = path.as_posix()
        lt_exec(f'run.section(dofile, OnUnInstallFDF, "{posix}")')
        lt_exec(f'run.section(dofile, OnInstallFDF, "{posix}")')
        xml = get_lt_str(f'GetFDFAsXML("{name}")$') or ""
        if name not in xml or "QpF" not in xml:
            base.fail(f"could not install {name}")
        print("FUNCTION", name, "xml", len(xml))


def run_fit(sheet, func, starts, fixed=()):
    """NLFit. Read the tree after nlfit and before nlend.

    Names in fixed stay at their starting values (f_<name> = 1).
    """
    sheet.activate()
    tree = "eisfit"
    lt_exec(f"del -vt {tree}")
    command = f"nlbeginr {sheet.lt_range()}!(1,2,3,4) {func} {tree}"
    if not lt_exec(command):
        base.fail(f"nlbegin failed: {command}")
    for name, value in starts.items():
        lt_exec(f"{tree}.{name} = {float(value)}")
    for name in fixed:
        if not lt_exec(f"{tree}.f_{name} = 1") or lt_float(f"{tree}.f_{name}") != 1:
            base.fail(f"could not hold {name} fixed")
    print("ORIGIN START", func, {name: lt_float(f"{tree}.{name}") for name in starts}, "fixed", list(fixed))
    if not lt_exec("nlfit"):
        base.fail(f"nlfit failed for {func}")
    names = list(starts) + [f"e_{name}" for name in starts] + ["chisqr", "niter"]
    fitted = {name: lt_float(f"{tree}.{name}") for name in names}
    for name in fixed:
        moved = abs(fitted[name] - float(starts[name]))
        if moved > max(1e-5, 1e-4 * abs(float(starts[name]))):
            base.fail(f"{name} was held at {starts[name]} but Origin returned {fitted[name]}")
    print(
        "ORIGIN END",
        func,
        " ".join(f"{name}={fitted[name]:.6g}" for name in starts),
        f"iter={fitted['niter']}",
    )
    held = lt_float("@NLFS")
    lt_exec("@NLFS = 0")
    if not lt_exec("nlend 1"):
        base.fail("nlend failed")
    lt_exec(f"@NLFS = {held}")
    report = get_lt_str("__REPORT")
    curve = get_lt_str("__FITCURVE")
    print("REPORT", report)
    print("CURVE", curve)
    return fitted, report, curve


def modulus_ss(residual):
    return float(np.sum(np.asarray(residual, dtype=float) ** 2))


def rcpe_residual(packed, freq, zreal, zimag):
    rs, rp, log_q, alpha = packed
    model_r, model_i = base.z_model(freq, rs, rp, 10 ** log_q, alpha)
    scale = np.hypot(zreal, zimag)
    return np.concatenate(((zreal - model_r) / scale, (zimag - model_i) / scale))


def l_residual(packed, freq, zreal, zimag, rs_fixed=None):
    if rs_fixed is None:
        log_l, rs, rp, log_q, alpha = packed
    else:
        log_l, rp, log_q, alpha = packed
        rs = rs_fixed
    model_r, model_i = z_lrcpe(freq, 10 ** log_l, rs, rp, 10 ** log_q, alpha)
    scale = np.hypot(zreal, zimag)
    return np.concatenate(((zreal - model_r) / scale, (zimag - model_i) / scale))


def prefit_l(freq, zreal, zimag):
    """Several starts. The capacitive arc is missing, so the valley is flat."""
    high = int(np.argmax(freq))
    omega = 2 * math.pi * float(freq[high])
    ind0 = max(-float(zimag[high]) / omega, 1e-8)
    rs_med = float(np.median(zreal))
    drop = max(float(np.max(zreal) - np.min(zreal)), 1.0)
    starts = []
    for rp0 in (drop, 10.0, 100.0, 1000.0, rs_med):
        for cap in (1e-12, 1e-11, 1e-10, 1e-8):
            for alpha in (0.8, 1.0):
                starts.append(
                    [math.log10(ind0), max(rs_med - rp0, 1.0), rp0, math.log10(cap), alpha]
                )
    best = None
    bounds = ([-8.0, 1e-3, 0.1, -15.0, 0.4], [-2.0, 1e5, 1e6, -4.0, 1.0])
    for guess in starts:
        fitted = least_squares(
            l_residual,
            np.asarray(guess, dtype=float),
            args=(freq, zreal, zimag),
            bounds=bounds,
            xtol=1e-14,
            ftol=1e-14,
            max_nfev=250,
        )
        cost = modulus_ss(l_residual(fitted.x, freq, zreal, zimag))
        if best is None or cost < best[0]:
            best = (cost, fitted.x)
    cost, packed = best
    log_l, rs, rp, log_q, alpha = (float(v) for v in packed)
    ind, q = 10 ** log_l, 10 ** log_q
    r_lf = rs + rp
    ratios = []
    for frac in (0.05, 0.85):
        rs_fixed = min(max(frac * r_lf, 1e-3), r_lf * 0.98)
        guess = np.array([log_l, max(r_lf - rs_fixed, 0.1), log_q, alpha])
        fitted = least_squares(
            l_residual,
            guess,
            args=(freq, zreal, zimag, rs_fixed),
            bounds=([-8.0, 0.1, -15.0, 0.4], [-2.0, 1e6, -4.0, 1.0]),
            xtol=1e-14,
            ftol=1e-14,
            max_nfev=200,
        )
        other = modulus_ss(l_residual(fitted.x, freq, zreal, zimag, rs_fixed))
        ratios.append(other / cost if cost else math.inf)
    resolved = min(ratios) > 5.0
    print(
        "PYTHON START",
        f"L={ind:.6g}",
        f"Rs={rs:.6g}",
        f"Rp={rp:.6g}",
        f"Q={q:.6g}",
        f"n={alpha:.6g}",
        f"Rlf={r_lf:.6g}",
        f"ss={cost:.6g}",
        f"flat={min(ratios):.3g}",
        f"resolved={resolved}",
    )
    return ind, rs, rp, q, alpha, resolved


def prefit_l_held(freq, zreal, zimag, q, alpha):
    """Fit L, Rs and Rp with Q and n already chosen."""
    high = int(np.argmax(freq))
    omega = 2 * math.pi * float(freq[high])
    ind0 = max(-float(zimag[high]) / omega, 1e-8)
    r_lf = float(np.median(zreal))

    def residual(packed, rs_fixed=None):
        if rs_fixed is None:
            log_l, rs, rp = packed
        else:
            log_l, rp = packed
            rs = rs_fixed
        model_r, model_i = z_lrcpe(freq, 10 ** log_l, rs, rp, q, alpha)
        scale = np.hypot(zreal, zimag)
        return np.concatenate(((zreal - model_r) / scale, (zimag - model_i) / scale))

    best = None
    bounds = ([-8.0, 1e-3, 0.1], [-2.0, 1e5, 1e6])
    for frac in (0.02, 0.15, 0.4, 0.7, 0.95):
        rs0 = max(frac * r_lf, 1e-3)
        rp0 = max(r_lf - rs0, 0.1)
        for scale_l in (0.3, 1.0, 3.0):
            guess = [math.log10(max(ind0 * scale_l, 1e-8)), rs0, rp0]
            fitted = least_squares(
                residual,
                np.asarray(guess, dtype=float),
                bounds=bounds,
                xtol=1e-14,
                ftol=1e-14,
                max_nfev=200,
            )
            cost = modulus_ss(residual(fitted.x))
            if best is None or cost < best[0]:
                best = (cost, fitted.x)
    cost, packed = best
    log_l, rs, rp = (float(value) for value in packed)
    ratios = []
    total = rs + rp
    for frac in (0.05, 0.85):
        rs_fixed = min(max(frac * total, 1e-3), total * 0.98)
        fitted = least_squares(
            residual,
            np.array([log_l, max(total - rs_fixed, 0.1)]),
            args=(rs_fixed,),
            bounds=([-8.0, 0.1], [-2.0, 1e6]),
            xtol=1e-14,
            ftol=1e-14,
            max_nfev=200,
        )
        other = modulus_ss(residual(fitted.x, rs_fixed))
        ratios.append(other / cost if cost else math.inf)
    ind = 10 ** log_l
    print(
        "PYTHON HELD",
        f"L={ind:.6g}",
        f"Rs={rs:.6g}",
        f"Rp={rp:.6g}",
        f"Q={q:.6g}",
        f"n={alpha:.6g}",
        f"Rlf={total:.6g}",
        f"ss={cost:.6g}",
        f"flat={min(ratios):.3g}",
    )
    return ind, rs, rp, min(ratios)


def scores(freq, zreal, zimag, model_r, model_i, n_param):
    scale = np.hypot(zreal, zimag)
    residual = np.concatenate(((zreal - model_r) / scale, (zimag - model_i) / scale))
    measured = np.concatenate((zreal / scale, zimag / scale))
    ss_res = float(np.sum(residual ** 2))
    ss_tot = float(np.sum((measured - np.mean(measured)) ** 2))
    return {
        "ss": ss_res,
        "chi_red": ss_res / (residual.size - n_param),
        "r2": 1.0 - ss_res / ss_tot,
        "n_obs": int(residual.size),
    }


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def check_synthetic():
    freq = np.logspace(0, 6, 40)
    rs, rp, q, alpha = 8000.0, 2.5e7, 1.8e-11, 0.93
    zreal, zimag = base.z_model(freq, rs, rp, q, alpha)
    zmag = np.hypot(zreal, zimag)
    drop_named("cfSyn")
    before = base.page_names()
    book = base.op.new_book("w", "synthetic RsRpCPE")
    book.name = "cfSyn"
    sheet = book[0]
    base.fill(
        sheet,
        (
            (freq, "f", "Hz", "X"),
            (zmag, "zm", "Ohm", "X"),
            (zreal / zmag, "yr", "", "Y"),
            (zimag / zmag, "yi", "", "Y"),
        ),
    )
    fitted, _, _ = run_fit(
        sheet, "RsRpCPE", {"Rs": 5000.0, "Rp": 1.2e7, "QpF": 50.0, "alpha": 0.8}
    )
    drop_named("cfSyn")
    for page in list(base.op.pe.active_folder().pages()):
        if page.name not in before:
            page.obj.Destroy()
    got = (fitted["Rs"], fitted["Rp"], fitted["QpF"] * 1e-12, fitted["alpha"])
    checks = {
        "Rs": abs(got[0] - rs) / rs,
        "Rp": abs(got[1] - rp) / rp,
        "Q": abs(got[2] - q) / q,
        "n": abs(got[3] - alpha),
    }
    print("SYN RCPE", checks)
    if max(checks["Rs"], checks["Rp"], checks["Q"]) > 0.02 or checks["n"] > 0.01:
        base.fail(f"RsRpCPE synthetic recovery failed: {checks}")

    ind, rs, rp, q, alpha = 5e-5, 1000.0, 2000.0, 1e-8, 0.85
    zreal, zimag = z_lrcpe(freq, ind, rs, rp, q, alpha)
    zmag = np.hypot(zreal, zimag)
    drop_named("cfSyn")
    before = base.page_names()
    book = base.op.new_book("w", "synthetic LRsRpCPE")
    book.name = "cfSyn"
    sheet = book[0]
    base.fill(
        sheet,
        (
            (freq, "f", "Hz", "X"),
            (zmag, "zm", "Ohm", "X"),
            (zreal / zmag, "yr", "", "Y"),
            (zimag / zmag, "yi", "", "Y"),
        ),
    )
    fitted, _, _ = run_fit(
        sheet,
        "LRsRpCPE",
        {"LuH": 100.0, "Rs": 500.0, "Rp": 8000.0, "QpF": 1000.0, "alpha": 0.6},
    )
    drop_named("cfSyn")
    for page in list(base.op.pe.active_folder().pages()):
        if page.name not in before:
            page.obj.Destroy()
    got_l = fitted["LuH"] * 1e-6
    checks = {
        "L": abs(got_l - ind) / ind,
        "Rs": abs(fitted["Rs"] - rs) / rs,
        "Rp": abs(fitted["Rp"] - rp) / rp,
        "Q": abs(fitted["QpF"] * 1e-12 - q) / q,
        "n": abs(fitted["alpha"] - alpha),
    }
    print("SYN LRCPE", checks)
    if max(checks["L"], checks["Rs"], checks["Rp"], checks["Q"]) > 0.02 or checks["n"] > 0.01:
        base.fail(f"LRsRpCPE synthetic recovery failed: {checks}")


def pack_origin(model, fitted):
    if model == "rcpe":
        q = fitted["QpF"] * 1e-12
        values = {
            "Rs": fitted["Rs"],
            "Rp": fitted["Rp"],
            "Q": q,
            "n": fitted["alpha"],
            "L": 0.0,
            "e_Rs": fitted["e_Rs"],
            "e_Rp": fitted["e_Rp"],
            "e_Q": fitted["e_QpF"] * 1e-12,
            "e_n": fitted["e_alpha"],
            "e_L": None,
        }
        needed = (values["Rs"], values["Rp"], values["Q"], values["n"])
    else:
        q = fitted["QpF"] * 1e-12
        values = {
            "Rs": fitted["Rs"],
            "Rp": fitted["Rp"],
            "Q": q,
            "n": fitted["alpha"],
            "L": fitted["LuH"] * 1e-6,
            "e_Rs": fitted["e_Rs"],
            "e_Rp": fitted["e_Rp"],
            "e_Q": fitted["e_QpF"] * 1e-12,
            "e_n": fitted["e_alpha"],
            "e_L": fitted["e_LuH"] * 1e-6,
        }
        needed = (values["L"], values["Rs"], values["Rp"], values["Q"], values["n"])
    if not all(finite(value) for value in needed):
        base.fail(f"Origin fit did not return parameters: {fitted}")
    return values


def evaluate(model, freq, zreal, zimag, values, n_param=None):
    if model == "rcpe":
        model_r, model_i = base.z_model(freq, values["Rs"], values["Rp"], values["Q"], values["n"])
        if n_param is None:
            n_param = 4
    else:
        model_r, model_i = z_lrcpe(
            freq, values["L"], values["Rs"], values["Rp"], values["Q"], values["n"]
        )
        if n_param is None:
            n_param = 5
    fit = scores(freq, zreal, zimag, model_r, model_i, n_param)
    cap, tau, f_char = base.ceff(values["Rp"], values["Q"], values["n"])
    return fit, cap, tau, f_char, model_r, model_i


def model_curve(model, freq, values):
    dense = np.logspace(math.log10(float(freq.min())), math.log10(float(freq.max())), 400)
    if model == "rcpe":
        model_r, model_i = base.z_model(dense, values["Rs"], values["Rp"], values["Q"], values["n"])
    else:
        model_r, model_i = z_lrcpe(
            dense, values["L"], values["Rs"], values["Rp"], values["Q"], values["n"]
        )
    return dense, model_r, model_i


def page_box(graph):
    """Page width and height. A new graph sometimes reports a blank height."""
    graph.activate()
    graph.obj.LT_execute("double eis_w = page.width")
    graph.obj.LT_execute("double eis_h = page.height")
    width = lt_float("eis_w")
    height = lt_float("eis_h")
    if not math.isfinite(width) or width <= 0:
        width = 6400.0
        graph.obj.LT_execute(f"page.width = {width}")
    if not math.isfinite(height) or height <= 0:
        height = width / 1.41
        graph.obj.LT_execute(f"page.height = {height}")
    return width, height


def display_unit(zmag):
    peak = float(np.max(zmag))
    if peak >= 1e5:
        return 1e6, "MΩ"
    if peak >= 1e3:
        return 1e3, "kΩ"
    return 1.0, "Ω"


def pm(value, error, unit):
    """Value and standard error, kept even when the error exceeds the value."""
    if error is None or not math.isfinite(error) or error <= 0:
        return base.same_unit(value, None, unit)
    if error < abs(value):
        return base.same_unit(value, error, unit)
    scale_source = max(abs(value), error)
    alone = base.same_unit(scale_source, None, unit)
    prefix = ""
    for token in ("M", "k", "m", "µ", "n", "p"):
        if token in alone:
            prefix = token
            break
    divisors = {"M": 1e6, "k": 1e3, "m": 1e-3, "µ": 1e-6, "n": 1e-9, "p": 1e-12}
    scale = divisors.get(prefix, 1.0)
    return f"{value / scale:.3g} ± {error / scale:.3g} {prefix}{unit}".replace("  ", " ")


def panel_note(spec, values):
    """Every fitted component, with Origin's standard error."""
    lines = [spec["title"]]
    if spec["model"] == "lrcpe":
        lines.append(f"L = {pm(values['L'], values['e_L'], 'H')}")
    lines.append(f"Rs = {pm(values['Rs'], values['e_Rs'], 'Ω')}")
    lines.append(f"Rp = {pm(values['Rp'], values['e_Rp'], 'Ω')}")
    held = values.get("held")
    lines.append(f"Q = {base.sci_pm(values['Q'], values['e_Q'])}" + (" held" if held else ""))
    n_error = values["e_n"]
    if n_error is not None and math.isfinite(n_error) and n_error > 0:
        lines.append(f"n = {values['n']:.4f} ± {n_error:.4f}" + (" held" if held else ""))
    else:
        lines.append(f"n = {values['n']:.4f}" + (" held" if held else ""))
    cap, _, _ = base.ceff(values["Rp"], values["Q"], values["n"])
    lines.append(f"Ceff = {base.prefixed(cap, 'F')}")
    return "\n".join(lines)


def add_open(layer, sheet, y_index, x_index, color, size):
    plot = layer.add_plot(sheet, coly=y_index, colx=x_index, type="s")
    plot.color = color
    plot.symbol_kind = 2
    plot.symbol_size = size
    plot.symbol_interior = 2
    return plot


def comparison_boxes(count):
    """Panel boxes as percent of the page: Nyquists, then |Z|, then phase.

    Six spectra keep the two-by-three Nyquist grid with |Z| and phase on
    the right. Any other count gets one Nyquist row and |Z| beside phase
    underneath, so the page has no empty axes.
    """
    if count == 6:
        ny_w, ny_h = 16.2, 38.0
        gap_x, gap_y = 4.6, 9.0
        left0, top0 = 2.2, 3.0
        boxes = []
        for row in range(2):
            for col in range(3):
                boxes.append(
                    (
                        left0 + col * (ny_w + gap_x),
                        top0 + row * (ny_h + gap_y),
                        ny_w,
                        ny_h,
                    )
                )
        bode_left = left0 + 3 * ny_w + 2 * gap_x + 3.4
        bode_w = 98.0 - bode_left
        boxes.append((bode_left, 3.0, bode_w, 40.0))
        boxes.append((bode_left, 49.0, bode_w, 42.0))
        return boxes
    if count < 1 or count > 6:
        base.fail(f"comparison page holds 1 to 6 spectra, not {count}")
    ny_h = 46.0
    gap_x = 2.6
    left0, top0 = 2.2, 2.5
    ny_w = (97.5 - left0 - gap_x * (count - 1)) / count
    boxes = [
        (left0 + col * (ny_w + gap_x), top0, ny_w, ny_h) for col in range(count)
    ]
    lower = top0 + ny_h + 6.5
    lower_h = 97.5 - lower
    # |Z| sits in from the left edge so a four-digit tick label is not clipped.
    boxes.append((8.0, lower, 40.5, lower_h))
    boxes.append((51.5, lower, 46.0, lower_h))
    return boxes


def build_comparison(records):
    drop_named(COMPARE)
    drop_named(GRAPH)
    book = base.op.new_book("w", f"{SET_TITLE} spectra comparison")
    book.name = COMPARE
    bode_sheet = book[0]
    bode_sheet.name = "Bode"
    graph = base.op.new_graph(f"{SET_TITLE}, all states")
    graph.name = GRAPH
    graph.obj.LT_execute("page.lock = 0")
    # A locked aspect ignores the height, so pick a width that still fits
    # the window. The gaps below are what separate the panels.
    graph.obj.LT_execute("page.width = 8800")
    graph.obj.LT_execute("page.height = 6200")
    width, height = page_box(graph)
    print("PAGE", width, height)

    # left, top, width, height, percent of the page. Gutters are wide enough
    # for the axis titles, so neighbouring panels do not cover each other.
    boxes = comparison_boxes(len(records))
    aspect = (boxes[0][2] / 100 * width) / (boxes[0][3] / 100 * height)

    layers = [graph[0]]
    for _ in range(len(boxes) - 1):
        layers.append(graph.add_layer())

    # Column order matters: a Y column uses the nearest X to its left.
    bode_columns = [(records[0]["freq"], "Frequency", "Hz", "X")]
    for record in records:
        bode_columns.append((record["zmag"], f"|Z| {record['spec']['title']}", "Ω", "Y"))
    for record in records:
        bode_columns.append((record["phase"], f"Phase {record['spec']['title']}", "°", "Y"))
    bode_columns.append((records[0]["dense"], "Frequency fit", "Hz", "X"))
    for record in records:
        bode_columns.append((record["model_mag"], f"|Z| fit {record['spec']['title']}", "Ω", "Y"))
    for record in records:
        bode_columns.append((record["model_phase"], f"Phase fit {record['spec']['title']}", "°", "Y"))
    base.fill(bode_sheet, bode_columns)

    summary = []
    for index, record in enumerate(records):
        spec = record["spec"]
        values = record["values"]
        scale, unit = display_unit(record["zmag"])
        x = record["zreal"] / scale
        y = record["zimag"] / scale
        x0, x1 = float(np.min(x)), float(np.max(x))
        y0 = min(0.0, float(np.min(y)))
        y1 = max(0.0, float(np.max(y)))
        span = max(x1 - x0, y1 - y0, 1e-9)
        pad = 0.07 * span
        x0, x1, y0, y1 = base.equal_limits(x0 - pad, x1 + pad, y0 - pad, y1 + pad, aspect)
        sheet = book.add_sheet(spec["key"])
        base.fill(
            sheet,
            (
                (x, "Z'", unit, "X"),
                (y, "−Z''", unit, "Y"),
                (record["model_r"] / scale, "Z' fit", unit, "X"),
                (record["model_i"] / scale, "−Z'' fit", unit, "Y"),
                ([x0, x1], "guide x", unit, "X"),
                ([0.0, 0.0], "guide y", unit, "Y"),
            ),
        )
        layer = layers[index]
        base.add_line(layer, sheet, 5, 4, base.GUIDE_COLOR, 0.6)
        add_open(layer, sheet, 1, 0, spec["color"], 5)
        base.add_line(layer, sheet, 3, 2, spec["color"], 1.8)
        record["limits"] = (x0, x1, y0, y1, unit)
        record["sheet"] = sheet
        r_lf = values["Rs"] + values["Rp"]
        summary.append(
            (
                spec["title"],
                "L–Rs–(Rp∥CPE)" if spec["model"] == "lrcpe" else "Rs–(Rp∥CPE)",
                base.prefixed(r_lf, "Ω"),
                base.same_unit(values["Rs"], values["e_Rs"], "Ω"),
                base.same_unit(values["Rp"], values["e_Rp"], "Ω"),
                "—" if spec["model"] == "rcpe" else base.same_unit(values["L"], values["e_L"], "H"),
                f"{values['n']:.4f}",
                base.prefixed(record["cap"], "F"),
                f"{record['fit']['r2']:.3f}",
                "yes" if spec.get("resolved", True) else "no, use Rs+Rp",
            )
        )

    bode = layers[-2]
    phase = layers[-1]
    n = len(records)
    fit_x = 1 + 2 * n
    for index, record in enumerate(records):
        add_open(bode, bode_sheet, 1 + index, 0, record["spec"]["color"], 5)
        add_open(phase, bode_sheet, 1 + n + index, 0, record["spec"]["color"], 5)
    for index, record in enumerate(records):
        base.add_line(bode, bode_sheet, fit_x + 1 + index, fit_x, record["spec"]["color"], 1.6)
        base.add_line(phase, bode_sheet, fit_x + 1 + n + index, fit_x, record["spec"]["color"], 1.6)

    for index, box in enumerate(boxes):
        base.place(graph, index, *box)

    for index, record in enumerate(records):
        layer = layers[index]
        x0, x1, y0, y1, unit = record["limits"]
        # Extra room on the left so the first tick is not clipped.
        x0 -= 0.1 * (x1 - x0)
        layer.xlim = [x0, x1]
        layer.ylim = [y0, y1]
        layer.axis("x").title = f"Z' ({unit})"
        layer.axis("y").title = f"−Z'' ({unit})"
        base.style_frame(layer)
        layer.obj.LT_execute("layer.x.label.pt = 14")
        layer.obj.LT_execute("layer.y.label.pt = 14")
        layer.obj.LT_execute("layer.x.ticklabel.pt = 11")
        layer.obj.LT_execute("layer.y.ticklabel.pt = 11")
        graph.obj.LT_execute(f"page.active = {index + 1}")
        hide_legend()
        set_lt_str("py_note", panel_note(record["spec"], record["values"]))
        name = f"n{index}"
        graph.obj.LT_execute(f"label -r {name}")
        graph.obj.LT_execute(f'label -s -n {name} "fit";')
        graph.obj.LT_execute(f"{name}.text$ = py_note$")
        # attach 2 is axis units, so the note stays inside that panel.
        # Semicircles are empty at the upper right; the pulse hook is empty
        # on the lower left. Keep the box off the axis titles.
        if record["spec"]["model"] == "lrcpe" and n == 6:
            lx = x0 + 0.16 * (x1 - x0)
            ly = y0 + 0.32 * (y1 - y0)
        elif record["spec"]["model"] == "lrcpe":
            # The equal-axis expansion leaves the right side empty.
            lx = x0 + 0.58 * (x1 - x0)
            ly = y1 - 0.10 * (y1 - y0)
        else:
            lx = x0 + 0.30 * (x1 - x0)
            ly = y1 - 0.06 * (y1 - y0)
        graph.obj.LT_execute(
            f"{name}.attach = 2; {name}.fsize = 8; "
            f"{name}.x = {lx}; {name}.y = {ly}; {name}.background = 1;"
        )

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
    for host in (bode, phase):
        base.style_frame(host)
        host.obj.LT_execute("layer.x.from = 1")
        host.obj.LT_execute("layer.x.to = 1e6")
        host.obj.LT_execute("layer.x.inc = 2")
        host.obj.LT_execute("layer.x.ticklabel.pt = 12")
        host.obj.LT_execute("layer.y.ticklabel.pt = 12")
        host.obj.LT_execute("layer.x.label.pt = 16")
        host.obj.LT_execute("layer.y.label.pt = 16")
        hide_legend()
    if n == 6:
        # Page percent. The lower left of the phase panel is empty, so the
        # key sits there instead of on the curves.
        graph.obj.LT_execute(f"page.active = {layers.index(bode) + 1}")
        base.write_legend(bode, tuple((i + 1, record["spec"]["title"]) for i, record in enumerate(records)))
        bode.obj.LT_execute("legend.attach = 0")
        bode.obj.LT_execute("legend.x = 40")
        bode.obj.LT_execute("legend.y = 55")
        bode.obj.LT_execute("legend.fsize = 8")
    else:
        # Axis units. Phase stays near 0 until the inductive rise, so the
        # key sits in that open corner.
        graph.obj.LT_execute(f"page.active = {layers.index(phase) + 1}")
        base.write_legend(phase, tuple((i + 1, record["spec"]["title"]) for i, record in enumerate(records)))
        phase.obj.LT_execute("legend.attach = 2")
        phase.obj.LT_execute("legend.x = 4")
        phase.obj.LT_execute("legend.y = 3.2")
        phase.obj.LT_execute("legend.fsize = 12")

    headers = ("State", "Circuit", "Rs+Rp", "Rs", "Rp", "L", "n", "C_eff", "R²", "Split resolved")
    sheet = book.add_sheet("Summary")
    for col, header in enumerate(headers):
        base.text_column(sheet, col, header, [row[col] for row in summary])

    graph.activate()
    lt_exec(f"win -a {GRAPH}")
    lt_exec("win -z")
    return graph


def hide_legend():
    """legend.show errors, and pops a dialog, when the layer has no legend."""
    if math.isfinite(lt_float("legend.x")):
        lt_exec("legend.show = 0")


def spectrum_sheet(book):
    for item in book:
        if item.name == "Spectrum":
            return item
    return book.add_sheet("Spectrum")


def set_limits(graph, index, x0, x1, y0, y1):
    """Write the axis range last. An earlier ylim was left at the ±10000 default."""
    graph.obj.LT_execute(f"page.active = {index}")
    graph.obj.LT_execute(f"layer.x.from = {float(x0):.8g}")
    graph.obj.LT_execute(f"layer.x.to = {float(x1):.8g}")
    graph.obj.LT_execute(f"layer.y.from = {float(y0):.8g}")
    graph.obj.LT_execute(f"layer.y.to = {float(y1):.8g}")


def data_span(values, log=False):
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if log:
        vals = vals[vals > 0]
    lo, hi = float(np.min(vals)), float(np.max(vals))
    if log:
        return lo / 1.25, hi * 1.25
    pad = 0.08 * max(hi - lo, 1e-9)
    return lo - pad, hi + pad


def build_individual(book, record):
    """Nyquist, |Z| and phase for one spectrum, with every fitted component."""
    spec = record["spec"]
    scale, unit = display_unit(record["zmag"])
    drop_named(spec["graph"])
    graph = base.op.new_graph(spec["long"])
    graph.name = spec["graph"]
    width, height = page_box(graph)
    if height >= width:
        graph.obj.LT_execute(f"page.width = {height * 1.65:.4f}")
        width, height = page_box(graph)
    boxes = ((10, 5, 46, 62), (68, 5, 28, 38), (68, 56, 28, 36))
    aspect = (boxes[0][2] / 100 * width) / (boxes[0][3] / 100 * height)
    x = record["zreal"] / scale
    y = record["zimag"] / scale
    fit_x = record["model_r"] / scale
    fit_y = record["model_i"] / scale
    x0, x1 = float(np.min(np.concatenate((x, fit_x)))), float(np.max(np.concatenate((x, fit_x))))
    y0 = min(0.0, float(np.min(np.concatenate((y, fit_y)))))
    y1 = max(0.0, float(np.max(np.concatenate((y, fit_y)))))
    span = max(x1 - x0, y1 - y0, 1e-9)
    pad = 0.06 * span
    x0, x1, y0, y1 = base.equal_limits(x0 - pad, x1 + pad, y0 - pad, y1 + pad, aspect)
    x0 -= 0.08 * (x1 - x0)
    y1 += 0.18 * (y1 - y0)
    sheet = spectrum_sheet(book)
    base.fill(
        sheet,
        (
            (record["freq"], "Frequency", "Hz", "X"),
            (record["zreal"], "Z'", "Ω", "Y"),
            (record["phase"], "Phase", "°", "Y"),
            (x, "Z'", unit, "Y"),
            (y, "−Z''", unit, "Y"),
            (record["zmag"], "|Z|", "Ω", "Y"),
            (record["dense"], "Frequency fit", "Hz", "X"),
            (fit_x, "Z' fit", unit, "Y"),
            (fit_y, "−Z'' fit", unit, "Y"),
            (record["model_mag"], "|Z| fit", "Ω", "Y"),
            (record["model_phase"], "Phase fit", "°", "Y"),
            ([x0, x1], "guide x", unit, "X"),
            ([0.0, 0.0], "guide y", unit, "Y"),
        ),
    )
    layer = graph[0]
    base.add_line(layer, sheet, 12, 11, base.GUIDE_COLOR, 0.8)
    data = layer.add_plot(sheet, coly=4, colx=3, type="s")
    data.color = base.DATA_COLOR
    data.symbol_kind = 2
    data.symbol_size = 8
    data.symbol_interior = 2
    base.add_line(layer, sheet, 8, 7, base.FIT_COLOR, 2.4)
    bode = graph.add_layer()
    phase = graph.add_layer()
    for host, y_index, fit_index in ((bode, 5, 9), (phase, 2, 10)):
        points = host.add_plot(sheet, coly=y_index, colx=0, type="s")
        points.color = base.DATA_COLOR
        points.symbol_kind = 2
        points.symbol_size = 6
        points.symbol_interior = 2
        base.add_line(host, sheet, fit_index, 6, base.FIT_COLOR, 2.2)
    for index, box in enumerate(boxes):
        base.place(graph, index, *box)
    layer.axis("x").title = f"Z' ({unit})"
    layer.axis("y").title = f"−Z'' ({unit})"
    bode.xscale = "log10"
    bode.yscale = "log10"
    bode.axis("x").title = "Frequency (Hz)"
    bode.axis("y").title = "|Z| (Ω)"
    phase.xscale = "log10"
    phase.axis("x").title = "Frequency (Hz)"
    phase.axis("y").title = "Phase (°)"
    for host in (layer, bode, phase):
        base.style_frame(host)
    for host in (bode, phase):
        host.obj.LT_execute("layer.x.inc = 2")
    z_lo, z_hi = data_span(np.concatenate((record["zmag"], record["model_mag"])), log=True)
    p_lo, p_hi = data_span(np.concatenate((record["phase"], record["model_phase"])))
    for index in (1, 2, 3):
        graph.obj.LT_execute(f"page.active = {index}")
        hide_legend()
    graph.obj.LT_execute("page.active = 1")
    note = panel_note(spec, record["values"]) + f"\nR² = {record['fit']['r2']:.3f}"
    set_lt_str("py_note", note)
    graph.obj.LT_execute("label -r fitnote")
    graph.obj.LT_execute('label -s -n fitnote "fit";')
    graph.obj.LT_execute("fitnote.text$ = py_note$")
    hide_legend()
    set_limits(graph, 1, x0, x1, y0, y1)
    set_limits(graph, 2, 1, 1e6, z_lo, z_hi)
    set_limits(graph, 3, 1, 1e6, p_lo, p_hi)
    graph.obj.LT_execute("page.active = 1")
    if spec["model"] == "lrcpe":
        lx = x0 + 0.08 * (x1 - x0)
        ly = y0 + 0.55 * (y1 - y0)
    else:
        lx = x0 + 0.08 * (x1 - x0)
        ly = y1 - 0.22 * (y1 - y0)
    graph.obj.LT_execute(
        f"fitnote.attach = 2; fitnote.fsize = 12; fitnote.background = 1; "
        f"fitnote.show = 1; fitnote.x = {lx:.8g}; fitnote.y = {ly:.8g};"
    )
    print(
        "GRAPH",
        spec["graph"],
        f"nyquist {x0:.4g}..{x1:.4g} {y0:.4g}..{y1:.4g} {unit}",
        f"|Z| {z_lo:.4g}..{z_hi:.4g}",
        f"phase {p_lo:.4g}..{p_hi:.4g}",
    )
    return graph


def fit_one(spec, require_r2=True):
    freq, zreal, zimag, phase, zmag = base.load_spectrum(spectrum_path(spec))
    print("SPECTRUM", spec["title"], "n", len(freq))
    if spec["model"] == "rcpe":
        rs, rp, q, alpha = base.prefit(freq, zreal, zimag)
        spec["resolved"] = True
        starts = {"Rs": rs, "Rp": rp, "QpF": q * 1e12, "alpha": alpha}
        fixed = ()
        n_free = 4
        func = "RsRpCPE"
    else:
        held = spec.get("hold_qn")
        if held:
            ind, rs, rp, flat = prefit_l_held(freq, zreal, zimag, held["Q"], held["n"])
            spec["resolved"] = flat > 5.0
            starts = {
                "LuH": ind * 1e6,
                "Rs": rs,
                "Rp": rp,
                "QpF": held["Q"] * 1e12,
                "alpha": held["n"],
            }
            fixed = ("QpF", "alpha")
            n_free = 3
        else:
            ind, rs, rp, q, alpha, resolved = prefit_l(freq, zreal, zimag)
            spec["resolved"] = resolved
            starts = {
                "LuH": ind * 1e6,
                "Rs": rs,
                "Rp": rp,
                "QpF": q * 1e12,
                "alpha": min(alpha, 0.999),
            }
            fixed = ()
            n_free = 5
        func = "LRsRpCPE"
    before = base.page_names()
    drop_named(spec["graph"])
    drop_named(spec["book"])
    book = base.op.new_book("w", spec["long"])
    book.name = spec["book"]
    fit_sheet = book[0]
    fit_sheet.name = "FitInput"
    base.fill(
        fit_sheet,
        (
            (freq, "f", "Hz", "X"),
            (zmag, "zm", "Ohm", "X"),
            (zreal / zmag, "yr", "", "Y"),
            (zimag / zmag, "yi", "", "Y"),
        ),
    )
    fitted, report, curve = run_fit(fit_sheet, func, starts, fixed)
    values = pack_origin(spec["model"], fitted)
    held = spec.get("hold_qn")
    if held:
        values["e_Q"] = held["e_Q"]
        values["e_n"] = held["e_n"]
        values["held"] = held["from"]
    fit, cap, tau, f_char, _, _ = evaluate(spec["model"], freq, zreal, zimag, values, n_free)
    print(
        "FIT",
        spec["title"],
        f"Rs={values['Rs']:.6g}",
        f"Rp={values['Rp']:.6g}",
        f"Q={values['Q']:.6g}",
        f"n={values['n']:.6g}",
        f"L={values['L']:.6g}",
        f"Rlf={values['Rs'] + values['Rp']:.6g}",
        f"R2={fit['r2']:.4f}",
        f"Ceff={cap:.6g}",
    )
    if require_r2 and fit["r2"] < 0.9:
        base.fail(f"{spec['title']} modulus R2 is only {fit['r2']:.3f}")
    base.write_parameters(
        book,
        parameter_rows(spec, freq, values, fit, cap, tau, f_char, report, curve),
    )
    for page in list(base.op.pe.active_folder().pages("g")):
        if page.name in before or page.name in {GRAPH, spec["graph"]}:
            continue
        print("DROP GRAPH", page.name)
        page.obj.Destroy()
    dense, model_r, model_i = model_curve(spec["model"], freq, values)
    record = {
        "spec": spec,
        "freq": freq,
        "zreal": zreal,
        "zimag": zimag,
        "phase": phase,
        "zmag": zmag,
        "values": values,
        "fit": fit,
        "cap": cap,
        "dense": dense,
        "model_r": model_r,
        "model_i": model_i,
        "model_mag": np.hypot(model_r, model_i),
        "model_phase": np.degrees(np.arctan2(-model_i, model_r)),
    }
    build_individual(book, record)
    return record


def parameter_rows(spec, freq, values, fit, cap, tau, f_char, report, curve):
    circuit = "Rs–(Rp ∥ CPE)" if spec["model"] == "rcpe" else "L–Rs–(Rp ∥ CPE)"
    n_param = 4 if spec["model"] == "rcpe" else (3 if spec.get("hold_qn") else 5)
    rows = [
        ("State", spec["title"], spec.get("context", "")),
        ("Circuit", circuit, "fitted in Origin NLFit, modulus weighting"),
        ("Points", str(len(freq)), "1 Hz to 1 MHz"),
        ("Rs", base.same_unit(values["Rs"], values["e_Rs"], "Ω"), "series resistance"),
        ("Rp", base.same_unit(values["Rp"], values["e_Rp"], "Ω"), "parallel resistance"),
        ("Rs+Rp", base.prefixed(values["Rs"] + values["Rp"], "Ω"), "low-frequency resistance"),
        ("Q", base.sci_pm(values["Q"], values["e_Q"]) + " S·sⁿ", "CPE coefficient"),
        ("n", f"{values['n']:.4f} ± {values['e_n']:.4f}", "CPE exponent"),
        ("C_eff", base.prefixed(cap, "F"), "τ/Rp with τ = (Rp Q)^(1/n)"),
        ("τ", base.scientific(tau) + " s", "characteristic time"),
        ("f_char", base.prefixed(f_char, "Hz"), "1/(2πτ)"),
        ("Modulus R²", f"{fit['r2']:.4f}", "weighted real and imaginary parts"),
        ("Reduced χ²", f"{fit['chi_red']:.4g}", f"{fit['n_obs']} observations, {n_param} parameters"),
        ("Origin report", report or "", "NLFit report range"),
        ("Fit curve", curve or "", "NLFit curve range"),
    ]
    if spec["model"] == "lrcpe":
        rows.insert(4, ("L", base.same_unit(values["L"], values["e_L"], "H"), "series inductance"))
        if spec.get("hold_qn"):
            rows.append(
                (
                    "Held",
                    "Q and n",
                    f"Taken from {spec['hold_qn']['from']}, where the capacitive arc is inside the window.",
                )
            )
        if not spec.get("resolved", True):
            rows.append(
                (
                    "Note",
                    "Rs and Rp trade off",
                    "The arc is outside the window. Rs+Rp is the stable resistance.",
                )
            )
    return rows


def use_set(group):
    global DATA_ROOT, GRAPH, COMPARE, SET_TITLE, FOLDER_NAME, SPECS
    DATA_ROOT = Path(group["data_root"])
    GRAPH = group["compare_graph"]
    COMPARE = group["compare_book"]
    SET_TITLE = group.get("context", group["name"])
    origin = group["origin"].replace("\\", "/").rstrip("/")
    FOLDER_NAME = origin.split("/")[-1]
    SPECS = group["spectra"]
    return origin


def annotate_choice(graph, rcpe, lrcpe, winner):
    circuit = "L–Rs–(Rp ∥ CPE)" if winner["spec"]["model"] == "lrcpe" else "Rs–(Rp ∥ CPE)"
    lines = [
        panel_note(winner["spec"], winner["values"]),
        f"R² = {winner['fit']['r2']:.3f}",
        f"rcpe R²={rcpe['fit']['r2']:.3f}  ss={rcpe['fit']['ss']:.4g}",
        f"lrcpe R²={lrcpe['fit']['r2']:.3f}  ss={lrcpe['fit']['ss']:.4g}",
        f"kept {circuit}",
    ]
    set_lt_str("py_note", "\n".join(lines))
    graph.activate()
    graph.obj.LT_execute("fitnote.text$ = py_note$")


def donor_from(record):
    values = record.get("rcpe_values")
    if values is None and record["spec"]["model"] == "rcpe":
        values = record["values"]
    if not values:
        return None
    return {
        "Q": values["Q"],
        "n": values["n"],
        "e_Q": values["e_Q"],
        "e_n": values["e_n"],
        "from": record["spec"]["title"],
    }


def fit_both(spec, donor=None):
    """Fit both circuits in Origin and keep the smaller modulus residual."""
    drop_named(spec["book"])
    drop_named(spec["graph"])
    trials = {}
    for model, book, graph_name in (
        ("rcpe", "cfTryR", "gCfTryR"),
        ("lrcpe", "cfTryL", "gCfTryL"),
    ):
        trial = dict(spec)
        trial["model"] = model
        trial["book"] = book
        trial["graph"] = graph_name
        trial.pop("hold_qn", None)
        if model == "lrcpe" and donor:
            trial["hold_qn"] = dict(donor)
        trials[model] = fit_one(trial, require_r2=False)
    rcpe = trials["rcpe"]
    lrcpe = trials["lrcpe"]
    if lrcpe["fit"]["ss"] < rcpe["fit"]["ss"]:
        winner, loser = lrcpe, rcpe
    else:
        winner, loser = rcpe, lrcpe
    drop_named(loser["spec"]["book"])
    drop_named(loser["spec"]["graph"])
    book = base.op.find_book("w", winner["spec"]["book"])
    graph = base.op.find_graph(winner["spec"]["graph"])
    if book is None or graph is None:
        base.fail(f"missing fitted page for {spec['title']}")
    book.name = spec["book"]
    graph.name = spec["graph"]
    kept = dict(spec)
    kept["model"] = winner["spec"]["model"]
    kept["resolved"] = winner["spec"].get("resolved", True)
    if winner["spec"].get("hold_qn"):
        kept["hold_qn"] = winner["spec"]["hold_qn"]
    winner["spec"] = kept
    winner["rcpe_values"] = rcpe["values"]
    annotate_choice(graph, rcpe, lrcpe, winner)
    print(
        "KEPT",
        spec["title"],
        kept["model"],
        f"rcpe ss={rcpe['fit']['ss']:.4g} R2={rcpe['fit']['r2']:.3f}",
        f"lrcpe ss={lrcpe['fit']['ss']:.4g} R2={lrcpe['fit']['r2']:.3f}",
    )
    if winner["fit"]["r2"] < 0.9:
        print("WARN", spec["title"], f"kept R2 is only {winner['fit']['r2']:.3f}")
    return winner


def build_overlay(records):
    """One Nyquist for more spectra than the six-panel comparison page."""
    drop_named(COMPARE)
    drop_named(GRAPH)
    book = base.op.new_book("w", f"{SET_TITLE} spectra comparison")
    book.name = COMPARE
    sheet = book[0]
    sheet.name = "Nyquist"
    columns = []
    for record in records:
        title = record["spec"]["title"]
        columns.append((record["zreal"], f"Z' {title}", "Ohm", "X"))
        columns.append((record["zimag"], f"-Z'' {title}", "Ohm", "Y"))
        columns.append((record["model_r"], f"Z' fit {title}", "Ohm", "X"))
        columns.append((record["model_i"], f"-Z'' fit {title}", "Ohm", "Y"))
    base.fill(sheet, columns)
    graph = base.op.new_graph(f"{SET_TITLE}, all states")
    graph.name = GRAPH
    layer = graph[0]
    for index, record in enumerate(records):
        color = record["spec"]["color"]
        add_open(layer, sheet, index * 4 + 1, index * 4, color, 6)
        base.add_line(layer, sheet, index * 4 + 3, index * 4 + 2, color, 1.8)
    layer.rescale()
    layer.axis("x").title = "Z' (Ohm)"
    layer.axis("y").title = "-Z'' (Ohm)"
    base.style_frame(layer)
    print("GRAPH", GRAPH, "overlay", len(records))
    return graph


def run_paths(
    paths,
    model="rcpe",
    hold_cpe=False,
    compare_book="cfBatch",
    compare_graph="gCfBatch",
    context="CF",
):
    """Fit spectra from a file list. Origin is already in the destination folder.

    model is rcpe, lrcpe, or both. both keeps the circuit with the smaller
    modulus-weighted residual and writes both scores on the graph.
    """
    global DATA_ROOT, GRAPH, COMPARE, SET_TITLE, FOLDER_NAME
    from gui_logic import batch_steps, cf_pairs

    paths = [Path(item) for item in paths]
    if model not in {"rcpe", "lrcpe", "both"}:
        base.fail("model must be rcpe, lrcpe, or both")
    for path in paths:
        if not path.is_file():
            base.fail(f"missing {path}")
    active = base.op.pe.active_folder().path.replace("\\", "/").rstrip("/")
    FOLDER_NAME = active.split("/")[-1]
    if not FOLDER_NAME:
        base.fail(f"refusing to write, active folder is {active!r}")
    COMPARE = compare_book
    GRAPH = compare_graph
    SET_TITLE = context
    DATA_ROOT = ROOT
    print("FOLDER", active)
    if hold_cpe and model == "rcpe":
        print("HOLD", "Q and n apply to inductor fits, so this capacitive batch fits them")
    elif hold_cpe and model == "lrcpe" and len(paths) > 1:
        print("HOLD", "the first file is fitted as Rs-(Rp || CPE) and later files keep its Q and n")
    elif hold_cpe and model == "both" and len(paths) > 1:
        print("HOLD", "later inductor fits keep Q and n from the first file")
    elif hold_cpe and len(paths) < 2:
        print("HOLD", "one spectrum, Q and n are fitted")
    install_functions()
    steps = batch_steps(len(paths), model, hold_cpe)
    pairs = cf_pairs(
        [path.stem for path in paths],
        compare_book,
        compare_graph,
    )
    colors = ("#1f4e79", "#0f7b6c", "#9a7209", "#c45c26", "#6c5480", "#9b2226")
    old = lt_float("@NLFS")
    lt_exec("@NLFS = 0")
    try:
        donor = None
        records = []
        for index, (path, step, (book, graph)) in enumerate(zip(paths, steps, pairs)):
            spec = {
                "key": book,
                "book": book,
                "graph": graph,
                "title": path.stem,
                "long": path.name,
                "model": step["model"],
                "path": str(path),
                "color": colors[index % len(colors)],
                "context": context,
            }
            print("FILE", path.name, "model", step["model"], "hold", step["use_donor"])
            if step["model"] == "both":
                if step["use_donor"] and donor is None:
                    base.fail("no capacitive fit to hold Q and n")
                record = fit_both(spec, donor if step["use_donor"] else None)
            else:
                if step["use_donor"]:
                    if donor is None:
                        base.fail("no capacitive fit to hold Q and n")
                    spec["hold_qn"] = dict(donor)
                record = fit_one(spec)
            found = donor_from(record)
            if found and donor is None:
                donor = found
                print("DONOR", donor["from"], f"Q={donor['Q']:.6g}", f"n={donor['n']:.4f}")
            records.append(record)
        if len(records) >= 2:
            if len(records) <= 6:
                build_comparison(records)
            else:
                print("COMPARE", "overlay", len(records), "spectra")
                build_overlay(records)
            located = base.op.pe.search(GRAPH, 0)
            print("GRAPH FOLDER", located)
            if not located or FOLDER_NAME.lower() not in located.replace("\\", "/").lower():
                base.fail(f"graph landed in {located!r}")
        print("DONE")
        return records
    finally:
        lt_exec(f"@NLFS = {old}")


def main():
    groups = load_sets(sys.argv[1:])
    origin = use_set(groups[0])
    enter_origin(origin)
    install_functions()
    old = lt_float("@NLFS")
    lt_exec("@NLFS = 0")
    try:
        check_synthetic()
        for group in groups:
            origin = use_set(group)
            enter_origin(origin)
            print("SET", group["name"])
            done = {}
            records = []
            for spec in SPECS:
                source_key = spec.get("hold_qn_from")
                if source_key:
                    source = done[source_key]["values"]
                    spec["hold_qn"] = {
                        "Q": source["Q"],
                        "n": source["n"],
                        "e_Q": source["e_Q"],
                        "e_n": source["e_n"],
                        "from": done[source_key]["spec"]["title"],
                    }
                record = fit_one(spec)
                done[spec["key"]] = record
                records.append(record)
            build_comparison(records)
            located = base.op.pe.search(GRAPH, 0)
            print("GRAPH FOLDER", located)
            if not located or FOLDER_NAME.lower() not in located.replace("\\", "/").lower():
                base.fail(f"graph landed in {located!r}")
        print("DONE")
    finally:
        lt_exec(f"@NLFS = {old}")


if __name__ == "__main__":
    sys.exit(main() or 0)
