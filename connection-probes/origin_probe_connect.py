import traceback
import win32com.client
print("dispatching ApplicationSI")
try:
    app = win32com.client.Dispatch("Origin.ApplicationSI")
except Exception:
    traceback.print_exc()
    raise SystemExit(2)
print("type", type(app))
print("visible", app.Visible)
try:
    path = app.LT_execute("pe_path$")
    print("LT pe_path", repr(path))
except Exception:
    traceback.print_exc()
try:
    name = app.LT_execute("page.name$")
    print("LT page", repr(name))
except Exception:
    traceback.print_exc()
