"""RoVibe MCP Installer."""

import sys
import threading
import customtkinter as ctk
from installer_logic import (
    find_studio_plugins, is_studio_running,
    claude_desktop_detected, cursor_detected, claude_code_detected,
    run_install,
)

# Palette
BG = "#0e0e0e"
SURFACE = "#161616"
BORDER = "#252525"
ACCENT = "#2d57fc"
ACCENT_DIM = "#1a3ab0"
TEXT = "#e0e0e0"
MUTED = "#585858"
SUCCESS = "#3dbf5e"
ERROR = "#d44"
WARN = "#c90"

W = 400
H = 440
PAD = 20

FONT = "Segoe UI"
MONO = "Consolas"


class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        self.overrideredirect(True)
        self.geometry(f"{W}x{H}")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - W) // 2
        y = (self.winfo_screenheight() - H) // 2
        self.geometry(f"{W}x{H}+{x}+{y}")

        # Custom titlebar
        self._drag_x = 0
        self._drag_y = 0
        tb = ctk.CTkFrame(self, fg_color=SURFACE, height=36, corner_radius=0)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tb.bind("<Button-1>", self._start_drag)
        tb.bind("<B1-Motion>", self._do_drag)

        title_lbl = ctk.CTkLabel(
            tb, text="RoVibe Installer", text_color=MUTED,
            font=ctk.CTkFont(family=FONT, size=12),
        )
        title_lbl.pack(side="left", padx=12)
        title_lbl.bind("<Button-1>", self._start_drag)
        title_lbl.bind("<B1-Motion>", self._do_drag)

        close_btn = ctk.CTkButton(
            tb, text="\u00d7", width=36, height=36, corner_radius=0,
            fg_color="transparent", hover_color="#ff4444",
            text_color=MUTED, font=ctk.CTkFont(size=16),
            command=self.destroy,
        )
        close_btn.pack(side="right")

        # Border line under titlebar
        ctk.CTkFrame(self, fg_color=BORDER, height=1, corner_radius=0).pack(fill="x")

        # Main content area
        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.pack(fill="both", expand=True)

        self.step_rows = {}
        self.detection = {"studio": False, "studio_running": False, "claude": False, "cursor": False, "claude_code": False}
        self._detect_labels = {}
        self._opts = {}

        # Show main UI immediately with "checking..." placeholders
        self._show_main_skeleton()

        # Detect each item in background, update UI as each finishes
        threading.Thread(target=self._run_detection, daemon=True).start()

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.winfo_x()
        self._drag_y = e.y_root - self.winfo_y()

    def _do_drag(self, e):
        self.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _clear(self):
        for w in self.main.winfo_children():
            w.destroy()

    def _lbl(self, parent, text, size=12, color=TEXT, weight="normal", **kw):
        return ctk.CTkLabel(
            parent, text=text, text_color=color,
            font=ctk.CTkFont(family=FONT, size=size, weight=weight), **kw,
        )

    def _div(self, parent):
        ctk.CTkFrame(parent, fg_color=BORDER, height=1, corner_radius=0).pack(fill="x", padx=PAD)

    # -- Main Screen (shown instantly) --

    def _show_main_skeleton(self):
        d = self.detection

        # Header
        hdr = ctk.CTkFrame(self.main, fg_color=BG)
        hdr.pack(fill="x", padx=PAD, pady=(16, 0))
        self._lbl(hdr, "RoVibe", size=22, weight="bold", color="#fff").pack(side="left")
        self._lbl(hdr, "MCP", size=12, color=MUTED).pack(side="left", padx=(8, 0), pady=(6, 0))

        self._div(self.main)

        # Detection results (all show "Checking..." initially)
        det = ctk.CTkFrame(self.main, fg_color=BG)
        det.pack(fill="x", padx=PAD, pady=(12, 0))
        self._lbl(det, "STATUS", size=9, color=MUTED).pack(anchor="w")

        self._detect_labels["studio"] = self._status_row(det, "Roblox Studio")
        self._studio_warn = self._lbl(det, "  Will be closed during install", size=10, color=WARN)
        # Hidden by default
        self._detect_labels["claude"] = self._status_row(det, "Claude Desktop")
        self._detect_labels["cursor"] = self._status_row(det, "Cursor")
        self._detect_labels["claude_code"] = self._status_row(det, "Claude Code CLI")

        # Configure checkboxes
        self._div(self.main)
        opts = ctk.CTkFrame(self.main, fg_color=BG)
        opts.pack(fill="x", padx=PAD, pady=(12, 0))
        self._lbl(opts, "CONFIGURE", size=9, color=MUTED).pack(anchor="w")

        self._opts["claude"] = {"var": ctk.BooleanVar(value=False), "frame": None, "cb": None}
        self._opts["cursor"] = {"var": ctk.BooleanVar(value=False), "frame": None, "cb": None}
        self._opts["claude_code"] = {"var": ctk.BooleanVar(value=False), "frame": None, "cb": None}

        self._opts["claude"]["frame"], self._opts["claude"]["cb"] = self._check_row(opts, "Claude Desktop", self._opts["claude"]["var"], disabled=True)
        self._opts["cursor"]["frame"], self._opts["cursor"]["cb"] = self._check_row(opts, "Cursor", self._opts["cursor"]["var"], disabled=True)
        self._opts["claude_code"]["frame"], self._opts["claude_code"]["cb"] = self._check_row(opts, "Claude Code CLI", self._opts["claude_code"]["var"], disabled=True)

        # Spacer
        ctk.CTkFrame(self.main, fg_color="transparent").pack(fill="both", expand=True)

        # Studio required error (hidden initially)
        self._bot = ctk.CTkFrame(self.main, fg_color=BG)
        self._bot.pack(fill="x", padx=PAD, pady=(0, PAD))

        self._studio_err_lbl = self._lbl(self._bot, "Roblox Studio is required", size=10, color=ERROR)
        # hidden initially

        self.install_btn = ctk.CTkButton(
            self._bot, text="Install", height=38,
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_DIM, text_color="#fff",
            corner_radius=6, command=self._on_install,
            state="disabled",
        )
        self.install_btn.pack(fill="x")

    def _run_detection(self):
        # Detect each item individually and update UI immediately
        plugins = find_studio_plugins()
        studio_ok = plugins is not None
        self.detection["studio"] = studio_ok
        self.after(0, lambda: self._update_detect("studio", studio_ok))

        if studio_ok:
            running = is_studio_running()
            self.detection["studio_running"] = running
            self.after(0, lambda: self._show_studio_warn(running))

        claude_ok = claude_desktop_detected()
        self.detection["claude"] = claude_ok
        self.after(0, lambda: self._update_detect("claude", claude_ok))

        cursor_ok = cursor_detected()
        self.detection["cursor"] = cursor_ok
        self.after(0, lambda: self._update_detect("cursor", cursor_ok))

        cc_ok = claude_code_detected()
        self.detection["claude_code"] = cc_ok
        self.after(0, lambda: self._update_detect("claude_code", cc_ok))

        # Enable install button if studio found
        self.after(0, self._detection_done)

    def _update_detect(self, key, ok):
        """Update a single detection row from checking -> result."""
        if key not in self._detect_labels:
            return
        dot_lbl, status_lbl = self._detect_labels[key]
        dot = "\u25cf" if ok else "\u25cb"
        color = SUCCESS if ok else MUTED
        dot_lbl.configure(text=dot, text_color=color)
        status_lbl.configure(text="Detected" if ok else "Not detected", text_color=color)

        # Update matching checkbox if exists
        if key in self._opts:
            opt = self._opts[key]
            if ok:
                opt["var"].set(True)
                opt["cb"].configure(state="normal", text_color=TEXT)
            else:
                opt["var"].set(False)
                opt["cb"].configure(state="disabled", text_color=MUTED)

    def _show_studio_warn(self, running):
        if running:
            self._studio_warn.pack(anchor="w")
        else:
            self._studio_warn.pack_forget()

    def _detection_done(self):
        if self.detection["studio"]:
            self.install_btn.configure(state="normal")
        else:
            self._studio_err_lbl.pack(pady=(0, 6))

    def _status_row(self, parent, name):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=22)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        dot_lbl = self._lbl(row, "\u25cb", size=7, color=MUTED)
        dot_lbl.pack(side="left", padx=(2, 6))

        self._lbl(row, name, size=12, color=MUTED).pack(side="left")

        status_lbl = self._lbl(row, "Checking...", size=10, color=MUTED)
        status_lbl.pack(side="right")

        return (dot_lbl, status_lbl)

    def _check_row(self, parent, name, var, disabled):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=26)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)
        cb = ctk.CTkCheckBox(
            row, text=name, variable=var,
            font=ctk.CTkFont(family=FONT, size=12),
            text_color=MUTED if disabled else TEXT,
            fg_color=ACCENT, hover_color=ACCENT_DIM,
            border_color=BORDER, checkmark_color="#fff",
            corner_radius=3, border_width=2, height=18, width=18,
        )
        cb.pack(side="left", padx=2)
        if disabled:
            cb.configure(state="disabled")
            var.set(False)
        return row, cb

    # -- Installing --

    def _on_install(self):
        self.install_btn.configure(state="disabled", text="Installing...")
        self._clear()

        hdr = ctk.CTkFrame(self.main, fg_color=BG)
        hdr.pack(fill="x", padx=PAD, pady=(16, 0))
        self._lbl(hdr, "Installing", size=18, weight="bold", color="#fff").pack(side="left")

        self._div(self.main)

        sf = ctk.CTkFrame(self.main, fg_color=BG)
        sf.pack(fill="x", padx=PAD, pady=(12, 0))

        step_defs = [
            ("server", "Install MCP server"),
            ("plugin", "Install Studio plugin"),
        ]
        if self._opts["claude"]["var"].get():
            step_defs.append(("claude", "Configure Claude Desktop"))
        if self._opts["cursor"]["var"].get():
            step_defs.append(("cursor", "Configure Cursor"))
        if self._opts["claude_code"]["var"].get():
            step_defs.append(("claude_code", "Configure Claude Code CLI"))
        step_defs.append(("restart", "Restart services"))

        self.step_rows = {}
        for sid, label in step_defs:
            row = ctk.CTkFrame(sf, fg_color="transparent", height=26)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            ind = self._lbl(row, "\u25cb", size=8, color=MUTED)
            ind.pack(side="left", padx=(2, 8))

            txt = self._lbl(row, label, size=12, color=MUTED)
            txt.pack(side="left")

            st = self._lbl(row, "", size=10, color=MUTED)
            st.pack(side="right")

            self.step_rows[sid] = (ind, txt, st)

        ctk.CTkFrame(self.main, fg_color="transparent").pack(fill="both", expand=True)

        self.progress = ctk.CTkProgressBar(
            self.main, fg_color=SURFACE, progress_color=ACCENT,
            height=2, corner_radius=0,
        )
        self.progress.pack(fill="x", side="bottom")
        self.progress.configure(mode="indeterminate")
        self.progress.start()

        def do_install():
            results = run_install(
                install_claude=self._opts["claude"]["var"].get(),
                install_cursor=self._opts["cursor"]["var"].get(),
                install_claude_code=self._opts["claude_code"]["var"].get(),
                on_step=lambda sid, s: self.after(0, lambda: self._update_step(sid, s)),
            )
            self.after(0, lambda: self._show_done(results))

        threading.Thread(target=do_install, daemon=True).start()

    def _update_step(self, step_id, status):
        if step_id not in self.step_rows:
            return
        ind, txt, st = self.step_rows[step_id]
        if status == "working":
            ind.configure(text="\u25c9", text_color=ACCENT)
            txt.configure(text_color=TEXT)
        elif status == "done":
            ind.configure(text="\u25cf", text_color=SUCCESS)
            txt.configure(text_color=TEXT)
            st.configure(text="Done", text_color=SUCCESS)
        elif status == "error":
            ind.configure(text="\u25cf", text_color=ERROR)
            txt.configure(text_color=TEXT)
            st.configure(text="Failed", text_color=ERROR)

    # -- Done Screen --

    def _show_done(self, results):
        self.progress.stop()
        self.progress.pack_forget()
        self._clear()

        has_errors = len(results.get("errors", [])) > 0
        all_failed = len(results.get("steps", [])) == 0

        hdr = ctk.CTkFrame(self.main, fg_color=BG)
        hdr.pack(fill="x", padx=PAD, pady=(16, 0))

        if all_failed:
            title, tc = "Installation failed", ERROR
        elif has_errors:
            title, tc = "Installed with issues", WARN
        else:
            title, tc = "Installed", SUCCESS

        self._lbl(hdr, title, size=18, weight="bold", color=tc).pack(side="left")

        self._div(self.main)

        rf = ctk.CTkFrame(self.main, fg_color=BG)
        rf.pack(fill="x", padx=PAD, pady=(12, 0))

        for s in results.get("steps", []):
            row = ctk.CTkFrame(rf, fg_color="transparent", height=20)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            self._lbl(row, "\u25cf", size=7, color=SUCCESS).pack(side="left", padx=(2, 6))
            self._lbl(row, s, size=11, color=TEXT).pack(side="left")

        for e in results.get("errors", []):
            row = ctk.CTkFrame(rf, fg_color="transparent", height=20)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            self._lbl(row, "\u25cf", size=7, color=ERROR).pack(side="left", padx=(2, 6))
            self._lbl(row, e, size=11, color=ERROR).pack(side="left")

        # Claude Code command if not auto-configured
        if results.get("claude_code_cmd") and not all_failed and not self._opts["claude_code"]["var"].get():
            self._div(self.main)
            cf = ctk.CTkFrame(self.main, fg_color=BG)
            cf.pack(fill="x", padx=PAD, pady=(10, 0))
            self._lbl(cf, "CLAUDE CODE", size=9, color=MUTED).pack(anchor="w")

            cmd_bg = ctk.CTkFrame(cf, fg_color=SURFACE, corner_radius=4)
            cmd_bg.pack(fill="x", pady=(4, 0))
            ctk.CTkLabel(
                cmd_bg, text=results["claude_code_cmd"],
                text_color=MUTED, font=ctk.CTkFont(family=MONO, size=10),
                wraplength=W - 70, justify="left", anchor="w",
            ).pack(padx=10, pady=8, anchor="w", fill="x")

            def copy_cmd():
                self.clipboard_clear()
                self.clipboard_append(results["claude_code_cmd"])
                copy_btn.configure(text="Copied")
                self.after(1500, lambda: copy_btn.configure(text="Copy"))

            copy_btn = ctk.CTkButton(
                cf, text="Copy", height=24, width=50,
                font=ctk.CTkFont(family=FONT, size=10),
                fg_color=SURFACE, hover_color=BORDER,
                text_color=MUTED, corner_radius=4,
                command=copy_cmd,
            )
            copy_btn.pack(anchor="e", pady=(4, 0))

        ctk.CTkFrame(self.main, fg_color="transparent").pack(fill="both", expand=True)

        if not all_failed:
            nf = ctk.CTkFrame(self.main, fg_color=BG)
            nf.pack(fill="x", padx=PAD, pady=(0, 6))
            self._lbl(nf, "Restart your AI client, then open Studio.", size=10, color=MUTED).pack(anchor="w")

        bot = ctk.CTkFrame(self.main, fg_color=BG)
        bot.pack(fill="x", padx=PAD, pady=(0, PAD))
        ctk.CTkButton(
            bot, text="Done", height=38,
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_DIM, text_color="#fff",
            corner_radius=6, command=self.destroy,
        ).pack(fill="x")


if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
