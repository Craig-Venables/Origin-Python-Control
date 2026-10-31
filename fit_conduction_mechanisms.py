"""Room-temperature conduction plots for six D114 B sweeps.

Each measurement gets one figure. The top row is the raw IV and a log IV.
The other panels are the usual diagnostic plots. Positive and negative
are separate, and each polarity is split into the outward sweep and the
return toward zero. R² is the straight-line fit on the axes of that panel.

No thickness, area, or temperature series is used. The score says whether
the plotted form is linear, not which mechanism is proven.

High-field fits use the upper half of |V| on that leg. Ohmic uses the
lower half of the same leg.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATA = Path(r"C:\Users\craig\OneDrive - The University of Nottingham\Documents\Data_folder\D114\B")
OUT = DATA / "conduction_fits"

# The three "Copy" names are not on disk. These are the matching sweeps.
FILES = [
    DATA / "4" / "4-FS-1.5v-0.05sv-0.05sd-Py-Simple_1.5V-.txt",
    DATA / "2" / "21-FS-2.0v-0.05sv-0.05sd-Py-50.txt",
    DATA / "3" / "17-FS-2.5v-0.05sv-0.05sd-Py-2.txt",
    DATA / "8" / "B8-8-FS-0.5v-0.05sv-0.05sd-Py-Simple_1.5V- - Copy.txt",
    DATA / "8" / "B8-9-PS-1.5v-0.05sv-0.05sd-Py-Simple_1.5V-.txt",
    DATA / "8" / "B8-10-FS-1.5v-0.05sv-0.05sd-Py-Simple_1.5V-.txt",
]

POS = "#1f4e79"
NEG = "#9c2f2f"
MIN_POINTS = 5


def load_iv(path: Path):
    raw = np.genfromtxt(path, names=True, delimiter=None)
    voltage = np.asarray(raw["Voltage"], dtype=float)
    current = np.asarray(raw["Current"], dtype=float)
    n = min(voltage.size, current.size)
    ok = np.isfinite(voltage[:n]) & np.isfinite(current[:n])
    return voltage[:n][ok], current[:n][ok]


def cycle_slices(voltage: np.ndarray):
    """Split a repeated triangle into cycles. One return to zero closes a unipolar cycle. A bipolar cycle closes after both polarities have been visited."""
    vmax = float(np.max(np.abs(voltage)))
    tol = max(1e-4, 0.03 * vmax)
    unipolar = float(np.min(voltage)) >= -tol or float(np.max(voltage)) <= tol
    bounds = [0]
    left = False
    seen_pos = False
    seen_neg = False
    for k in range(1, voltage.size):
        if voltage[k] > tol:
            seen_pos = True
            left = True
        elif voltage[k] < -tol:
            seen_neg = True
            left = True
        back = abs(voltage[k]) <= tol and abs(voltage[k - 1]) > tol
        if not (left and back):
            continue
        if unipolar or (seen_pos and seen_neg):
            bounds.append(k + 1)
            left = False
            seen_pos = False
            seen_neg = False
    if bounds[-1] < voltage.size:
        bounds.append(voltage.size)
    slices = []
    for start, stop in zip(bounds, bounds[1:]):
        if stop - start > 8:
            slices.append((start, stop))
    if not slices:
        slices = [(0, voltage.size)]
    return slices


def polarity_legs(voltage, current, positive: bool):
    """Outward and return for one polarity.

    Outward runs from near zero up to the voltage peak. Return runs from
    that peak back toward zero. Either leg is None when it is too short.
    """
    v = np.asarray(voltage, dtype=float)
    i = np.asarray(current, dtype=float)
    floor = 0.05
    if positive:
        peak = int(np.argmax(v))
        if v[peak] < floor:
            return None, None
        before = np.where(v[:peak] < floor)[0]
        on_return = v[peak:] >= floor
    else:
        peak = int(np.argmin(v))
        if v[peak] > -floor:
            return None, None
        before = np.where(v[:peak] > -floor)[0]
        on_return = v[peak:] <= -floor
    start = int(before[-1] + 1) if before.size else 0
    # First point on the way back that has crossed the floor ends the return.
    crossed = np.where(~on_return)[0]
    end = peak + int(crossed[0]) if crossed.size else v.size
    outward = (v[start : peak + 1], i[start : peak + 1])
    returning = (v[peak:end], i[peak:end])
    if outward[0].size < MIN_POINTS:
        outward = None
    if returning[0].size < MIN_POINTS:
        returning = None
    return outward, returning


def line_fit(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]
    if x.size < MIN_POINTS or np.ptp(x) <= 0:
        return None
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    order = np.argsort(x)
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(r2),
        "x": x[order],
        "y": pred[order],
        "n": int(x.size),
    }


def power_law_name(slope):
    """Name a log I–log V slope. Child's law is the slope-2 case of SCLC."""
    if slope < 1.35:
        return "Ohmic"
    if slope < 1.75:
        return "near-Ohmic"
    if slope <= 2.25:
        return "SCLC"
    if slope < 3.0:
        return "steep SCLC"
    return "steep"


