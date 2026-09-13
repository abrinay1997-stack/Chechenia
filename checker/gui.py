from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .engine import load_config, load_emails, run_checks, write_results

ROOT = Path(__file__).resolve().parent.parent
BG = "#100101"
PANEL = "#1a1010"
FG = "#f5f0ea"
ACCENT = "#FF5100"
OK = "#3DDC97"
BAD = "#FF5D73"
MUTED = "#9A8F86"


class CheckerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Chechenia — checker de tu app")
        self.root.geometry("920x640")
        self.root.configure(bg=BG)
        self.stop_flag = False
        self.running = False
        self.emails_path = ROOT / "data" / "emails.example.txt"
        self.config_path = ROOT / "config.json"
        if not self.config_path.exists() and (ROOT / "config.example.json").exists():
            self.config_path.write_text(
                (ROOT / "config.example.json").read_text(encoding="utf-8"), encoding="utf-8"
            )

        self._build()
        self._load_config_into_form()

    def _build(self) -> None:
        pad = {"padx": 14, "pady": 8}
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", **pad)
        tk.Label(
            header,
            text="CHECHENIA",
            fg=ACCENT,
            bg=BG,
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Comprueba si un email ya existe en TU aplicación. No sirve contra servicios de terceros.",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        form = tk.Frame(self.root, bg=PANEL)
        form.pack(fill="x", padx=14, pady=6)

        self.api_var = tk.StringVar()
        self.path_var = tk.StringVar()
        self.key_var = tk.StringVar()
        self.workers_var = tk.StringVar(value="8")
        self.file_var = tk.StringVar(value=str(self.emails_path))

        self._row(form, 0, "API base", self.api_var)
        self._row(form, 1, "Ruta exists", self.path_var)
        self._row(form, 2, "Admin key", self.key_var, show="*")
        self._row(form, 3, "Workers", self.workers_var)
        self._row(form, 4, "Archivo emails", self.file_var)

        btns = tk.Frame(form, bg=PANEL)
        btns.grid(row=5, column=0, columnspan=3, sticky="w", padx=10, pady=10)
        self._btn(btns, "Cargar lista", self.pick_file).pack(side="left", padx=4)
        self._btn(btns, "Iniciar", self.start, accent=True).pack(side="left", padx=4)
        self._btn(btns, "Detener", self.stop).pack(side="left", padx=4)
        self._btn(btns, "Guardar config", self.save_config).pack(side="left", padx=4)

        stats = tk.Frame(self.root, bg=BG)
        stats.pack(fill="x", padx=14, pady=8)
        self.lbl_reg = self._stat(stats, "REGISTRADOS", OK)
        self.lbl_ava = self._stat(stats, "LIBRES", ACCENT)
        self.lbl_inv = self._stat(stats, "INVALIDOS", MUTED)
        self.lbl_err = self._stat(stats, "ERRORES", BAD)

        log_wrap = tk.Frame(self.root, bg=PANEL)
        log_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.log = tk.Text(
            log_wrap,
            bg="#140b0b",
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=("Consolas", 10),
            wrap="none",
        )
        scroll = ttk.Scrollbar(log_wrap, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.log.tag_config("registered", foreground=OK)
        self.log.tag_config("available", foreground=ACCENT)
        self.log.tag_config("invalid", foreground=MUTED)
        self.log.tag_config("error", foreground=BAD)
        self.log.tag_config("blocked", foreground=BAD)

    def _row(self, parent, row, label, var, show=None) -> None:
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, width=16, anchor="w").grid(
            row=row, column=0, padx=10, pady=6, sticky="w"
        )
        entry = tk.Entry(
            parent,
            textvariable=var,
            bg="#140b0b",
            fg=FG,
            insertbackground=FG,
            relief="flat",
            show=show or "",
        )
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=10, pady=6)
        parent.grid_columnconfigure(1, weight=1)

    def _btn(self, parent, text, cmd, accent=False) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=ACCENT if accent else "#2a1a14",
            fg="#100101" if accent else FG,
            activebackground=ACCENT,
            relief="flat",
            padx=12,
            pady=6,
            font=("Segoe UI", 9, "bold"),
        )

    def _stat(self, parent, title, color) -> tk.Label:
        box = tk.Frame(parent, bg=PANEL)
        box.pack(side="left", expand=True, fill="x", padx=6)
        tk.Label(box, text=title, bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack()
        lbl = tk.Label(box, text="0", bg=PANEL, fg=color, font=("Segoe UI", 18, "bold"))
        lbl.pack()
        return lbl

    def _load_config_into_form(self) -> None:
        try:
            cfg = load_config(self.config_path)
        except FileNotFoundError:
            cfg = load_config(ROOT / "config.example.json")
        self.api_var.set(cfg["api_base_url"])
        self.path_var.set(cfg["exists_path"])
        self.key_var.set(cfg["admin_key"])
        self.workers_var.set(str(cfg["workers"]))

    def current_cfg(self) -> dict:
        return {
            "api_base_url": self.api_var.get().strip().rstrip("/"),
            "exists_path": self.path_var.get().strip() or "/admin/users/exists",
            "admin_key": self.key_var.get().strip(),
            "timeout_sec": 12,
            "workers": max(1, min(32, int(self.workers_var.get() or 8))),
            "delay_ms": 0,
        }

    def save_config(self) -> None:
        self.config_path.write_text(json.dumps(self.current_cfg(), indent=2), encoding="utf-8")
        messagebox.showinfo("Chechenia", f"Config guardada en {self.config_path}")

    def pick_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Lista de emails",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if path:
            self.file_var.set(path)

    def start(self) -> None:
        if self.running:
            return
        path = Path(self.file_var.get())
        if not path.exists():
            messagebox.showerror("Chechenia", "No encuentro el archivo de emails.")
            return
        try:
            emails = load_emails(path)
        except OSError as exc:
            messagebox.showerror("Chechenia", str(exc))
            return
        if not emails:
            messagebox.showerror("Chechenia", "La lista está vacía.")
            return

        self.running = True
        self.stop_flag = False
        self.log.delete("1.0", "end")
        self._set_stats(0, 0, 0, 0)
        cfg = self.current_cfg()
        threading.Thread(target=self._worker, args=(emails, cfg), daemon=True).start()

    def stop(self) -> None:
        self.stop_flag = True

    def _worker(self, emails, cfg) -> None:
        results, _ = run_checks(
            emails,
            cfg,
            on_progress=lambda result, stats: self.root.after(0, self._on_progress, result, stats),
            should_stop=lambda: self.stop_flag,
        )
        out = ROOT / "results"
        write_results(results, out)
        self.running = False
        self.root.after(
            0,
            lambda: self._append("\nGuardado en results/registered.txt y results/available.txt\n", "available"),
        )

    def _on_progress(self, result, stats) -> None:
        self._set_stats(stats.registered, stats.available, stats.invalid, stats.errors + stats.blocked)
        line = f"{result.status.upper():12} {result.email:40} {result.detail} {result.ms}ms\n"
        self._append(line, result.status)

    def _set_stats(self, reg, ava, inv, err) -> None:
        self.lbl_reg.config(text=str(reg))
        self.lbl_ava.config(text=str(ava))
        self.lbl_inv.config(text=str(inv))
        self.lbl_err.config(text=str(err))

    def _append(self, text: str, tag: str) -> None:
        self.log.insert("end", text, tag)
        self.log.see("end")


def main() -> None:
    root = tk.Tk()
    CheckerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
