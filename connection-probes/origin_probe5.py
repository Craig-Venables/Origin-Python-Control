import win32com.client
app = win32com.client.Dispatch("Origin.ApplicationSI")
app.BeginSession()
try:
    def run(script):
        try:
            app.Execute(script)
            return True
        except Exception as e:
            print("ERR", script[:180], "->", e)
            return False

    run("StringArray saBooks; saBooks.RemoveAll(); doc -ef W { saBooks.Add(page.name$); }; py_nb = saBooks.GetSize();")
    print("nbooks", app.LTVar("py_nb"))
    for i in range(0, 4):
        ok = run(f"string py_one$ = saBooks.GetAt({i})$;")
        if ok:
            print(i, repr(app.LTStr("py_one$")))
finally:
    app.EndSession()
