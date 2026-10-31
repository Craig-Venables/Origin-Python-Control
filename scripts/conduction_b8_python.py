"""The same B8 conduction pages as conduction_b8.py, drawn with matplotlib.

    py -3 scripts/conduction_b8_python.py

Figures land in plots/b8_conduction/. The last cycle only: circles outward,
triangles back. Solid lines are the outward fits and dashed lines are the
return fits. Each SCLC piece is labelled with its gradient.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from conduction_b8 import (  # noqa: E402
    DEFAULTS,
    NEG,
    NEG_BACK,
    POS,
    POS_BACK,
    analyse,
    names_for,
    notes_for,
)

OUT = ROOT / "plots" / "b8_conduction"

PANELS = (
    ("sclc", "|Voltage| (V)", "|Current| (A)", True),
    ("sch", "sqrt(|V|)", "ln(|I|)", False),
    ("pf", "sqrt(|V|)", "ln(|I| / |V|)", False),
    ("fn", "1/|V|", "ln(|I| / V^2)", False),
)


def keep(label, sign):
    return sign is None or label.startswith(sign)


def threshold_x(mech, leg):
    if mech == "sclc":
        if len(leg["sclc"]) == 2:
            return leg["sclc"][1]["v_th"]
        return None
    window = leg["windows"][mech]
    if not window.get("ok") or window.get("across"):
        return None
    if mech in ("sch", "pf"):
        return window["v_th"] ** 0.5
    return 1.0 / window["v_th"]


def draw(record, sign, title):
    last = len(record["legs"]) - 1
    side = {None: "both", "+": "positive", "-": "negative"}[sign]
    notes = notes_for(record, sign)
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 10.4))
    fig.suptitle(
        f"{title}, {side}    circles out, triangles back    solid out, dashed back",
        fontsize=13,
    )
    styles = (
        ("+ out", POS, "o", 1),
        ("+ back", POS_BACK, "^", 2),
        ("- out", NEG, "o", 1),
        ("- back", NEG_BACK, "^", 2),
    )
    fit_colors = {"+": POS, "-": NEG}
    for ax, (mech, xlabel, ylabel, log) in zip(axes.ravel(), PANELS):
        for label, color, marker, interior in styles:
            if not keep(label, sign):
                continue
            leg = record["legs"][last][label]
            if leg is None:
                continue
            x_data, y_data = leg["coords"][mech]
            ax.plot(
                x_data,
                y_data,
                marker,
                color=color,
                ms=4.5,
                mew=0.6,
                mfc=color if interior == 1 else "none",
                linestyle="none",
                zorder=3,
            )
        signs = ("+", "-") if sign is None else (sign,)
        for item in signs:
            color = fit_colors[item]
            for way, linestyle in (("out", "-"), ("back", "--")):
                leg = record["legs"][last][f"{item} {way}"]
                if leg is None:
                    continue
                if mech == "sclc":
                    for region in leg["sclc"]:
                        ax.plot(region["x"], region["y"], color=color, lw=2.0, ls=linestyle, zorder=4)
                        if sign is not None:
                            mid = len(region["x"]) // 2
                            ax.annotate(
                                f"n = {region['slope']:.2f}",
                                (region["x"][mid], region["y"][mid]),
                                textcoords="offset points",
                                xytext=(6, 8 if way == "out" else -14),
                                fontsize=8,
                                color=color,
                            )
                else:
                    window = leg["windows"][mech]
                    if window.get("ok"):
                        ax.plot(window["x"], window["y"], color=color, lw=2.0, ls=linestyle, zorder=4)
                if way == "out":
                    x_th = threshold_x(mech, leg)
                    if x_th is not None:
                        ax.axvline(x_th, color=color, ls=":", lw=1.0, zorder=2)
        if log:
            ax.set_xscale("log")
            ax.set_yscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        ax.tick_params(labelsize=9)
        note_x = 0.46 if mech == "fn" else 0.03
        ax.text(
            note_x,
            0.97,
            notes[mech],
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=8,
            family="monospace",
            bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "0.45", "alpha": 0.94},
            zorder=5,
        )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for path in DEFAULTS:
        record = analyse(path)
        _book, _both, _pos, _neg, title = names_for(path)
        token = "sweep12" if path.name.startswith("12-") else "sweep4"
        for sign, name in ((None, "both"), ("+", "positive"), ("-", "negative")):
            fig = draw(record, sign, title)
            dest = OUT / f"{token}_{name}.png"
            fig.savefig(dest, dpi=130)
            plt.close(fig)
            written.append(dest)
            print(dest)
    return written


if __name__ == "__main__":
    main()
