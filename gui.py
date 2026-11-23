"""Window for plotting IV sweeps, CF spectra, and pulse tests in Origin.

    py -3 gui.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, ttk

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from template_plot import available_templates

PANELS = (
    ("iv", "IV"),
    ("logiv", "Log IV"),
    ("ohmic", "Ohmic"),
    ("sclc", "SCLC"),
    ("schottky", "Schottky"),
    ("pf", "Poole–Frenkel"),
    ("fn", "Fowler–Nordheim"),
    ("tat", "Trap-assisted tunneling"),
)
MODELS = (
    ("Rs-(Rp || CPE)", "rcpe"),
    ("L-Rs-(Rp || CPE)", "lrcpe"),
    ("Try both", "both"),
)


class Log:
    def __init__(self, widget, root):
        self.widget = widget
        self.root = root

    def write(self, text):
        if not text:
            return
        self.widget.insert("end", text)
        self.widget.see("end")
        self.root.update_idletasks()

    def flush(self):
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.paths = []
        self.connected = False
        self.job = tk.StringVar(value="iv")
        self.origin_mode = tk.StringVar(value="attach")
        self.project = tk.StringVar()
        self.folder = tk.StringVar(value="/PythonPlots/")
        self.model = tk.StringVar(value=MODELS[0][0])
        self.hold = tk.BooleanVar(value=False)
        self.template = tk.StringVar()
        self.panel_vars = {key: tk.BooleanVar(value=True) for key, _label in PANELS}
        self.template_paths = {}
        self._build()
        self._load_templates()
        self._show_options()

    def _build(self):
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)
        root.rowconfigure(5, weight=1)

        jobs = ttk.Frame(root, padding=(8, 8, 8, 0))
        jobs.grid(row=0, column=0, sticky="ew")
        for value, label in (
            ("iv", "IV analysis"),
            ("cf", "CF"),
            ("template", "Quick template"),
            ("endurance", "Endurance"),
            ("retention", "Retention"),
        ):
            ttk.Radiobutton(
                jobs, text=label, value=value, variable=self.job, command=self._show_options
            ).pack(side="left", padx=(0, 12))

        files = ttk.LabelFrame(root, text="Files", padding=8)
        files.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        files.columnconfigure(0, weight=1)
        self.file_list = tk.Listbox(files, height=6)
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(files, command=self.file_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scroll.set)
        buttons = ttk.Frame(files)
        buttons.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(buttons, text="Add files", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="Add folder", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(buttons, text="Remove", command=self.remove_selected).pack(side="left")

        target = ttk.LabelFrame(root, text="Origin", padding=8)
        target.grid(row=2, column=0, sticky="ew", padx=8)
        target.columnconfigure(1, weight=1)
        for column, (value, label) in enumerate(
            (("attach", "Already open"), ("open", "Open this project"), ("new", "New project"))
        ):
            ttk.Radiobutton(
                target,
                text=label,
                value=value,
                variable=self.origin_mode,
                command=self._toggle_project,
            ).grid(row=0, column=column, sticky="w", padx=(0, 12))
        ttk.Label(target, text="Project").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.project_entry = ttk.Entry(target, textvariable=self.project)
        self.project_entry.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        self.project_button = ttk.Button(target, text="Browse", command=self.browse_project)
        self.project_button.grid(row=1, column=2, padx=(6, 0), pady=(6, 0))
        ttk.Label(target, text="Folder").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(target, textvariable=self.folder).grid(row=2, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(
            target,
            text="Project Explorer folder. The window creates it and writes only there.",
        ).grid(row=3, column=1, sticky="w")

        self.options = ttk.LabelFrame(root, text="Options", padding=8)
        self.options.grid(row=3, column=0, sticky="nsew", padx=8, pady=8)
        self.iv_box = ttk.Frame(self.options)
        for index, (key, label) in enumerate(PANELS):
            ttk.Checkbutton(self.iv_box, text=label, variable=self.panel_vars[key]).grid(
                row=index // 4, column=index % 4, sticky="w", padx=(0, 12)
            )
        self.cf_box = ttk.Frame(self.options)
        ttk.Label(self.cf_box, text="Circuit").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            self.cf_box, textvariable=self.model, values=[label for label, _key in MODELS], state="readonly"
        ).grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Checkbutton(
            self.cf_box,
            text="For inductor fits, hold Q and n from the first capacitive file",
            variable=self.hold,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.endurance_box = ttk.Frame(self.options)
        ttk.Label(
            self.endurance_box,
            text="Resistance against cycle. SET and RESET are separate lines. Two or more files also share one comparison graph.",
            wraplength=720,
        ).grid(row=0, column=0, sticky="w")
        self.retention_box = ttk.Frame(self.options)
        ttk.Label(
            self.retention_box,
            text="Resistance against time, on a log time axis. Baseline and the read just after the pulse are marked. Two or more files also share one comparison graph.",
            wraplength=720,
        ).grid(row=0, column=0, sticky="w")
        self.template_box = ttk.Frame(self.options)
        self.template_box.columnconfigure(0, weight=1)
        self.template_menu = ttk.Combobox(self.template_box, textvariable=self.template, state="readonly")
        self.template_menu.grid(row=0, column=0, sticky="ew")
        ttk.Button(self.template_box, text="Browse", command=self.browse_template).grid(
            row=0, column=1, padx=(6, 0)
        )

        actions = ttk.Frame(root, padding=(8, 0, 8, 0))
        actions.grid(row=4, column=0, sticky="ew")
        self.run_button = ttk.Button(actions, text="Run", command=self.run)
        self.run_button.pack(side="left")
        self.save_button = ttk.Button(actions, text="Save", command=self.save, state="disabled")
        self.save_button.pack(side="left", padx=6)
        ttk.Label(actions, text="The project is not saved until you press Save.").pack(side="left", padx=8)

        log_frame = ttk.LabelFrame(root, text="Log", padding=8)
        log_frame.grid(row=5, column=0, sticky="nsew", padx=8, pady=8)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_widget = tk.Text(log_frame, height=10, wrap="word")
        self.log_widget.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_widget.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_widget.configure(yscrollcommand=log_scroll.set)
        self._toggle_project()

    def _show_options(self):
        for box in (self.iv_box, self.cf_box, self.template_box, self.endurance_box, self.retention_box):
            box.grid_forget()
        job = self.job.get()
        if job == "iv":
            self.iv_box.grid(row=0, column=0, sticky="ew")
        elif job == "cf":
            self.cf_box.grid(row=0, column=0, sticky="ew")
        elif job == "endurance":
            self.endurance_box.grid(row=0, column=0, sticky="ew")
        elif job == "retention":
            self.retention_box.grid(row=0, column=0, sticky="ew")
        else:
            self.template_box.grid(row=0, column=0, sticky="ew")

    def _toggle_project(self):
        enabled = self.origin_mode.get() == "open"
        state = "normal" if enabled else "disabled"
        self.project_entry.configure(state=state)
        self.project_button.configure(state=state)

    def _load_templates(self):
        self.template_paths = {}
        labels = []
        for path in available_templates():
            self.template_paths[path.name] = path
            labels.append(path.name)
        self.template_menu.configure(values=labels)
        if labels:
            self.template.set(labels[0])

    def _suffixes(self):
        job = self.job.get()
        if job == "cf":
            return {".csv"}
        if job in {"endurance", "retention"}:
            return {".txt"}
        return {".txt", ".csv", ".dat"}

    def _add_paths(self, paths):
        suffixes = self._suffixes()
        for path in paths:
            path = Path(path)
            if path.suffix.lower() not in suffixes or not path.is_file():
                continue
            text = str(path)
            if text not in self.paths:
                self.paths.append(text)
                self.file_list.insert("end", text)

    def add_files(self):
        job = self.job.get()
        if job == "cf":
            filetypes = [("CF spectra", "*.csv"), ("All files", "*.*")]
        elif job in {"endurance", "retention"}:
            filetypes = [("Pulse files", "*.txt"), ("All files", "*.*")]
        else:
            filetypes = [("Sweeps", "*.txt *.csv *.dat"), ("All files", "*.*")]
        chosen = filedialog.askopenfilenames(filetypes=filetypes)
        self._add_paths(chosen)

    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        paths = sorted(path for path in Path(folder).iterdir() if path.is_file())
        self._add_paths(paths)

    def remove_selected(self):
        selected = list(self.file_list.curselection())
        for index in reversed(selected):
            self.file_list.delete(index)
            del self.paths[index]

    def browse_project(self):
        chosen = filedialog.askopenfilename(
            filetypes=[("Origin project", "*.opju *.opj"), ("All files", "*.*")]
        )
        if chosen:
            self.project.set(chosen)

    def browse_template(self):
        chosen = filedialog.askopenfilename(filetypes=[("Origin template", "*.otpu"), ("All files", "*.*")])
        if not chosen:
            return
        path = Path(chosen)
        self.template_paths[path.name] = path
        labels = list(self.template_menu.cget("values"))
        if path.name not in labels:
            labels.append(path.name)
            self.template_menu.configure(values=labels)
        self.template.set(path.name)

    def log_line(self, text):
        self.log_widget.insert("end", text + "\n")
        self.log_widget.see("end")
        self.root.update_idletasks()

    def run(self):
        self.run_button.configure(state="disabled")
        self.log_widget.delete("1.0", "end")
        stdout, stderr = sys.stdout, sys.stderr
        logged = Log(self.log_widget, self.root)
        sys.stdout = logged
        sys.stderr = logged
        try:
            self._run()
            self.connected = True
            self.save_button.configure(state="normal")
            self.log_line("The project was not saved.")
        except SystemExit as exc:
            message = exc.code if isinstance(exc.code, str) and exc.code else "Stopped."
            self.log_line(str(message))
        except Exception:
            self.log_line(traceback.format_exc())
        finally:
            sys.stdout = stdout
            sys.stderr = stderr
            self.run_button.configure(state="normal")

    def _run(self):
        from origin_session import connect

        if not self.paths:
            raise SystemExit("Add at least one file.")
        mode = self.origin_mode.get()
        connect(mode, self.project.get().strip() or None)
        folder = self.folder.get()
        job = self.job.get()
        if job == "iv":
            import conduction_origin

            keys = [key for key, _label in PANELS if self.panel_vars[key].get()]
            conduction_origin.run(self.paths, folder, keys)
        elif job == "cf":
            from origin_session import enter_folder
            import fit_cf_all

            model = dict(MODELS)[self.model.get()]
            enter_folder(folder)
            fit_cf_all.run_paths(self.paths, model=model, hold_cpe=self.hold.get())
        elif job in {"endurance", "retention"}:
            import pulse_origin

            pulse_origin.run(self.paths, folder, job)
        else:
            import template_plot

            name = self.template.get()
            path = self.template_paths.get(name)
            if path is None:
                raise SystemExit("Choose a template.")
            template_plot.plot_sweeps(self.paths, path, folder)

    def save(self):
        from origin_session import save_project

        if not self.connected:
            self.log_line("Run a plot before saving.")
            return
        target = ""
        try:
            import originpro as op

            if self.origin_mode.get() == "new" or not op.path("p"):
                target = filedialog.asksaveasfilename(
                    defaultextension=".opju",
                    filetypes=[("Origin project", "*.opju")],
                )
                if not target:
                    return
            save_project(target)
        except ValueError:
            target = filedialog.asksaveasfilename(
                defaultextension=".opju",
                filetypes=[("Origin project", "*.opju")],
            )
            if not target:
                return
            save_project(target)
        except SystemExit as exc:
            self.log_line(str(exc.code if isinstance(exc.code, str) else exc))
            return
        except Exception:
            self.log_line(traceback.format_exc())
            return
        self.log_line("Saved" + (f" {target}" if target else "."))


def main():
    root = tk.Tk()
    root.title("Origin plots")
    root.geometry("780x700")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
