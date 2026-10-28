import win32com.client
app = win32com.client.Dispatch("Origin.ApplicationSI")
app.BeginSession()
try:
    def run(script):
        try:
            app.Execute(script)
        except Exception as e:
            print("ERR", e)
            print(script[:200])
            raise

    run("""
StringArray saBooks;
StringArray saLong;
saBooks.RemoveAll();
saLong.RemoveAll();
doc -ef W {
  saBooks.Add(page.name$);
  saLong.Add(page.longname$);
};
py_nb = saBooks.GetSize();
""")
    n = int(app.LTVar("py_nb"))
    print("count", n)
    for i in range(1, n+1):
        run(f"string py_one$ = saBooks.GetAt({i})$; string py_ln$ = saLong.GetAt({i})$;")
        name = app.LTStr("py_one$")
        longn = app.LTStr("py_ln$")
        run(f"""
range r1 = [{name}]1!col(1);
range r2 = [{name}]1!col(2);
range r3 = [{name}]1!col(3);
py_nc = [{name}]1!wks.ncols;
string py_a$ = r1.lname$;
string py_b$ = r1.unit$;
string py_c$ = r2.lname$;
string py_d$ = r2.unit$;
string py_e$ = r3.lname$;
string py_f$ = r3.unit$;
py_nlay = [{name}]!page.nlayers;
""")
        # wks.ncols via range page may fail; fetch individually if needed
        def S(k):
            return app.LTStr(k)
        try:
            nc = app.LTVar("py_nc")
        except Exception:
            nc = "?"
        try:
            nlay = app.LTVar("py_nlay")
        except Exception:
            nlay = "?"
        print(f"{i:02d} {name} | layers={nlay} ncols={nc} | {S('py_a$')!r} {S('py_b$')!r} | {S('py_c$')!r} {S('py_d$')!r} | {S('py_e$')!r} {S('py_f$')!r} | {longn}")
finally:
    app.EndSession()
