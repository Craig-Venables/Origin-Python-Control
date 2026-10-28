"""List the workbooks in the folder that contains Book51.

Purpose
    Read-only inventory before combining. Book51 lives in /D114/B/all/.

Input
    The open OriginPro session, with a workbook whose short name is Book51.

Output
    Printed short name, long name, column count, row count, and the long
    name and units of the first columns. Creates and edits nothing.
"""
import originpro as op
op.attach()
op.set_show(True)
path = op.pe.search("Book51", 0)
print("SEARCH", repr(path))
op.pe.cd(path)
fld = op.pe.active_folder()
print("ACTIVE", repr(fld.path))
n = 0
for wb in fld.pages("w"):
    n += 1
    sheets = list(wb)
    shapes = []
    for wks in sheets:
        labels = []
        for c in range(min(wks.cols, 4)):
            labels.append((wks.get_label(c, "L"), wks.get_label(c, "U")))
        shapes.append((wks.cols, wks.rows, labels))
    print(f"{n:02d} {wb.name} | {wb.lname} | {shapes}")
print("TOTAL", n)
