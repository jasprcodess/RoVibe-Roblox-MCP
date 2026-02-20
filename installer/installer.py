"""RoVibe MCP Installer — Dark monochrome UI."""

import threading
import customtkinter as ctk
from installer_logic import (
    claude_code_detected,
    claude_desktop_detected,
    cursor_detected,
    find_studio_plugins,
    is_studio_running,
    run_install,
)

# Dark monochrome palette with blue accent
BG = "#0e0e0e"
SURFACE = "#181818"
SURFACE2 = "#222222"
BORDER = "#2a2a2a"
ACCENT = "#2d57fc"
ACCENT_DIM = "#1a3ab0"
TEXT = "#e0e0e0"
MUTED = "#707070"
SUCCESS = "#44cc66"
ERROR = "#cc4444"
WARN = "#cc9944"

W = 480
H = 540

FONT = "Segoe UI"
MONO = "Consolas"


class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RoVibe Installer")
        self.geometry(f"{W}x{H}")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        ctk.set_appearance_mode("dark")

        self.main = ctk.CTkFrame(self, fg_color=BG)
        self.main.pack(fill="both", expand=True)

        self.step_rows = {}
        self.show_main()

    def clear(self):
        for w in self.main.winfo_children():
            w.destroy()

    def _label(self, parent, text, size=13, color=TEXT, weight="normal", **kw):
        return ctk.CTkLabel(
            parent, text=text, text_color=color,
            font=ctk.CTkFont(family=FONT, size=size, weight=weight), **kw,
        )

    def _divider(self, parent):
        d = ctk.CTkFrame(parent, fg_color=BORDER, height=1)
        d.pack(fill="x", padx=24, pady=0)
        return d

    # ── Main Screen ──

    def show_main(self):
        self.clear()

        # Header
        header = ctk.CTkFrame(self.main, fg_color=BG, height=70)
        header.pack(fill="x", padx=24, pady=(24, 0))
        header.pack_propagate(False)

        self._label(header, "RoVibe", size=28, weight="bold", color="#ffffff").pack(side="left")
        self._label(header, "MCP Installer", size=14, color=MUTED).place(x=130, y=32)

        self._divider(self.main)

        # Detection section
        detect = ctk.CTkFrame(self.main, fg_color=BG)
        detect.pack(fill="x", padx=24, pady=(16, 0))

        self._label(detect, "DETECTED", size=10, color=MUTED).pack(anchor="w")

        plugins = find_studio_plugins()
        studio_ok = plugins is not None
        studio_running = is_studio_running()

        self._detect_row(detect, "Roblox Studio",
                         "Found" if studio_ok else "Not found",
                         studio_ok)
        if studio_running and studio_ok:
            self._label(detect, "  Will be closed during install", size=11, color=WARN).pack(anchor="w", padx=4)

        has_claude = claude_desktop_detected()
        has_cursor = cursor_detected()
        has_claude_code = claude_code_detected()

        self._detect_row(detect, "Claude Desktop",
                         "Detected" if has_claude else "Not installed",
                         has_claude)
        self._detect_row(detect, "Cursor",
                         "Detected" if has_cursor else "Not installed",
                         has_cursor)
        self._detect_row(detect, "Claude Code CLI",
                         "Detected" if has_claude_code else "Not installed",
                         has_claude_code)

        # Options section
        self._divider(self.main)
        opts = ctk.CTkFrame(self.main, fg_color=BG)
        opts.pack(fill="x", padx=24, pady=(16, 0))

        self._label(opts, "CONFIGURE", size=10, color=MUTED).pack(anchor="w")

        self.opt_claude = ctk.BooleanVar(value=has_claude)
        self.opt_cursor = ctk.BooleanVar(value=has_cursor)
        self.opt_claude_code = ctk.BooleanVar(value=has_claude_code)

        self._option_row(opts, "Claude Desktop", self.opt_claude, not has_claude)
        self._option_row(opts, "Cursor", self.opt_cursor, not has_cursor)
        self._option_row(opts, "Claude Code CLI", self.opt_claude_code, not has_claude_code)

        # Spacer
        ctk.CTkFrame(self.main, fg_color="transparent", height=1).pack(fill="both", expand=True)

        # Install button
        btn_frame = ctk.CTkFrame(self.main, fg_color=BG)
        btn_frame.pack(fill="x", padx=24, pady=(0, 24))

        if not studio_ok:
            self._label(btn_frame, "Roblox Studio is required", size=11, color=ERROR).pack(pady=(0, 8))

        self.install_btn = ctk.CTkButton(
            btn_frame, text="Install", height=44,
            font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_DIM, text_color="#ffffff",
            corner_radius=8,
            command=self._on_install,
            state="normal" if studio_ok else "disabled",
        )
        self.install_btn.pack(fill="x")

    def _detect_row(self, parent, name, status, ok):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=26)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)
        dot = "●" if ok else "○"
        color = SUCCESS if ok else MUTED
        self._label(row, dot, size=8, color=color).pack(side="left", padx=(4, 8))
        self._label(row, name, size=13, color=TEXT).pack(side="left")
        self._label(row, status, size=12, color=color).pack(side="right")

    def _option_row(self, parent, name, var, disabled):
        row = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)
        cb = ctk.CTkCheckBox(
            row, text=name, variable=var,
            font=ctk.CTkFont(family=FONT, size=13),
            text_color=MUTED if disabled else TEXT,
            fg_color=ACCENT, hover_color=ACCENT_DIM,
            border_color=BORDER, checkmark_color="#ffffff",
            corner_radius=4, border_width=2, height=20, width=20,
        )
        cb.pack(side="left", padx=4)
        if disabled:
            cb.configure(state="disabled")
            var.set(False)

    # ── Installing ──

    def _on_install(self):
        self.install_btn.configure(state="disabled", text="Installing...")
        self.clear()

        header = ctk.CTkFrame(self.main, fg_color=BG, height=56)
        header.pack(fill="x", padx=24, pady=(24, 0))
        header.pack_propagate(False)
        self._label(header, "Installing", size=22, weight="bold", color="#ffffff").pack(side="left", anchor="s")

        self._divider(self.main)

        # Step list
        steps_frame = ctk.CTkFrame(self.main, fg_color=BG)
        steps_frame.pack(fill="x", padx=24, pady=(20, 0))

        step_defs = [
            ("server", "Install MCP server"),
            ("plugin", "Install Studio plugin"),
        ]
        if self.opt_claude.get():
            step_defs.append(("claude", "Configure Claude Desktop"))
        if self.opt_cursor.get():
            step_defs.append(("cursor", "Configure Cursor"))
        if self.opt_claude_code.get():
            step_defs.append(("claude_code", "Configure Claude Code CLI"))
        step_defs.append(("restart", "Restart services"))

        self.step_rows = {}
        for step_id, label in step_defs:
            row = ctk.CTkFrame(steps_frame, fg_color="transparent", height=32)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            indicator = self._label(row, "○", size=10, color=MUTED)
            indicator.pack(side="left", padx=(4, 12))

            text_lbl = self._label(row, label, size=14, color=MUTED)
            text_lbl.pack(side="left")

            status_lbl = self._label(row, "", size=12, color=MUTED)
            status_lbl.pack(side="right", padx=4)

            self.step_rows[step_id] = (indicator, text_lbl, status_lbl)

        # Spacer
        ctk.CTkFrame(self.main, fg_color="transparent").pack(fill="both", expand=True)

        # Progress bar at bottom
        self.progress = ctk.CTkProgressBar(
            self.main, fg_color=SURFACE, progress_color=ACCENT,
            height=3, corner_radius=0,
        )
        self.progress.pack(fill="x", side="bottom")
        self.progress.configure(mode="indeterminate")
        self.progress.start()

        def do_install():
            results = run_install(
                install_claude=self.opt_claude.get(),
                install_cursor=self.opt_cursor.get(),
                install_claude_code=self.opt_claude_code.get(),
                on_step=lambda sid, s: self.after(0, lambda: self._update_step(sid, s)),
            )
            self.after(0, lambda: self._show_done(results))

        threading.Thread(target=do_install, daemon=True).start()

    def _update_step(self, step_id: str, status: str):
        if step_id not in self.step_rows:
            return
        indicator, text_lbl, status_lbl = self.step_rows[step_id]
        if status == "working":
            indicator.configure(text="◉", text_color=ACCENT)
            text_lbl.configure(text_color=TEXT)
            status_lbl.configure(text="", text_color=MUTED)
        elif status == "done":
            indicator.configure(text="●", text_color=SUCCESS)
            text_lbl.configure(text_color=TEXT)
            status_lbl.configure(text="Done", text_color=SUCCESS)
        elif status == "error":
            indicator.configure(text="●", text_color=ERROR)
            text_lbl.configure(text_color=TEXT)
            status_lbl.configure(text="Failed", text_color=ERROR)

    # ── Done Screen ──

    def _show_done(self, results: dict):
        self.progress.stop()
        self.progress.pack_forget()

        self.clear()

        has_errors = len(results.get("errors", [])) > 0
        all_failed = len(results.get("steps", [])) == 0

        # Header
        header = ctk.CTkFrame(self.main, fg_color=BG, height=56)
        header.pack(fill="x", padx=24, pady=(24, 0))
        header.pack_propagate(False)

        if all_failed:
            title = "Installation failed"
            title_color = ERROR
        elif has_errors:
            title = "Installed with issues"
            title_color = WARN
        else:
            title = "Installed"
            title_color = SUCCESS

        self._label(header, title, size=22, weight="bold", color=title_color).pack(side="left", anchor="s")

        self._divider(self.main)

        # Results
        results_frame = ctk.CTkFrame(self.main, fg_color=BG)
        results_frame.pack(fill="x", padx=24, pady=(16, 0))

        for s in results.get("steps", []):
            row = ctk.CTkFrame(results_frame, fg_color="transparent", height=24)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            self._label(row, "●", size=8, color=SUCCESS).pack(side="left", padx=(4, 8))
            self._label(row, s, size=13, color=TEXT).pack(side="left")

        for e in results.get("errors", []):
            row = ctk.CTkFrame(results_frame, fg_color="transparent", height=24)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            self._label(row, "●", size=8, color=ERROR).pack(side="left", padx=(4, 8))
            self._label(row, e, size=13, color=ERROR).pack(side="left")

        # Claude Code command (if not auto-configured)
        if results.get("claude_code_cmd") and not all_failed and not self.opt_claude_code.get():
            self._divider(self.main)
            cli_frame = ctk.CTkFrame(self.main, fg_color=BG)
            cli_frame.pack(fill="x", padx=24, pady=(12, 0))

            self._label(cli_frame, "CLAUDE CODE", size=10, color=MUTED).pack(anchor="w")

            cmd_bg = ctk.CTkFrame(cli_frame, fg_color=SURFACE, corner_radius=6)
            cmd_bg.pack(fill="x", pady=(6, 0))

            cmd_text = ctk.CTkLabel(
                cmd_bg, text=results["claude_code_cmd"],
                text_color=MUTED, font=ctk.CTkFont(family=MONO, size=11),
                wraplength=W - 80, justify="left", anchor="w",
            )
            cmd_text.pack(padx=12, pady=10, anchor="w", fill="x")

            def copy_cmd():
                self.clipboard_clear()
                self.clipboard_append(results["claude_code_cmd"])
                copy_btn.configure(text="Copied")
                self.after(1500, lambda: copy_btn.configure(text="Copy"))

            copy_btn = ctk.CTkButton(
                cli_frame, text="Copy", height=28, width=60,
                font=ctk.CTkFont(family=FONT, size=11),
                fg_color=SURFACE2, hover_color=BORDER,
                text_color=MUTED, corner_radius=6,
                command=copy_cmd,
            )
            copy_btn.pack(anchor="e", pady=(6, 0))

        # Spacer
        ctk.CTkFrame(self.main, fg_color="transparent").pack(fill="both", expand=True)

        # Next steps note
        if not all_failed:
            note = ctk.CTkFrame(self.main, fg_color=BG)
            note.pack(fill="x", padx=24, pady=(0, 8))
            self._label(note, "Restart your AI client, then open Studio to start.", size=12, color=MUTED).pack(anchor="w")

        # Done button
        btn_frame = ctk.CTkFrame(self.main, fg_color=BG)
        btn_frame.pack(fill="x", padx=24, pady=(0, 24))

        ctk.CTkButton(
            btn_frame, text="Done", height=44,
            font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_DIM, text_color="#ffffff",
            corner_radius=8, command=self.destroy,
        ).pack(fill="x")


if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
