import win32com.client
app = win32com.client.Dispatch("Origin.ApplicationSI")
app.BeginSession()
try:
    def run(script):
        try:
            app.Execute(script)
            return True
        except Exception as e:
            print("ERR", e)
            return False
    def S(n):
        try:
            return app.LTStr(n)
        except Exception as e:
            return f"<err {e}>"
    def N(n):
        try:
            return app.LTVar(n)
        except Exception as e:
            return f"<err {e}>"

    for nm in ("Book51", "Book51A", "Book35", "Book35A", "Book70"):
        run(f"py_ex = exist({nm});")
        print("exist", nm, N("py_ex"))

    print("activate Book51", run("win -a Book51;"))
    run("string py_now$ = page.name$;")
    print("now", S("py_now$"))

    # folder probes
    probes = [
        'string py_f1$ = page.folder$;',
        'string py_f2$ = pe_path$;',
        'string py_f3$ = path$;',
    ]
    for p in probes:
        print("PROBE", p, run(p))
    for n in ("py_f1$","py_f2$","py_f3$"):
        print(n, repr(S(n)))

    run("py_nf = 0; doc -ef W { py_nf = py_nf + 1; }; string py_after$ = page.name$;")
    print("ef count after activate", N("py_nf"), "left on", S("py_after$"))
finally:
    app.EndSession()
