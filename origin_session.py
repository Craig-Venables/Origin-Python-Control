"""Attach to Origin, open a project, or start a new one, then enter a folder.

originpro is imported inside the functions so importing this module does
not start Origin.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from gui_logic import normalize_folder

_NO_WINDOW = 0x08000000


def origin_is_running():
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Origin64.exe", "/NH"],
            text=True,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return "Origin64.exe" in output


def connect(mode, project=None):
    """Join an Origin session.

    mode is "attach", "open", or "new". Opening a file and starting a new
    project ask before discarding an unsaved project. This never calls
    op.exit().
    """
    import originpro as op

    choice = str(mode).lower()
    if choice == "attach":
        if not origin_is_running():
            raise SystemExit(
                "Origin is not open. Start Origin, or choose a project file, or start a new project."
            )
        op.attach()
    elif choice == "open":
        if not project:
            raise SystemExit("Choose an Origin project file.")
        path = Path(project)
        if not path.is_file():
            raise SystemExit(f"missing {path}")
        _ensure_origin(op)
        if not op.open(str(path), asksave=True):
            raise SystemExit(f"Could not open {path}")
    elif choice == "new":
        _ensure_origin(op)
        op.new(asksave=True)
    else:
        raise SystemExit(f"unknown Origin mode {choice}")
    op.set_show(True)
    return op


def _ensure_origin(op):
    if origin_is_running():
        op.attach()
    else:
        op.set_show(True)


def enter_folder(folder):
    """Create each part of the Project Explorer path and move there.

    Refuses to continue when the active folder is anything else.
    """
    import originpro as op

    try:
        wanted = normalize_folder(folder).rstrip("/")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    parts = [part for part in wanted.split("/") if part]
    op.pe.cd("/")
    built = ""
    for part in parts:
        parent = built + "/" if built else "/"
        op.pe.cd(parent)
        op.pe.mkdir(part, True)
        built = built + "/" + part
        op.pe.cd(built + "/")
    active = op.pe.active_folder().path.replace("\\", "/").rstrip("/")
    if active.lower() != wanted.lower():
        raise SystemExit(f"refusing to write, active folder is {active!r}")
    print("FOLDER", active)
    return active


def save_project(file=""):
    import originpro as op

    return op.save(file or "")