def threshold_kind(lower, upper):
    """What the break between two power-law regions is called."""
    if lower < 1.75 and 1.75 <= upper <= 2.6:
        return "V_tr"
    if 1.6 <= lower <= 2.6 and upper >= 3.0:
        return "V_TFL"
    return "break"


def _segment_line(x, y, count=24):
    fit = line_fit(x, y)
    if fit is None:
        return None
    x0 = float(np.min(x))
    x1 = float(np.max(x))
    xs = np.linspace(x0, x1, count)
    ys = fit["slope"] * xs + fit["intercept"]
    return fit, xs, ys


def sclc_regions(abs_v, abs_i):
    """One or two power-law regions on one leg.

    A break is kept only when both sides are linear and the slopes fall
    in different regimes. The plotted line is in |V| and |I|.
    """
    abs_v = np.asarray(abs_v, dtype=float)
    abs_i = np.asarray(abs_i, dtype=float)
    order = np.argsort(abs_v)
    voltage = abs_v[order]
    current = abs_i[order]
    log_v = np.log10(voltage)
    log_i = np.log10(current)
    whole = line_fit(log_v, log_i)
    if whole is None:
        return []

    def region(fit, v0, v1):
        v_line = np.logspace(np.log10(v0), np.log10(v1), 24)
        i_line = 10 ** (fit["slope"] * np.log10(v_line) + fit["intercept"])
        return {
            "v_lo": float(v0),
            "v_hi": float(v1),
            "slope": fit["slope"],
            "r2": fit["r2"],
            "name": power_law_name(fit["slope"]),
            "x": v_line,
            "y": i_line,
        }

    best = None
    last = int(voltage.size)
    for index in range(8, last - 8):
        left = line_fit(log_v[:index], log_i[:index])
        right = line_fit(log_v[index:], log_i[index:])
        if left is None or right is None:
            continue
        if left["r2"] < 0.95 or right["r2"] < 0.95:
            continue
        if power_law_name(left["slope"]) == power_law_name(right["slope"]):
            continue
        if abs(right["slope"] - left["slope"]) < 0.45:
            continue
        quality = abs(right["slope"] - left["slope"])
        if best is None or quality > best[0]:
            best = (quality, index, left, right)
    if best is None:
        only = region(whole, voltage[0], voltage[-1])
        only["kind"] = ""
        return [only]
    _quality, index, left, right = best
    lower = region(left, voltage[0], voltage[index - 1])
    upper = region(right, voltage[index], voltage[-1])
    kind = threshold_kind(left["slope"], right["slope"])
    if kind == "V_TFL":
        upper["name"] = "trap-filled"
    lower["kind"] = ""
    upper["kind"] = kind
    upper["v_th"] = float(voltage[index])
    return [lower, upper]


