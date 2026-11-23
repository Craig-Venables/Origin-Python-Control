"""Plot one sweep per file with a cloneable Origin template."""
from __future__ import annotations

import shutil
from pathlib import Path

from gui_logic import read_sweep, template_pairs

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "IV+LOGIV(INDEX).otpu"
USER_TEMPLATE_FOLDERS = (
    Path.home() / "Documents" / "OriginLab" / "User Files",
    Path(r"C:\Users\craig\Documents\OriginLab\User Files"),
)


def available_templates():
    """Shipped templates first, then any other .otpu in Origin's User Files."""
    ordered = []
    seen = set()

    def add(path):
        path = Path(path)
        if path.suffix.lower() != ".otpu" or not path.is_file():
            return
        key = path.name.lower()
        if key in seen:
            return
        seen.add(key)
        ordered.append(path)

    if DEFAULT_TEMPLATE.is_file():
        add(DEFAULT_TEMPLATE)
    if TEMPLATE_DIR.is_dir():
        for path in sorted(TEMPLATE_DIR.glob("*.otpu"), key=lambda item: item.name.lower()):
            add(path)
    for folder in USER_TEMPLATE_FOLDERS:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.otpu"), key=lambda item: item.name.lower()):
            add(path)
    return ordered


def _fresh_graph(before):
    import originpro as op

    fresh = [page for page in op.pe.active_folder().pages("g") if page.name not in before]
    if fresh:
        return fresh[-1]
    active = op.find_graph()
    if active is not None and active.name not in before:
        return active
    return None


def _graph_names():
    import originpro as op

    return {page.name for page in op.pe.active_folder().pages("g")}


def clone_graph(sheet, template):
    """Draw the sheet with the template. Copy it into User Files if a path is not enough."""
    import originpro as op

    template = Path(template)
    if not template.is_file():
        raise SystemExit(f"missing template {template}")
    sheet.activate()
    before = _graph_names()
    quoted = template.resolve().as_posix()
    sheet.obj.LT_execute(f'worksheet -pa ? "{quoted}";win -rp %H;')
    graph = _fresh_graph(before)
    if graph is not None:
        return graph
    user = Path(op.path("u"))
    dest = user / template.name
    if dest.resolve() != template.resolve():
        user.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, dest)
        print("TEMPLATE", "copied to", dest)
    sheet.activate()
    before = _graph_names()
    sheet.plot_cloneable(template.stem)
    graph = _fresh_graph(before)
    if graph is None:
        raise SystemExit(
            f"Origin did not plot {template.name}. "
            f"The template name Origin looks up is {template.stem}."
        )
    return graph


def plot_sweeps(paths, template, folder):
    """One workbook and one template graph per sweep. Origin is already connected."""
    import originpro as op
    from origin_session import enter_folder
    from plot_conduction_origin import drop_if_here, set_write_folder

    template = Path(template)
    if not template.is_file():
        raise SystemExit(f"missing template {template}")
    paths = [Path(item) for item in paths]
    active = enter_folder(folder)
    set_write_folder(active)
    pairs = template_pairs([path.stem for path in paths])
    for path, (book_name, graph_name) in zip(paths, pairs):
        voltage, current, time = read_sweep(path)
        drop_if_here(book_name)
        drop_if_here(graph_name)
        book = op.new_book("w", path.name)
        book.name = book_name
        sheet = book[0]
        sheet.from_list(0, voltage, lname="Voltage", units="V", axis="X")
        sheet.from_list(1, current, lname="Current", units="A", axis="Y")
        if time is None:
            print("TIME", path.name, "no Time column")
        else:
            sheet.from_list(2, time, lname="Time", units="T", axis="Y")
        graph = clone_graph(sheet, template)
        graph.name = graph_name
        graph.lname = path.name
        print("GRAPH", graph.name, path.name, "template", template.name)
    print("DONE")
