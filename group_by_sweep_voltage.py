"""Split /D114/B/all/ sweep books into one workbook per sweep voltage.

Purpose
    Group filenames such as b22-FS-1.0v-... by the first -<number>v token
    (1.0 or 1.5, not the trailing _1.5V). Copy voltage, current, and time.
    Put the first two filename characters in the column comments, and mark
    Voltage columns as X.

Input
    The open OriginPro session and /D114/B/all/. Books whose long name does
    not match that filename pattern, including allcombined, are skipped.

Output
    v1p0 ("combined 1.0v") and v1p5 ("combined 1.5v") in the same folder.
    Prints the groups, then whether labels, units, and comments match.
    Does not save the project and does not change the source books.
    Stops if v1p0 or v1p5 already exist.
"""
import math
import re

import originpro as op

op.attach()
op.set_show(True)

FOLDER = "/D114/B/all/"
op.pe.cd(FOLDER)
active = op.pe.active_folder().path
print("ACTIVE", repr(active))
if active != FOLDER:
    raise SystemExit(f"refusing to write, active folder is {active!r}")

# b22-FS-1.0v-...  -> prefix b2, group 1.0
# The trailing _1.5V is not used; the first -<number>v token is the sweep voltage.
PATTERN = re.compile(r"^(..).*?-([0-9]+(?:\.[0-9]+)?)v", re.IGNORECASE)


def cell_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if math.isnan(number):
        return None
    return number


groups = {}
skipped = []
snapshots = {}
for wb in op.pe.active_folder().pages("w"):
    match = PATTERN.match(wb.lname or "")
    if not match:
        skipped.append(f"{wb.name}|{wb.lname}")
        continue
    prefix, voltage = match.group(1), match.group(2)
    sheets = []
    for wks in wb:
        columns = []
        for index in range(wks.cols):
            data = [cell_value(item) for item in wks.to_list(index)]
            columns.append(
                {
                    "lname": wks.get_label(index, "L") or "",
                    "units": wks.get_label(index, "U") or "",
                    "rows": len(data),
                    "data": data,
                    "first": data[0] if data else None,
                    "last": data[-1] if data else None,
                }
            )
        sheets.append(columns)
    record = {
        "name": wb.name,
        "lname": wb.lname,
        "prefix": prefix,
        "sheets": sheets,
    }
    groups.setdefault(voltage, []).append(record)
    snapshots[wb.name] = record

print("SKIPPED", len(skipped))
for item in skipped:
    print("SKIP", item)
for voltage in sorted(groups, key=float):
    names = [item["lname"] for item in groups[voltage]]
    print(f"GROUP {voltage} COUNT {len(names)}")
    for name in names:
        print("  ", name)

short_for = {}
for voltage in groups:
    token = voltage.replace(".", "p")
    short_for[voltage] = "v" + token

existing = {wb.name for wb in op.pe.active_folder().pages("w")}
for voltage, short in short_for.items():
    if short in existing:
        raise SystemExit(f"{short} already exists; leaving it untouched")

created = []
for voltage in sorted(groups, key=float):
    records = groups[voltage]
    dest_wb = op.new_book("w", f"combined {voltage}v")
    dest_wb.name = short_for[voltage]
    dest = dest_wb[0]
    column_index = 0
    expected_lnames = []
    expected_units = []
    expected_comments = []
    voltage_columns = []
    for record in records:
        for sheet in record["sheets"]:
            for column in sheet:
                is_voltage = column["lname"].strip().lower() == "voltage"
                dest.from_list(
                    column_index,
                    column["data"],
                    lname=column["lname"],
                    units=column["units"],
                    comments=record["prefix"],
                    axis="X" if is_voltage else "",
                )
                expected_lnames.append(column["lname"])
                expected_units.append(column["units"])
                expected_comments.append(record["prefix"])
                if is_voltage:
                    voltage_columns.append(column_index)
                column_index += 1
    got_lnames = [dest.get_label(i, "L") for i in range(dest.cols)]
    got_units = [dest.get_label(i, "U") for i in range(dest.cols)]
    got_comments = [dest.get_label(i, "C") for i in range(dest.cols)]
    print(
        "CREATED",
        dest_wb.name,
        dest_wb.lname,
        "cols",
        dest.cols,
        "labels",
        got_lnames == expected_lnames,
        "units",
        got_units == expected_units,
        "comments",
        got_comments == expected_comments,
        "folder",
        op.pe.search(dest_wb.name, 0),
    )
    # Column type: Origin stores X as numeric type. Read it back for voltage columns.
    x_ok = []
    for index in voltage_columns:
        dest.lt_exec(f"wks.col = {index + 1}; py_xtype = wks.col.type;")
        x_ok.append(int(op.lt_float("py_xtype")))
    print("VOLTAGE_TYPES", x_ok)
    created.append((voltage, dest_wb.name, dest_wb.lname, len(records), dest.cols))

mismatches = []
for wb in op.pe.active_folder().pages("w"):
    original = snapshots.get(wb.name)
    if original is None:
        continue
    sheets = list(wb)
    if len(sheets) != len(original["sheets"]):
        mismatches.append(f"{wb.name} sheet count")
        continue
    for sheet, wks in zip(original["sheets"], sheets):
        if wks.cols != len(sheet):
            mismatches.append(f"{wb.name} col count")
            continue
        for index, column in enumerate(sheet):
            lname = wks.get_label(index, "L") or ""
            units = wks.get_label(index, "U") or ""
            data = [cell_value(item) for item in wks.to_list(index)]
            first = data[0] if data else None
            last = data[-1] if data else None
            if lname != column["lname"] or units != column["units"]:
                mismatches.append(f"{wb.name} col {index} label")
            if first != column["first"] or last != column["last"] or len(data) != column["rows"]:
                mismatches.append(f"{wb.name} col {index} data")

print("SOURCE_MISMATCHES", len(mismatches))
for item in mismatches[:20]:
    print("MISMATCH", item)
print("SUMMARY")
for voltage, short, long_name, count, cols in created:
    print(f"  {voltage}v -> {short} ({long_name}), files {count}, columns {cols}")