def high_field_window(x, y, voltage, strong=0.98, weak=0.95):
    """Widest high-voltage tail that stays linear on the plotted axes.

    ``x`` and ``y`` are the mechanism coordinates. ``voltage`` is |V|.
    The lowest start that still meets the cutoff is the threshold.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    voltage = np.asarray(voltage, dtype=float)
    order = np.argsort(voltage)
    x, y, voltage = x[order], y[order], voltage[order]

    def first_start(cutoff):
        for start in range(0, voltage.size - 8):
            fit = line_fit(x[start:], y[start:])
            if fit is not None and fit["r2"] >= cutoff:
                return start, fit
        return None

    found = first_start(strong)
    grade = "strong"
    if found is None:
        found = first_start(weak)
        grade = "weak"
    if found is None:
        whole = line_fit(x, y)
        return {
            "ok": False,
            "r2": float("nan") if whole is None else whole["r2"],
            "slope": float("nan") if whole is None else whole["slope"],
        }
    start, fit = found
    built = _segment_line(x[start:], y[start:])
    if built is None:
        return {"ok": False, "r2": fit["r2"], "slope": fit["slope"]}
    _fit, xs, ys = built
    return {
        "ok": True,
        "grade": grade,
        "v_th": float(voltage[start]),
        "v_hi": float(voltage[-1]),
        "across": start <= 1,
        "slope": fit["slope"],
        "r2": fit["r2"],
        "n": fit["n"],
        "x": xs,
        "y": ys,
    }


def field_mask(abs_v, high: bool):
    peak = float(np.max(abs_v))
    mid = 0.5 * peak
    if high:
        mask = abs_v >= mid
    else:
        mask = abs_v < mid
    if np.count_nonzero(mask) < MIN_POINTS:
        mask = np.ones(abs_v.shape, dtype=bool)
    return mask


def fit_polarity(voltage, current):
    """Diagnostic fits. Current and voltage are signed; models use |V| and |I| except Ohmic."""
    abs_v = np.abs(voltage)
    abs_i = np.abs(current)
    good = abs_i > 0
    if np.count_nonzero(good) < MIN_POINTS:
        return {}
    voltage = voltage[good]
    current = current[good]
    abs_v = abs_v[good]
    abs_i = abs_i[good]
    low = field_mask(abs_v, high=False)
    high = field_mask(abs_v, high=True)

    fits = {}
    ohm = line_fit(voltage[low], current[low])
    if ohm is not None:
        fits["ohmic"] = ohm

    log_v = np.log10(abs_v[high])
    log_i = np.log10(abs_i[high])
    sclc = line_fit(log_v, log_i)
    if sclc is not None:
        # Child's law is the same line with the slope fixed at 2.
        intercept = float(np.mean(log_i - 2.0 * log_v))
        pred = 2.0 * log_v + intercept
        ss_res = float(np.sum((log_i - pred) ** 2))
        ss_tot = float(np.sum((log_i - np.mean(log_i)) ** 2))
        sclc["child_r2"] = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        fits["sclc"] = sclc

    sqrt_v = np.sqrt(abs_v[high])
    sch = line_fit(sqrt_v, np.log(abs_i[high]))
    if sch is not None:
        fits["schottky"] = sch
    pf = line_fit(sqrt_v, np.log(abs_i[high] / abs_v[high]))
    if pf is not None:
        fits["poole_frenkel"] = pf
    inv = 1.0 / abs_v[high]
    fn = line_fit(inv, np.log(abs_i[high] / abs_v[high] ** 2))
    if fn is not None:
        fits["fowler_nordheim"] = fn
    tat = line_fit(inv, np.log(abs_i[high]))
    if tat is not None:
        fits["tat"] = tat
    return fits


def r_text(fit):
    if fit is None:
        return "no fit"
    return f"R²={fit['r2']:.3f}"


def draw_fit(ax, fit, color, logx=False, logy=False, linestyle="-"):
    if fit is None:
        return
    x = fit["x"]
    y = fit["y"]
    if logx:
        x = 10 ** x
    if logy:
        y = 10 ** y
    ax.plot(x, y, color=color, linewidth=1.6, linestyle=linestyle)


def plot_file(path: Path):
    voltage, current = load_iv(path)
    slices = cycle_slices(voltage)
    start, stop = slices[0]
    v = voltage[start:stop]
    i = current[start:stop]
    pos_out, pos_back = polarity_legs(v, i, True)
    neg_out, neg_back = polarity_legs(v, i, False)
    # Circles are the sweep out to the peak. Triangles are the return toward zero.
    series = (
        ("+ out", pos_out, "#1f4e79", "o", "-"),
        ("+ back", pos_back, "#5b8fc7", "^", "--"),
        ("- out", neg_out, "#9c2f2f", "o", "-"),
        ("- back", neg_back, "#d07a6a", "^", "--"),
    )
    fits = {
        name: fit_polarity(*branch) if branch is not None else {}
        for name, branch, *_rest in series
    }

    fig, axes = plt.subplots(4, 2, figsize=(12.5, 15.5))
    cycle_note = f"cycle 1 of {len(slices)}" if len(slices) > 1 else "single sweep"
    fig.suptitle(path.name, fontsize=12)
    fig.text(
        0.5,
        0.955,
        f"Room temperature  ·  {cycle_note}  ·  circles = sweep out, triangles = return  ·  R² is the high-field half of that leg",
        ha="center",
        fontsize=8,
        color="#444444",
    )

    ax = axes[0, 0]
    if len(slices) > 1:
        ax.plot(voltage, current, color="#d0d0d0", linewidth=0.4, label=f"all {len(slices)} cycles")
    for name, branch, color, _marker, style in series:
        if branch is None:
            continue
        ax.plot(branch[0], branch[1], color=color, linestyle=style, linewidth=1.3, label=name)
    ax.axhline(0, color="#bbbbbb", linewidth=0.6)
    ax.axvline(0, color="#bbbbbb", linewidth=0.6)
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (A)")
    ax.set_title("IV")
    ax.legend(fontsize=7, loc="best")

    ax = axes[0, 1]
    for name, branch, color, _marker, style in series:
        if branch is None:
            continue
        ax.semilogy(branch[0], np.abs(branch[1]), color=color, linestyle=style, linewidth=1.2, label=name)
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("|Current| (A)")
    ax.set_title("Log IV, out and return")
    ax.legend(fontsize=7, loc="best")

    # Ohmic: signed I vs V, low-field line.
    ax = axes[1, 0]
    for name, branch, color, marker, style in series:
        if branch is None:
            continue
        ax.plot(branch[0], branch[1], marker, color=color, markersize=3.5, linestyle="none", label=f"{name} {r_text(fits[name].get('ohmic'))}")
        draw_fit(ax, fits[name].get("ohmic"), color, linestyle=style)
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current (A)")
    ax.set_title("Ohmic, low-field")
    ax.legend(fontsize=6.5)

    # SCLC log-log.
    ax = axes[1, 1]
    for name, branch, color, marker, style in series:
        if branch is None:
            continue
        ax.loglog(np.abs(branch[0]), np.abs(branch[1]), marker, color=color, markersize=3.5, linestyle="none")
        fit = fits[name].get("sclc")
        draw_fit(ax, fit, color, logx=True, logy=True, linestyle=style)
        if fit is None:
            label = f"{name} no fit"
        else:
            label = f"{name} n={fit['slope']:.2f} {r_text(fit)}"
        ax.plot([], [], color=color, linestyle=style, label=label)
    ax.set_xlabel("|Voltage| (V)")
    ax.set_ylabel("|Current| (A)")
    ax.set_title("SCLC, log-log, high-field")
    ax.legend(fontsize=6.5)

    def diag(ax, key, xlabel, ylabel, title, x_of, y_of, high_only=False):
        for name, branch, color, marker, style in series:
            if branch is None:
                continue
            abs_v = np.abs(branch[0])
            abs_i = np.abs(branch[1])
            high = field_mask(abs_v, high=True)
            xx = x_of(abs_v)
            yy = y_of(abs_v, abs_i)
            if not high_only:
                ax.plot(xx[~high], yy[~high], marker, color=color, markersize=3, alpha=0.35, linestyle="none")
            ax.plot(
                xx[high],
                yy[high],
                marker,
                color=color,
                markersize=3.5,
                linestyle="none",
                label=f"{name} {r_text(fits[name].get(key))}",
            )
            draw_fit(ax, fits[name].get(key), color, linestyle=style)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=6.5)

    diag(
        axes[2, 0],
        "schottky",
        "sqrt(|V|) (V^0.5)",
        "ln(|I|)",
        "Schottky, high-field",
        lambda av: np.sqrt(av),
        lambda av, ai: np.log(ai),
    )
    diag(
        axes[2, 1],
        "poole_frenkel",
        "sqrt(|V|) (V^0.5)",
        "ln(|I|/|V|)",
        "Poole–Frenkel, high-field",
        lambda av: np.sqrt(av),
        lambda av, ai: np.log(ai / av),
    )
    diag(
        axes[3, 0],
        "fowler_nordheim",
        "1/|V| (1/V)",
        "ln(|I|/V²)",
        "Fowler–Nordheim, high-field",
        lambda av: 1.0 / av,
        lambda av, ai: np.log(ai / av ** 2),
        high_only=True,
    )
    diag(
        axes[3, 1],
        "tat",
        "1/|V| (1/V)",
        "ln(|I|)",
        "Trap-assisted tunneling, high-field",
        lambda av: 1.0 / av,
        lambda av, ai: np.log(ai),
        high_only=True,
    )

    for ax in axes.ravel():
        ax.grid(True, alpha=0.25)
        ax.tick_params(labelsize=8)

    fig.tight_layout(rect=(0, 0, 1, 0.945))
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{path.stem}_conduction.png"
    fig.savefig(dest, dpi=130)
    plt.close(fig)

    rows = []
    for side in ("+ out", "+ back", "- out", "- back"):
        for name in ("ohmic", "sclc", "schottky", "poole_frenkel", "fowler_nordheim", "tat"):
            fit = fits[side].get(name)
            rows.append(
                {
                    "file": path.name,
                    "cycles": len(slices),
                    "polarity": side,
                    "model": name,
                    "r2": "" if fit is None else f"{fit['r2']:.4f}",
                    "slope": "" if fit is None else f"{fit['slope']:.6g}",
                    "n": "" if fit is None else fit["n"],
                    "child_r2": "" if fit is None or "child_r2" not in fit else f"{fit['child_r2']:.4f}",
                }
            )
    return dest, rows


def main():
    all_rows = []
    for path in FILES:
        if not path.exists():
            raise SystemExit(f"missing {path}")
        dest, rows = plot_file(path)
        all_rows.extend(rows)
        print(dest.name)
        for row in rows:
            if row["r2"]:
                extra = f"  child {row['child_r2']}" if row["child_r2"] else ""
                print(f"  {row['polarity']:<8} {row['model']:<16} R2 {row['r2']}  slope {row['slope']}{extra}")

    summary = OUT / "conduction_r2.csv"
    with summary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file", "cycles", "polarity", "model", "r2", "slope", "n", "child_r2"],
        )
        writer.writeheader()
        writer.writerows(all_rows)
    print("WROTE", summary)


if __name__ == "__main__":
    main()
