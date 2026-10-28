import win32com.client
app = win32com.client.Dispatch("Origin.ApplicationSI")
app.BeginSession()
try:
    def run(script):
        print("RUN", script)
        try:
            app.Execute(script)
            print("  ok")
        except Exception as e:
            print("  ERR", e)

    def show(name):
        try:
            if name.endswith("$") or "str" in name:
                print(name, repr(app.LTStr(name)))
            else:
                print(name, app.LTVar(name))
        except Exception as e:
            try:
                print(name, "STR", repr(app.LTStr(name)))
            except Exception as e2:
                print(name, "FAIL", e, e2)

    tests = [
        'string py_u$ = wks.col1.unit$;',
        'string py_u2$ = wks.col1.units$;',
        'string py_lab$ = col(1)[U]$;',
        'string py_l2$ = col(2)[L]$;',
        'string py_u2b$ = col(2)[U]$;',
        'string py_l3$ = col(3)[L]$;',
        'string py_u3$ = col(3)[U]$;',
        'string py_c1$ = col(1)[C]$;',
        'string py_c2$ = col(2)[C]$;',
        'string py_c3$ = col(3)[C]$;',
        'string py_fold$ = page.folder$;',
        'py_nl = wks.labels;',
        'py_ncols = wks.ncols;',
    ]
    for t in tests:
        run(t)
    for n in ["py_u$","py_u2$","py_lab$","py_l2$","py_u2b$","py_l3$","py_u3$","py_c1$","py_c2$","py_c3$","py_fold$","py_nl","py_ncols"]:
        show(n)
finally:
    app.EndSession()
