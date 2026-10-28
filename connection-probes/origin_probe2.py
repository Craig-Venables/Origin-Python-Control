import traceback
import win32com.client
app = win32com.client.Dispatch("Origin.ApplicationSI")
print("begin")
app.BeginSession()
try:
    app.Execute('string py_probe$ = page.name$;')
    for key in ("py_probe$", "py_probe"):
        try:
            print("LTStr", key, repr(app.LTStr(key)))
        except Exception as e:
            print("LTStr fail", key, e)
    app.Execute('string py_path$ = pe_path$;')
    print("path", repr(app.LTStr("py_path$")))
    app.Execute('py_ncols = wks.ncols;')
    print("ncols", app.LTVar("py_ncols"))
    app.Execute('string py_l1$ = wks.col1.lname$; string py_u1$ = wks.col1.units$; string py_l2$ = wks.col2.lname$; string py_u2$ = wks.col2.units$; string py_l3$ = wks.col3.lname$; string py_u3$ = wks.col3.units$;')
    for k in ("py_l1$","py_u1$","py_l2$","py_u2$","py_l3$","py_u3$"):
        print(k, repr(app.LTStr(k)))
    app.Execute('string py_ln$ = page.longname$; string py_sn$ = page.name$;')
    print("long", repr(app.LTStr("py_ln$")))
    print("short", repr(app.LTStr("py_sn$")))
finally:
    app.EndSession()
    print("end session")
