"""RoVibe MCP Installer - pure tkinter, no external GUI deps."""

import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
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
ACCENT_HOVER = "#4970ff"
TEXT = "#e0e0e0"
MUTED = "#585858"
SUCCESS = "#3dbf5e"
ERROR = "#dd4444"
WARN = "#cc9900"

W = 400
H = 440
PAD = 20


class InstallerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # hide until ready
        self.root.title("RoVibe Installer")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Center on screen
        x = (self.root.winfo_screenwidth() - W) // 2
        y = (self.root.winfo_screenheight() - H) // 2
        self.root.geometry(f"{W}x{H}+{x}+{y}")

        # Set icon if available
        try:
            import os
            if getattr(sys, "frozen", False):
                icon_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                icon_path = os.path.join(os.path.dirname(__file__), "logo.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        # Fonts
        self.fn = tkfont.Font(family="Segoe UI", size=12)
        self.fn_sm = tkfont.Font(family="Segoe UI", size=10)
        self.fn_xs = tkfont.Font(family="Segoe UI", size=9)
        self.fn_lg = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self.fn_md = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self.fn_btn = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.fn_mono = tkfont.Font(family="Consolas", size=10)

        # State
        self.detection = {}
        self._detect_labels = {}
        self._opt_vars = {}
        self._opt_cbs = {}
        self.step_rows = {}

        # Main content
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(fill="both", expand=True)

        # Build UI skeleton immediately
        self._show_main_skeleton()

        # Show window
        self.root.deiconify()

        # Detect in background
        threading.Thread(target=self._run_detection, daemon=True).start()

    def run(self):
        self.root.mainloop()

    # -- Helpers --
    def _clear(self):
        for w in self.main.winfo_children():
            w.destroy()

    def _div(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=PAD)

    def _make_btn(self, parent, text, command, state="normal"):
        btn_frame = tk.Frame(parent, bg=ACCENT, cursor="hand2" if state == "normal" else "")
        lbl = tk.Label(btn_frame, text=text, bg=ACCENT, fg="#fff", font=self.fn_btn, pady=8)
        lbl.pack(fill="x")

        def on_click(e=None):
            if btn_frame._state == "normal":
                command()

        def on_enter(e):
            if btn_frame._state == "normal":
                btn_frame.configure(bg=ACCENT_HOVER)
                lbl.configure(bg=ACCENT_HOVER)

        def on_leave(e):
            c = ACCENT if btn_frame._state == "normal" else SURFACE
            btn_frame.configure(bg=c)
            lbl.configure(bg=c)

        btn_frame._state = state
        btn_frame._lbl = lbl
        if state == "disabled":
            btn_frame.configure(bg=SURFACE)
            lbl.configure(bg=SURFACE, fg=MUTED)

        lbl.bind("<Button-1>", on_click)
        btn_frame.bind("<Button-1>", on_click)
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        btn_frame.bind("<Enter>", on_enter)
        btn_frame.bind("<Leave>", on_leave)

        def set_state(s):
            btn_frame._state = s
            if s == "normal":
                btn_frame.configure(bg=ACCENT, cursor="hand2")
                lbl.configure(bg=ACCENT, fg="#fff")
            else:
                btn_frame.configure(bg=SURFACE, cursor="")
                lbl.configure(bg=SURFACE, fg=MUTED)

        def set_text(t):
            lbl.configure(text=t)

        btn_frame.set_state = set_state
        btn_frame.set_text = set_text
        return btn_frame

    # -- Main Screen --
    def _show_main_skeleton(self):
        # Header
        hdr = tk.Frame(self.main, bg=BG)
        hdr.pack(fill="x", padx=PAD, pady=(16, 8))
        tk.Label(hdr, text="RoVibe", bg=BG, fg="#fff", font=self.fn_lg).pack(side="left")
        tk.Label(hdr, text="MCP", bg=BG, fg=MUTED, font=self.fn_sm).pack(side="left", padx=(8, 0), pady=(8, 0))

        self._div(self.main)

        # Status section
        det = tk.Frame(self.main, bg=BG)
        det.pack(fill="x", padx=PAD, pady=(10, 0))
        tk.Label(det, text="STATUS", bg=BG, fg=MUTED, font=self.fn_xs).pack(anchor="w")

        self._detect_labels["studio"] = self._status_row(det, "Roblox Studio")
        self._studio_warn = tk.Label(det, text="  Will be closed during install", bg=BG, fg=WARN, font=self.fn_sm)
        self._detect_labels["claude"] = self._status_row(det, "Claude Desktop")
        self._detect_labels["cursor"] = self._status_row(det, "Cursor")
        self._detect_labels["claude_code"] = self._status_row(det, "Claude Code CLI")

        # Configure section
        self._div(self.main)
        opts = tk.Frame(self.main, bg=BG)
        opts.pack(fill="x", padx=PAD, pady=(10, 0))
        tk.Label(opts, text="CONFIGURE", bg=BG, fg=MUTED, font=self.fn_xs).pack(anchor="w")

        for key, name in [("claude", "Claude Desktop"), ("cursor", "Cursor"), ("claude_code", "Claude Code CLI")]:
            self._opt_vars[key] = tk.BooleanVar(value=False)
            row = tk.Frame(opts, bg=BG)
            row.pack(fill="x", pady=1)
            cb = tk.Checkbutton(
                row, text=name, variable=self._opt_vars[key],
                bg=BG, fg=TEXT, selectcolor=SURFACE,
                activebackground=BG, activeforeground=TEXT,
                font=self.fn, anchor="w",
            )
            cb.pack(side="left")
            self._opt_cbs[key] = cb

        # Spacer
        tk.Frame(self.main, bg=BG).pack(fill="both", expand=True)

        # Bottom
        bot = tk.Frame(self.main, bg=BG)
        bot.pack(fill="x", padx=PAD, pady=(0, PAD))

        self._studio_err = tk.Label(bot, text="Roblox Studio is required", bg=BG, fg=ERROR, font=self.fn_sm)

        self.install_btn = self._make_btn(bot, "Install", self._on_install, state="disabled")
        self.install_btn.pack(fill="x")

    def _status_row(self, parent, name):
        row = tk.Frame(parent, bg=BG, height=22)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        dot = tk.Label(row, text="\u25cb", bg=BG, fg=MUTED, font=("Segoe UI", 7))
        dot.pack(side="left", padx=(2, 6))

        tk.Label(row, text=name, bg=BG, fg=MUTED, font=self.fn).pack(side="left")

        status = tk.Label(row, text="Checking...", bg=BG, fg=MUTED, font=self.fn_sm)
        status.pack(side="right")

        return (dot, status)

    # -- Detection --
    def _run_detection(self):
        plugins = find_studio_plugins()
        studio_ok = plugins is not None
        self.detection["studio"] = studio_ok
        self.root.after(0, lambda: self._update_detect("studio", studio_ok))

        if studio_ok:
            running = is_studio_running()
            self.detection["studio_running"] = running
            if running:
                self.root.after(0, lambda: self._studio_warn.pack(anchor="w"))

        claude_ok = claude_desktop_detected()
        self.detection["claude"] = claude_ok
        self.root.after(0, lambda: self._update_detect("claude", claude_ok))

        cursor_ok = cursor_detected()
        self.detection["cursor"] = cursor_ok
        self.root.after(0, lambda: self._update_detect("cursor", cursor_ok))

        cc_ok = claude_code_detected()
        self.detection["claude_code"] = cc_ok
        self.root.after(0, lambda: self._update_detect("claude_code", cc_ok))

        self.root.after(0, self._detection_done)

    def _update_detect(self, key, ok):
        if key not in self._detect_labels:
            return
        dot, status = self._detect_labels[key]
        dot.configure(text="\u25cf" if ok else "\u25cb", fg=SUCCESS if ok else MUTED)
        status.configure(text="Detected" if ok else "Not detected", fg=SUCCESS if ok else MUTED)

        if key in self._opt_vars:
            self._opt_vars[key].set(ok)

    def _detection_done(self):
        if self.detection.get("studio"):
            self.install_btn.set_state("normal")
        else:
            self._studio_err.pack(pady=(0, 6))

    # -- Installing --
    def _on_install(self):
        self.install_btn.set_state("disabled")
        self.install_btn.set_text("Installing...")
        self._clear()

        hdr = tk.Frame(self.main, bg=BG)
        hdr.pack(fill="x", padx=PAD, pady=(16, 8))
        tk.Label(hdr, text="Installing", bg=BG, fg="#fff", font=self.fn_md).pack(side="left")

        self._div(self.main)

        sf = tk.Frame(self.main, bg=BG)
        sf.pack(fill="x", padx=PAD, pady=(10, 0))

        step_defs = [("server", "Install MCP server"), ("plugin", "Install Studio plugin")]
        if self._opt_vars["claude"].get():
            step_defs.append(("claude", "Configure Claude Desktop"))
        if self._opt_vars["cursor"].get():
            step_defs.append(("cursor", "Configure Cursor"))
        if self._opt_vars["claude_code"].get():
            step_defs.append(("claude_code", "Configure Claude Code CLI"))
        step_defs.append(("restart", "Restart services"))

        self.step_rows = {}
        for sid, label in step_defs:
            row = tk.Frame(sf, bg=BG, height=24)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            ind = tk.Label(row, text="\u25cb", bg=BG, fg=MUTED, font=("Segoe UI", 8))
            ind.pack(side="left", padx=(2, 8))

            txt = tk.Label(row, text=label, bg=BG, fg=MUTED, font=self.fn)
            txt.pack(side="left")

            st = tk.Label(row, text="", bg=BG, fg=MUTED, font=self.fn_sm)
            st.pack(side="right")

            self.step_rows[sid] = (ind, txt, st)

        # Progress bar (simple animated)
        tk.Frame(self.main, bg=BG).pack(fill="both", expand=True)
        self._progress_frame = tk.Frame(self.main, bg=SURFACE, height=3)
        self._progress_frame.pack(fill="x", side="bottom")
        self._progress_bar = tk.Frame(self._progress_frame, bg=ACCENT, height=3, width=0)
        self._progress_bar.place(x=0, y=0, height=3)
        self._progress_pos = 0
        self._progress_running = True
        self._animate_progress()

        def do_install():
            results = run_install(
                install_claude=self._opt_vars["claude"].get(),
                install_cursor=self._opt_vars["cursor"].get(),
                install_claude_code=self._opt_vars["claude_code"].get(),
                on_step=lambda sid, s: self.root.after(0, lambda: self._update_step(sid, s)),
            )
            self.root.after(0, lambda: self._show_done(results))

        threading.Thread(target=do_install, daemon=True).start()

    def _animate_progress(self):
        if not self._progress_running:
            return
        self._progress_pos = (self._progress_pos + 3) % (W + 80)
        x = self._progress_pos - 80
        self._progress_bar.place(x=x, width=80, height=3)
        self.root.after(16, self._animate_progress)

    def _update_step(self, step_id, status):
        if step_id not in self.step_rows:
            return
        ind, txt, st = self.step_rows[step_id]
        if status == "working":
            ind.configure(text="\u25c9", fg=ACCENT)
            txt.configure(fg=TEXT)
        elif status == "done":
            ind.configure(text="\u25cf", fg=SUCCESS)
            txt.configure(fg=TEXT)
            st.configure(text="Done", fg=SUCCESS)
        elif status == "error":
            ind.configure(text="\u25cf", fg=ERROR)
            txt.configure(fg=TEXT)
            st.configure(text="Failed", fg=ERROR)

    # -- Done --
    def _show_done(self, results):
        self._progress_running = False
        self._clear()

        has_errors = len(results.get("errors", [])) > 0
        all_failed = len(results.get("steps", [])) == 0

        hdr = tk.Frame(self.main, bg=BG)
        hdr.pack(fill="x", padx=PAD, pady=(16, 8))

        if all_failed:
            title, tc = "Installation failed", ERROR
        elif has_errors:
            title, tc = "Installed with issues", WARN
        else:
            title, tc = "Installed", SUCCESS

        tk.Label(hdr, text=title, bg=BG, fg=tc, font=self.fn_md).pack(side="left")

        self._div(self.main)

        rf = tk.Frame(self.main, bg=BG)
        rf.pack(fill="x", padx=PAD, pady=(10, 0))

        for s in results.get("steps", []):
            row = tk.Frame(rf, bg=BG, height=20)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            tk.Label(row, text="\u25cf", bg=BG, fg=SUCCESS, font=("Segoe UI", 7)).pack(side="left", padx=(2, 6))
            tk.Label(row, text=s, bg=BG, fg=TEXT, font=self.fn_sm).pack(side="left")

        for e in results.get("errors", []):
            row = tk.Frame(rf, bg=BG, height=20)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            tk.Label(row, text="\u25cf", bg=BG, fg=ERROR, font=("Segoe UI", 7)).pack(side="left", padx=(2, 6))
            tk.Label(row, text=e, bg=BG, fg=ERROR, font=self.fn_sm).pack(side="left")

        # Claude Code command
        if results.get("claude_code_cmd") and not all_failed and not self._opt_vars["claude_code"].get():
            self._div(self.main)
            cf = tk.Frame(self.main, bg=BG)
            cf.pack(fill="x", padx=PAD, pady=(8, 0))
            tk.Label(cf, text="CLAUDE CODE", bg=BG, fg=MUTED, font=self.fn_xs).pack(anchor="w")

            cmd_bg = tk.Frame(cf, bg=SURFACE)
            cmd_bg.pack(fill="x", pady=(4, 0))
            tk.Label(
                cmd_bg, text=results["claude_code_cmd"], bg=SURFACE, fg=MUTED,
                font=self.fn_mono, wraplength=W - 70, justify="left", anchor="w",
            ).pack(padx=10, pady=8, anchor="w", fill="x")

            copy_lbl = tk.Label(cf, text="Copy", bg=SURFACE, fg=MUTED, font=self.fn_sm, cursor="hand2", padx=8, pady=2)
            copy_lbl.pack(anchor="e", pady=(4, 0))

            def copy_cmd(e=None):
                self.root.clipboard_clear()
                self.root.clipboard_append(results["claude_code_cmd"])
                copy_lbl.configure(text="Copied")
                self.root.after(1500, lambda: copy_lbl.configure(text="Copy"))

            copy_lbl.bind("<Button-1>", copy_cmd)

        tk.Frame(self.main, bg=BG).pack(fill="both", expand=True)

        if not all_failed:
            tk.Label(self.main, text="Restart your AI client, then open Studio.", bg=BG, fg=MUTED, font=self.fn_sm).pack(padx=PAD, anchor="w", pady=(0, 4))

        bot = tk.Frame(self.main, bg=BG)
        bot.pack(fill="x", padx=PAD, pady=(0, PAD))
        self._make_btn(bot, "Done", self.root.destroy).pack(fill="x")


def _acquire_lock():
    """Ensure only one instance of the installer runs at a time."""
    if sys.platform == "win32":
        import ctypes
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "RoVibeMCPInstallerMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            # Another instance is running, bring it to front and exit
            import ctypes.wintypes
            hwnd = ctypes.windll.user32.FindWindowW(None, "RoVibe Installer")
            if hwnd:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            sys.exit(0)
        return _mutex
    return None


if __name__ == "__main__":
    try:
        _lock = _acquire_lock()
        app = InstallerApp()
        app.run()
    except Exception:
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
