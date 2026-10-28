import win32com.client
app = win32com.client.Dispatch("Origin.ApplicationSI")
app.BeginSession()
try:
    def run(script, label=None):
        print("RUN", label or script[:120])
        try:
            app.Execute(script)
            print("  ok")
        except Exception as e:
            print("  ERR", e)

    def svar(name):
        try:
            v = app.LTStr(name)
            print(name, "len", len(v))
            print(v[:4000])
        except Exception as e:
            print(name, "STRFAIL", e)
    def nvar(name):
        try:
            print(name, app.LTVar(name))
        except Exception as e:
            print(name, "NUMFAIL", e)

    run('py_nall = 0; doc -e W { py_nall = py_nall + 1; };', 'count all W')
    nvar('py_nall')
    run('py_nf = 0; doc -ef W { py_nf = py_nf + 1; };', 'count ef W')
    nvar('py_nf')
    run('py_ncf = 0; doc -cf W { py_ncf = py_ncf + 1; };', 'count cf W')
    nvar('py_ncf')
    run(r'''string py_inv$ = ""; doc -ef W { py_inv$ = py_inv$ + page.name$ + "|" + page.longname$ + "|" + $(wks.ncols) + "|" + $(page.nlayers) + ";;"; };''', 'inventory ef')
    svar('py_inv$')
finally:
    app.EndSession()
    print('session closed')
