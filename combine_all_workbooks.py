"""Copy every workbook in /D114/B/all/ into one new workbook.

Purpose
    Side-by-side copy of the D114 sweep books. Each source keeps voltage,
    current, and time together. Long names and units are copied as they are.

Input
    The open OriginPro session, with Project Explorer able to open
    /D114/B/all/. Every workbook in that folder is a source.

Output
    A new workbook in that folder, long name "all combined". Origin stores
    the short name as allcombined. A Source parameter row holds each source
    book's long name. Prints a label check and whether source books still
    match the values that were read. Does not save the project and does not
    edit the source books.
"""
import math
import originpro as op

op.attach()
op.set_show(True)

FOLDER = "/D114/B/all/"
op.pe.cd(FOLDER)
active = op.pe.active_folder().path
print("ACTIVE", repr(active))
if active != FOLDER:
    raise SystemExit(f"refusing to write, active folder is {active!r}")


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


sources = []
for wb in op.pe.active_folder().pages("w"):
    sheets = []
    for wks in wb:
        columns = []
        for index in range(wks.cols):
            data = [cell_value(item) for item in wks.to_list(index)]
            columns.append(
                {
                    "lname": wks.get_label(index, "L") or "",
                    "units": wks.get_label(index, "U") or "",
                    "comments": wks.get_label(index, "C") or "",
                    "rows": wks.rows,
                    "data": data,
                    "first": data[0] if data else None,
                    "last": data[-1] if data else None,
                }
            )
        sheets.append({"name": wks.name, "columns": columns})
    sources.append({"name": wb.name, "lname": wb.lname or "", "sheets": sheets})

print("SOURCES", len(sources))
if not sources:
    raise SystemExit("no workbooks in folder")

taken = {item["name"] for item in sources}
if "all_combined" in taken:
    raise SystemExit("all_combined already exists; leaving it untouched")

dest_wb = op.new_book("w", "all combined")
dest_wb.name = "all_combined"
dest = dest_wb[0]
print("DEST", dest_wb.name, dest_wb.lname, "folder", op.pe.search(dest_wb.name, 0))

column_index = 0
for source in sources:
    for sheet in source["sheets"]:
        for column in sheet["columns"]:
            dest.from_list(
                column_index,
                column["data"],
                lname=column["lname"],
                units=column["units"],
                comments=column["comments"],
            )
            dest.set_label(column_index, source["lname"] or source["name"], "Source")
            column_index += 1

print("WROTE", column_index, "columns")

# Confirm the new sheet and that source labels and endpoints were not changed.
dest_lnames = [dest.get_label(i, "L") for i in range(dest.cols)]
dest_units = [dest.get_label(i, "U") for i in range(dest.cols)]
expected_lnames = [
    column["lname"]
    for source in sources
    for sheet in source["sheets"]
    for column in sheet["columns"]
]
expected_units = [
    column["units"]
    for source in sources
    for sheet in source["sheets"]
    for column in sheet["columns"]
]
print("LABELS_MATCH", dest_lnames == expected_lnames)
print("UNITS_MATCH", dest_units == expected_units)
print("DEST_COLS", dest.cols, "DEST_ROWS", dest.rows)

mismatches = []
by_name = {item["name"]: item for item in sources}
seen = set()
for wb in op.pe.active_folder().pages("w"):
    if wb.name == dest_wb.name:
        continue
    seen.add(wb.name)
    original = by_name.get(wb.name)
    if original is None:
        mismatches.append(f"unexpected book {wb.name}")
        continue
    sheets = list(wb)
    if len(sheets) != len(original["sheets"]):
        mismatches.append(f"{wb.name} sheet count changed")
        continue
    for sheet, wks in zip(original["sheets"], sheets):
        if wks.cols != len(sheet["columns"]):
            mismatches.append(f"{wb.name} col count changed")
            continue
        for index, column in enumerate(sheet["columns"]):
            lname = wks.get_label(index, "L") or ""
            units = wks.get_label(index, "U") or ""
            data = [cell_value(item) for item in wks.to_list(index)]
            first = data[0] if data else None
            last = data[-1] if data else None
            if lname != column["lname"] or units != column["units"]:
                mismatches.append(f"{wb.name} col {index} label changed")
            if first != column["first"] or last != column["last"] or len(data) != len(column["data"]):
                mismatches.append(f"{wb.name} col {index} data changed")

if seen != set(by_name):
    mismatches.append(f"missing sources {set(by_name) - seen}")

print("SOURCE_MISMATCHES", len(mismatches))
for item in mismatches[:20]:
    print("MISMATCH", item)

# Spot-check the first triplet against Book35.
first = sources[0]
print(
    "FIRST_TRIPLET",
    dest.get_label(0, "L"),
    dest.get_label(0, "U"),
    dest.get_label(1, "L"),
    dest.get_label(1, "U"),
    dest.get_label(2, "L"),
    dest.get_label(2, "U"),
    "from",
    first["lname"],
)
print("DONE", dest_wb.name, "sources", len(sources), "columns", dest.cols)
