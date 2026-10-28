import originpro as op
op.attach()
op.set_show(True)
for name in ("Book35", "v1p0"):
    wks = op.find_book("w", name)[0]
    types = [wks.obj[i].GetType() for i in range(wks.cols)]
    print(name, types[:6], "L", [wks.get_label(i,"L") for i in range(3)], "C", [wks.get_label(i,"C") for i in range(3)])
