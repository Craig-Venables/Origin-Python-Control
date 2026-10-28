"""Print column plot types for Book35 and v1p0.

Purpose
    Show GetType() for the first columns. Voltage on an original sweep and
    on v1p0 is 3 (X). Current and time are 0 (Y). LabTalk wks.col.type is
    not a reliable check on these sheets.

Input
    The open OriginPro session, with Book35 and v1p0 present.

Output
    One printed line per book: type codes, long names, and comments.
    Read only.
"""
import originpro as op
op.attach()
op.set_show(True)
for name in ("Book35", "v1p0"):
    wks = op.find_book("w", name)[0]
    types = [wks.obj[i].GetType() for i in range(wks.cols)]
    print(name, types[:6], "L", [wks.get_label(i,"L") for i in range(3)], "C", [wks.get_label(i,"C") for i in range(3)])
