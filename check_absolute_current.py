"""Spot-check Absolute Current against Current in the three combined books.

Purpose
    Confirm each combined book has Absolute Current beside Current, and that
    a negative current was stored as a positive value.

Input
    The open OriginPro session, with allcombined, v1p0, and v1p5 present.

Output
    Printed column counts, long names, units, comments, one sample pair,
    and the voltage column types. Read only.
"""
import originpro as op
op.attach()
op.set_show(True)
for name in ("allcombined", "v1p0", "v1p5"):
    wks = op.find_book("w", name)[0]
    print("BOOK", name, "cols", wks.cols)
    shown = 0
    for i in range(wks.cols):
        lname = wks.get_label(i, "L")
        if lname not in ("Voltage", "Current", "Absolute Current", "Time"):
            print(" unexpected", i, lname)
        if lname == "Current" and shown < 2:
            data = wks.to_list(i)
            absdata = wks.to_list(i + 1)
            pair = None
            for a, b in zip(data, absdata):
                if a not in (None, "") and float(a) < 0:
                    pair = (float(a), float(b))
                    break
            if pair is None and data:
                pair = (data[0], absdata[0])
            print(" sample", lname, wks.get_label(i, "U"), "->", wks.get_label(i+1, "L"), wks.get_label(i+1, "U"), "comment", repr(wks.get_label(i+1, "C")), "pair", pair, "types", wks.obj[i].GetType(), wks.obj[i+1].GetType())
            shown += 1
    vtypes = [int(wks.obj[i].GetType()) for i in range(wks.cols) if wks.get_label(i, "L") == "Voltage"]
    print(" voltage types", vtypes[:6], "count", len(vtypes))
print("Book35", op.find_book("w", "Book35")[0].cols)
