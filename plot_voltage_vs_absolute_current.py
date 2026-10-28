"""One graph per combined workbook: every sweep, voltage vs absolute current.

Does not change worksheet columns and does not save the project.
"""
import originpro as op

op.attach()
op.set_show(True)

FOLDER = "/D114/B/all/"
op.pe.cd(FOLDER)
if op.pe.active_folder().path != FOLDER:
    raise SystemExit(f"refusing to plot, folder is {op.pe.active_folder().path!r}")

JOBS = (
    ("allcombined", "gAbsAll", "allcombined |I| vs V"),
    ("v1p0", "gAbs10", "combined 1.0v |I| vs V"),
    ("v1p5", "gAbs15", "combined 1.5v |I| vs V"),
)


def label(wks, index, kind):
    try:
        return wks.get_label(index, kind) or ""
    except Exception:
        return ""


def pairs(wks):
    names = [label(wks, i, "L") for i in range(wks.cols)]
    found = []
    for index, name in enumerate(names):
        if name.strip().lower() != "voltage":
            continue
        for follow in range(index + 1, len(names)):
            follow_name = names[follow].strip().lower()
            if follow_name == "voltage":
                break
            if follow_name == "absolute current":
                found.append((index, follow))
                break
    return found


def trace_name(wks, y_index):
    source = label(wks, y_index, "Source")
    if source:
        return source
    comment = label(wks, y_index, "C")
    if comment:
        return comment
    return f"column {y_index + 1}"


for book_name, graph_name, long_name in JOBS:
    if op.find_graph(graph_name) is not None:
        raise SystemExit(f"{graph_name} already exists")
    wb = op.find_book("w", book_name)
    if wb is None:
        raise SystemExit(f"missing workbook {book_name}")
    wks = wb[0]
    xy = pairs(wks)
    if not xy:
        raise SystemExit(f"no voltage / absolute-current pairs in {book_name}")
    graph = op.new_graph(long_name)
    graph.name = graph_name
    layer = graph[0]
    names = []
    for x_index, y_index in xy:
        plot = layer.add_plot(wks, coly=y_index, colx=x_index, type="l")
        if plot is None:
            raise SystemExit(f"failed to add a trace from {book_name}")
        names.append(trace_name(wks, y_index))
    plots = list(layer.plot_list())
    for index, plot in enumerate(plots):
        plot.set_cmd(f"-c {(index % 16) + 1}")
    layer.rescale()
    legend = "\\n".join(f"\\l({index}) {name}" for index, name in enumerate(names, 1))
    for command in (
        f'legend.text$ = "{legend}";',
        'label -xb "Voltage (V)";',
        'label -yl "Absolute Current (A)";',
    ):
        try:
            layer.obj.LT_execute(command)
        except Exception as error:
            print("LABEL_SKIP", graph_name, error)
    print(
        "GRAPH",
        graph.name,
        graph.lname,
        "traces",
        len(plots),
        "folder",
        op.pe.search(graph.name, 0),
    )
