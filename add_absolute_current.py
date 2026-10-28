"""Add an Absolute Current column immediately after every Current column.

Touches only allcombined, v1p0, and v1p5. Does not save the project and
does not change the original sweep books.
"""
import math

import originpro as op

op.attach()
op.set_show(True)

TARGETS = ("allcombined", "v1p0", "v1p5")
AMP_UNITS = {"a", "amp", "amps", "ampere", "amperes"}


def cell_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if isinstance(number, float) and math.isnan(number):
        return None
    return number


def is_current(lname, units):
    name = (lname or "").strip().lower()
    unit = (units or "").strip().lower().replace(" ", "")
    if "absolute" in name:
        return False
    if name == "current":
        return True
    return unit in AMP_UNITS


def label(wks, index, kind):
    try:
        return wks.get_label(index, kind) or ""
    except Exception:
        return ""


def read_columns(wks):
    columns = []
    for index in range(wks.cols):
        data = [cell_value(item) for item in wks.to_list(index)]
        columns.append(
            {
                "lname": label(wks, index, "L"),
                "units": label(wks, index, "U"),
                "comments": label(wks, index, "C"),
                "source": label(wks, index, "Source"),
                "type": int(wks.obj[index].GetType()),
                "data": data,
            }
        )
    return columns


def absolute_column(column):
    values = []
    for value in column["data"]:
        if value is None or isinstance(value, str):
            values.append(value)
        else:
            values.append(abs(value))
    return {
        "lname": "Absolute Current",
        "units": "A",
        "comments": column["comments"],
        "source": column["source"],
        "type": 0,
        "data": values,
    }


def with_absolute(columns):
    expanded = []
    added = 0
    for index, column in enumerate(columns):
        expanded.append(column)
        if not is_current(column["lname"], column["units"]):
            continue
        nxt = columns[index + 1] if index + 1 < len(columns) else None
        if nxt and (nxt["lname"] or "").strip().lower() == "absolute current":
            continue
        expanded.append(absolute_column(column))
        added += 1
    return expanded, added


# Guard: a source sweep book must stay untouched.
source = op.find_book("w", "Book35")
source_cols_before = source[0].cols if source else None

for name in TARGETS:
    wb = op.find_book("w", name)
    if wb is None:
        raise SystemExit(f"missing workbook {name}")
    wks = wb[0]
    original = read_columns(wks)
    expanded, added = with_absolute(original)
    print(f"{name} before {len(original)} after {len(expanded)} added {added}")
    for index, column in enumerate(expanded):
        wks.from_list(
            index,
            column["data"],
            lname=column["lname"],
            units=column["units"],
            comments=column["comments"],
        )
        if column["source"]:
            wks.set_label(index, column["source"], "Source")
        wks.obj[index].PutType(column["type"])

    check = read_columns(wks)
    current_followed = 0
    current_total = 0
    bad_voltage = []
    for index, column in enumerate(check):
        if is_current(column["lname"], column["units"]):
            current_total += 1
            nxt = check[index + 1] if index + 1 < len(check) else None
            if nxt and nxt["lname"] == "Absolute Current" and nxt["units"] == "A":
                current_followed += 1
        if column["lname"].strip().lower() == "voltage" and column["type"] != 3:
            bad_voltage.append(index)
    print(
        f"  currents {current_total} followed {current_followed} "
        f"bad_voltage {bad_voltage} cols {wks.cols}"
    )

if source is not None:
    print("Book35 cols", source_cols_before, "->", source[0].cols)
