"""Pure helpers for the plotting window. No Origin import."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

PANEL_KEYS = ("iv", "logiv", "ohmic", "sclc", "schottky", "pf", "fn", "tat")
PANEL_SUFFIX = {
    "iv": "IV",
    "logiv": "Log",
    "ohmic": "Ohm",
    "sclc": "Sclc",
    "schottky": "Sch",
    "pf": "PF",
    "fn": "FN",
    "tat": "TAT",
}


def normalize_folder(folder):
    text = str(folder).strip().replace("\\", "/")
    parts = [part for part in text.split("/") if part and part not in {".", ".."}]
    if not parts:
        raise ValueError("Type a Project Explorer folder.")
    return "/" + "/".join(parts) + "/"


def same_folder(located, folder):
    """True when a page path is the target folder or a folder inside it."""
    loc = str(located).replace("\\", "/").rstrip("/").lower()
    want = str(folder).replace("\\", "/").rstrip("/").lower()
    if not loc or not want:
        return False
    return loc == want or loc.startswith(want + "/")


def chosen_panels(keys):
    wanted = list(keys)
    unknown = [key for key in wanted if key not in PANEL_KEYS]
    if unknown:
        raise ValueError("Unknown panel: " + ", ".join(unknown))
    chosen = [key for key in PANEL_KEYS if key in wanted]
    if not chosen:
        raise ValueError("Choose at least one IV panel.")
    return chosen


def _alnum(stem):
    return "".join(ch for ch in str(stem) if ch.isalnum())


def _good_page(name):
    return bool(name) and len(name) <= 21 and name.isidentifier()


def conduction_graph_names(token):
    names = [f"g{token}{suffix}" for suffix in PANEL_SUFFIX.values()]
    names.append(f"g{token}Page")
    return names


def conduction_tokens(stems):
    """Book short name and graph token for each sweep. Unique, and safe as Origin names."""
    used = set()
    pairs = []
    for stem in stems:
        raw = (_alnum(stem)[:6] or "sweep")
        number = 1
        while True:
            extra = "" if number == 1 else str(number)
            token = (raw[: 6 - len(extra)] + extra) if extra else raw
            token = token[:6]
            book = "c" + token[:7]
            graphs = conduction_graph_names(token)
            fresh = token.lower() not in used and book.lower() not in used
            if fresh and _good_page(book) and all(_good_page(name) for name in graphs):
                used.add(token.lower())
                used.add(book.lower())
                pairs.append((book, token))
                break
            number += 1
            if number > 500:
                raise ValueError(f"no short name for {stem}")
    return pairs


def unique_name(prefix, stem, used, limit=16):
    raw = _alnum(stem) or "data"
    number = 1
    while number < 1000:
        extra = "" if number == 1 else str(number)
        room = limit - len(prefix) - len(extra)
        if room >= 1:
            name = prefix + raw[:room] + extra
            if _good_page(name) and name.lower() not in used:
                used.add(name.lower())
                return name
        number += 1
    raise ValueError(f"no short name for {stem}")


CF_RESERVED = ("cftryr", "gcftryr", "cftryl", "gcftryl")


def cf_pairs(stems, compare_book="cfBatch", compare_graph="gCfBatch"):
    used = {compare_book.lower(), compare_graph.lower(), *CF_RESERVED}
    pairs = []
    for stem in stems:
        book = unique_name("cf", stem, used)
        graph = unique_name("g", stem, used)
        pairs.append((book, graph))
    return pairs


def template_pairs(stems):
    used = set()
    pairs = []
    for stem in stems:
        book = unique_name("b", stem, used)
        graph = unique_name("g", stem, used)
        pairs.append((book, graph))
    return pairs


def batch_steps(count, model, hold):
    """How each spectrum is fitted.

    hold on an inductor batch treats the first file as the capacitive
    reference. Later inductor fits keep that file's Q and n.
    """
    if model not in {"rcpe", "lrcpe", "both"}:
        raise ValueError("model must be rcpe, lrcpe, or both")
    if count < 1:
        raise ValueError("Add at least one file.")
    steps = []
    for index in range(count):
        use_donor = bool(hold and model in {"lrcpe", "both"} and count > 1 and index > 0)
        this_model = model
        if hold and model == "lrcpe" and count > 1 and index == 0:
            this_model = "rcpe"
        steps.append({"model": this_model, "use_donor": use_donor})
    return steps


def grid_shape(count):
    cols = 1 if count == 1 else 2
    rows = int(math.ceil(count / cols))
    return rows, cols


def read_sweep(path):
    """Voltage, current, and time from one sweep file.

    Column names are matched without case, so both ``Voltage`` and
    ``voltage`` are accepted. Time is None when the file has no Time
    column. Rows that are not finite are left out.
    """
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    for delimiter in (None, ","):
        try:
            raw = np.genfromtxt(
                str(path),
                names=True,
                dtype=None,
                encoding="utf-8",
                delimiter=delimiter,
            )
        except (ValueError, OSError, UnicodeError):
            continue
        names = getattr(getattr(raw, "dtype", None), "names", None) or ()
        lookup = {str(name).lower(): name for name in names}
        if "voltage" not in lookup or "current" not in lookup:
            continue
        voltage = np.atleast_1d(np.asarray(raw[lookup["voltage"]], dtype=float))
        current = np.atleast_1d(np.asarray(raw[lookup["current"]], dtype=float))
        count = min(voltage.size, current.size)
        time = None
        if "time" in lookup:
            time = np.atleast_1d(np.asarray(raw[lookup["time"]], dtype=float))[:count]
        keep = np.isfinite(voltage[:count]) & np.isfinite(current[:count])
        if time is not None:
            keep = keep & np.isfinite(time[:count])
            time = time[:count][keep]
        voltage = voltage[:count][keep]
        current = current[:count][keep]
        if voltage.size < 2:
            raise SystemExit(f"{path.name} has no usable Voltage and Current rows")
        packed_time = None if time is None else [float(value) for value in time]
        return (
            [float(value) for value in voltage],
            [float(value) for value in current],
            packed_time,
        )
    raise SystemExit(f"{path.name} needs Voltage and Current columns")


def _meta_value(meta, key):
    try:
        return float(meta[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(f"pulse file is missing {key}") from exc


def pulse_width_text(seconds):
    """Pulse width as written on the graph label."""
    seconds = float(seconds)
    if seconds < 1:
        millis = seconds * 1000
        if abs(millis - round(millis)) < 1e-6:
            return f"{int(round(millis))} ms"
        return f"{millis:g} ms"
    return f"{seconds:g} s"


def pulse_caption(filename, meta, kind):
    """Short graph label: run number, voltage, and pulse width."""
    index = str(filename).split("-", 1)[0]
    width = pulse_width_text(_meta_value(meta, "pulse_width"))
    if kind == "endurance":
        set_v = _meta_value(meta, "set_voltage")
        reset_v = _meta_value(meta, "reset_voltage")
        if abs(reset_v + set_v) < 1e-6 * max(abs(set_v), 1.0):
            volts = f"±{abs(set_v):g} V"
        else:
            volts = f"{set_v:g}/{reset_v:g} V"
    elif kind == "retention":
        volts_value = _meta_value(meta, "pulse_voltage")
        sign = "+" if volts_value > 0 else "−"
        volts = f"{sign}{abs(volts_value):g} V"
    else:
        raise SystemExit(f"unknown pulse kind {kind}")
    return f"{index}, {volts}, {width}"


def read_pulse(path):
    """Keithley 2450 endurance or timed-retention text file.

    Comment lines hold the test parameters. The table is tab-separated.
    Endurance rows are grouped by SET, RESET, and INIT. Retention rows are
    grouped by baseline, post_pulse, and retention.
    """
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    kind = ""
    meta = {}
    header = None
    start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") and "Pulse Test:" in stripped and not kind:
            title = stripped.split("Pulse Test:", 1)[1].strip().lower()
            if "endurance" in title:
                kind = "endurance"
            elif "retention" in title:
                kind = "retention"
        if stripped.startswith("#") and ":" in stripped[1:]:
            body = stripped[1:].strip()
            key, _, value = body.partition(":")
            key = key.strip()
            if key and " " not in key and value.strip():
                meta[key] = value.strip()
        if "Measurement_Number" in line and "Operation" in line:
            header = [part.strip() for part in line.lstrip("#").strip().split("\t")]
            start = index + 1
            break
    if not kind or header is None:
        raise SystemExit(f"{path.name} is not an endurance or retention file")
    needed = ["Timestamp(s)", "Resistance(Ohm)", "Operation"]
    if kind == "endurance":
        needed.append("Cycle Number")
    missing = [name for name in needed if name not in header]
    if missing:
        raise SystemExit(f"{path.name} is missing {', '.join(missing)}")
    groups = {}
    for line in lines[start:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < len(header):
            continue
        row = dict(zip(header, parts))
        try:
            resistance = float(row["Resistance(Ohm)"])
            timestamp = float(row["Timestamp(s)"])
            cycle = float(row["Cycle Number"]) if kind == "endurance" else None
        except ValueError:
            continue
        if not all(math.isfinite(value) for value in (resistance, timestamp) if value is not None):
            continue
        if cycle is not None and not math.isfinite(cycle):
            continue
        operation = row["Operation"].strip()
        if not operation:
            continue
        bucket = groups.setdefault(operation, {"cycle": [], "time": [], "resistance": []})
        bucket["time"].append(timestamp)
        bucket["resistance"].append(resistance)
        if cycle is not None:
            bucket["cycle"].append(cycle)
    if kind == "endurance" and (len(groups.get("SET", {}).get("resistance", ())) < 2 or len(groups.get("RESET", {}).get("resistance", ())) < 2):
        raise SystemExit(f"{path.name} has no SET and RESET reads")
    if kind == "retention" and len(groups.get("retention", {}).get("resistance", ())) < 2:
        raise SystemExit(f"{path.name} has no retention reads")
    return {
        "kind": kind,
        "path": path,
        "name": path.name,
        "label": pulse_caption(path.name, meta, kind),
        "meta": meta,
        "groups": groups,
    }


def pulse_names(stems, kind):
    """Workbook and graph short names for one endurance or retention batch."""
    if kind == "endurance":
        book_prefix, graph_prefix = "en", "gEn"
        compare_book, compare_graph = "enAll", "gEnAll"
    elif kind == "retention":
        book_prefix, graph_prefix = "rt", "gRt"
        compare_book, compare_graph = "rtAll", "gRtAll"
    else:
        raise ValueError(f"unknown pulse kind {kind}")
    used = {compare_book.lower(), compare_graph.lower()}
    pairs = []
    for stem in stems:
        book = unique_name(book_prefix, stem, used)
        graph = unique_name(graph_prefix, stem, used)
        pairs.append((book, graph))
    return pairs, compare_book, compare_graph
