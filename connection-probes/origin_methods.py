import win32com.client
app = win32com.client.Dispatch("Origin.ApplicationSI")
ti = app._oleobj_.GetTypeInfo()
attr = ti.GetTypeAttr()
print("funcs", attr.cFuncs, "vars", attr.cVars)
names = []
for i in range(attr.cFuncs):
    fd = ti.GetFuncDesc(i)
    n = ti.GetNames(fd.memid)
    names.append(n[0])
for n in sorted(set(names)):
    print(n)
