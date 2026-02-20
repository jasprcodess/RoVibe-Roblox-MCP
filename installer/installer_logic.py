"""RoVibe MCP installation logic."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

if sys.platform == "win32":
    import winreg


def get_bundled_path(filename: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / filename


def get_install_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "RoVibe"
    return Path.home() / ".local" / "bin" / "rovibe"


def get_exe_name() -> str:
    return "rovibe-mcp.exe" if sys.platform == "win32" else "rovibe-mcp"


def find_studio_plugins() -> Path | None:
    if sys.platform == "win32":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Roblox\RobloxStudio",
            )
            content_folder, _ = winreg.QueryValueEx(key, "ContentFolder")
            winreg.CloseKey(key)
            return Path(content_folder).parent / "Plugins"
        except (OSError, FileNotFoundError):
            pass

        local_appdata = os.environ.get("LOCALAPPDATA", "")
        versions_dir = Path(local_appdata) / "Roblox" / "Versions"
        if versions_dir.exists():
            for entry in sorted(versions_dir.iterdir(), reverse=True):
                if (entry / "RobloxStudioBeta.exe").exists():
                    return entry / "Plugins"
    return None


def is_studio_running() -> bool:
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq RobloxStudioBeta.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return "RobloxStudioBeta.exe" in result.stdout
        else:
            result = subprocess.run(["pgrep", "-f", "RobloxStudio"], capture_output=True, timeout=5)
            return result.returncode == 0
    except Exception:
        return False


def kill_studio() -> bool:
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/IM", "RobloxStudioBeta.exe", "/F"],
                           capture_output=True, timeout=10)
        else:
            subprocess.run(["pkill", "-f", "RobloxStudio"], capture_output=True, timeout=10)
        time.sleep(1)
        return not is_studio_running()
    except Exception:
        return False


def is_process_running(name: str) -> bool:
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return name.lower() in result.stdout.lower()
    except Exception:
        pass
    return False


def kill_process(name: str) -> bool:
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, timeout=10)
            time.sleep(1)
            return not is_process_running(name)
    except Exception:
        pass
    return False


def get_claude_config_path() -> Path | None:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return None


def get_cursor_config_path() -> Path | None:
    return Path.home() / ".cursor" / "mcp.json"


def claude_desktop_detected() -> bool:
    p = get_claude_config_path()
    return p is not None and p.parent.exists()


def cursor_detected() -> bool:
    p = get_cursor_config_path()
    return p is not None and p.parent.exists()


def _find_claude_cli() -> str | None:
    """Find the claude CLI executable path."""
    path = shutil.which("claude")
    if path:
        return path
    if sys.platform == "win32":
        for candidate in [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "claude-code" / "claude.exe",
            Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd",
        ]:
            if candidate.exists():
                return str(candidate)
    return None


def claude_code_detected() -> bool:
    return _find_claude_cli() is not None


def detect_all() -> dict:
    """Run all detection checks. Returns dict of booleans."""
    plugins = find_studio_plugins()
    return {
        "studio": plugins is not None,
        "studio_running": is_studio_running() if plugins else False,
        "claude": claude_desktop_detected(),
        "cursor": cursor_detected(),
        "claude_code": claude_code_detected(),
    }


def upsert_mcp_config(config_path: Path, exe_path: Path) -> bool:
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        if "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
            config["mcpServers"] = {}
        config["mcpServers"].pop("Roblox Studio", None)
        config["mcpServers"]["RoVibe_Studio"] = {
            "command": str(exe_path),
            "args": ["--stdio"],
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


def run_claude_code_add(exe_path: Path) -> tuple[bool, str]:
    cli = _find_claude_cli()
    if not cli:
        return False, "claude CLI not found"
    try:
        # Remove existing entry first (ignore errors if it doesn't exist)
        subprocess.run(
            [cli, "mcp", "remove", "RoVibe_Studio"],
            capture_output=True, text=True, timeout=10,
        )
        result = subprocess.run(
            [cli, "mcp", "add", "--transport", "stdio", "RoVibe_Studio", "--", str(exe_path), "--stdio"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, "Added to Claude Code"
        return False, result.stderr.strip() or "Unknown error"
    except Exception as e:
        return False, str(e)


def run_install(
    install_claude: bool,
    install_cursor: bool,
    install_claude_code: bool,
    on_step: Callable[[str, str], None] | None = None,
) -> dict:
    """
    Run the full installation.
    on_step(step_id, status) where status is 'working', 'done', or 'error'.
    """

    def step(step_id: str, status: str):
        if on_step:
            on_step(step_id, status)
        if status == "working":
            time.sleep(0.1)

    results = {"steps": [], "errors": [], "exe_path": None, "claude_code_cmd": None}

    # 1. Copy MCP server
    step("server", "working")
    install_dir = get_install_dir()
    install_dir.mkdir(parents=True, exist_ok=True)
    exe_name = get_exe_name()
    src_exe = get_bundled_path(exe_name)
    dst_exe = install_dir / exe_name

    if not src_exe.exists():
        results["errors"].append(f"Bundled {exe_name} not found")
        step("server", "error")
        return results

    try:
        shutil.copy2(src_exe, dst_exe)
        results["exe_path"] = str(dst_exe)
        results["steps"].append("MCP server installed")
        step("server", "done")
    except PermissionError:
        results["errors"].append("MCP server is in use — close Claude/Cursor first, then reinstall")
        step("server", "error")
        return results
    except Exception as e:
        results["errors"].append(f"Failed to copy server: {e}")
        step("server", "error")
        return results

    # 2. Install Studio plugin
    step("plugin", "working")
    plugin_src = get_bundled_path("MCPStudioPlugin.rbxm")
    plugins_dir = find_studio_plugins()

    if plugins_dir and plugin_src.exists():
        plugins_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(plugin_src, plugins_dir / "MCPStudioPlugin.rbxm")
            results["steps"].append("Studio plugin installed")
            step("plugin", "done")
        except Exception as e:
            results["errors"].append(f"Failed to copy plugin: {e}")
            step("plugin", "error")
    elif not plugin_src.exists():
        results["errors"].append("Plugin file not found in bundle")
        step("plugin", "error")
    else:
        results["errors"].append("Roblox Studio not found")
        step("plugin", "error")

    # 3. Configure Claude Desktop
    if install_claude:
        step("claude", "working")
        claude_path = get_claude_config_path()
        if claude_path and upsert_mcp_config(claude_path, dst_exe):
            results["steps"].append("Claude Desktop configured")
            step("claude", "done")
        else:
            results["errors"].append("Failed to configure Claude Desktop")
            step("claude", "error")

    # 4. Configure Cursor
    if install_cursor:
        step("cursor", "working")
        cursor_path = get_cursor_config_path()
        if cursor_path and upsert_mcp_config(cursor_path, dst_exe):
            results["steps"].append("Cursor configured")
            step("cursor", "done")
        else:
            results["errors"].append("Failed to configure Cursor")
            step("cursor", "error")

    # 5. Claude Code CLI
    if install_claude_code:
        step("claude_code", "working")
        ok, msg = run_claude_code_add(dst_exe)
        if ok:
            results["steps"].append("Claude Code CLI configured")
            step("claude_code", "done")
        else:
            results["errors"].append(f"Claude Code: {msg}")
            step("claude_code", "error")

    results["claude_code_cmd"] = (
        f'claude mcp add --transport stdio RoVibe_Studio -- "{dst_exe}" --stdio'
    )

    step("complete", "done")
    return results


def is_installed() -> bool:
    """Check if RoVibe is already installed."""
    install_dir = get_install_dir()
    exe = install_dir / get_exe_name()
    return exe.exists()


def run_uninstall(
    on_step: Callable[[str, str], None] | None = None,
) -> dict:
    """
    Remove all RoVibe files and config entries.
    on_step(step_id, status) where status is 'working', 'done', or 'error'.
    """

    def step(step_id: str, status: str):
        if on_step:
            on_step(step_id, status)
        if status == "working":
            time.sleep(0.1)

    results = {"steps": [], "errors": []}

    # 1. Remove MCP server
    step("server", "working")
    install_dir = get_install_dir()
    exe = install_dir / get_exe_name()
    try:
        if exe.exists():
            try:
                exe.unlink()
            except PermissionError:
                results["errors"].append("MCP server is in use — close Claude/Cursor first, then uninstall")
                step("server", "error")
            else:
                # Remove dir if empty
                if install_dir.exists() and not any(install_dir.iterdir()):
                    install_dir.rmdir()
                results["steps"].append("MCP server removed")
                step("server", "done")
        else:
            results["steps"].append("MCP server (not found, skipped)")
            step("server", "done")
    except Exception as e:
        results["errors"].append(f"Failed to remove server: {e}")
        step("server", "error")

    # 2. Remove Studio plugin
    step("plugin", "working")
    plugins_dir = find_studio_plugins()
    if plugins_dir:
        plugin_file = plugins_dir / "MCPStudioPlugin.rbxm"
        try:
            if plugin_file.exists():
                plugin_file.unlink()
            results["steps"].append("Studio plugin removed")
            step("plugin", "done")
        except Exception as e:
            results["errors"].append(f"Failed to remove plugin: {e}")
            step("plugin", "error")
    else:
        results["steps"].append("Studio plugin (not found, skipped)")
        step("plugin", "done")

    # 3. Remove from Claude Desktop config
    step("claude", "working")
    claude_path = get_claude_config_path()
    if claude_path and claude_path.exists():
        try:
            with open(claude_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            servers = config.get("mcpServers", {})
            removed = False
            for key in ["RoVibe_Studio", "Roblox Studio"]:
                if key in servers:
                    del servers[key]
                    removed = True
            if removed:
                with open(claude_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                results["steps"].append("Claude Desktop config cleaned")
            else:
                results["steps"].append("Claude Desktop (no entry found)")
            step("claude", "done")
        except Exception as e:
            results["errors"].append(f"Claude Desktop config: {e}")
            step("claude", "error")
    else:
        step("claude", "done")

    # 4. Remove from Cursor config
    step("cursor", "working")
    cursor_path = get_cursor_config_path()
    if cursor_path and cursor_path.exists():
        try:
            with open(cursor_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            servers = config.get("mcpServers", {})
            removed = False
            for key in ["RoVibe_Studio", "Roblox Studio"]:
                if key in servers:
                    del servers[key]
                    removed = True
            if removed:
                with open(cursor_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                results["steps"].append("Cursor config cleaned")
            else:
                results["steps"].append("Cursor (no entry found)")
            step("cursor", "done")
        except Exception as e:
            results["errors"].append(f"Cursor config: {e}")
            step("cursor", "error")
    else:
        step("cursor", "done")

    # 5. Remove from Claude Code CLI
    step("claude_code", "working")
    cli = _find_claude_cli()
    if cli:
        try:
            result = subprocess.run(
                [cli, "mcp", "remove", "RoVibe_Studio"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                results["steps"].append("Claude Code CLI config cleaned")
            else:
                results["steps"].append("Claude Code (no entry found)")
            step("claude_code", "done")
        except Exception:
            step("claude_code", "done")
    else:
        step("claude_code", "done")

    step("complete", "done")
    return results


def get_running_restartable() -> dict[str, bool]:
    """Check which restartable processes are currently running."""
    running = {}
    if is_studio_running():
        running["studio"] = True
    if is_process_running("Claude.exe"):
        running["claude"] = True
    if is_process_running("Cursor.exe"):
        running["cursor"] = True
    return running


def restart_process(key: str) -> bool:
    """Kill and relaunch a process by key. Returns True on success."""
    if key == "studio":
        kill_studio()
        # Relaunch Studio
        try:
            local = os.environ.get("LOCALAPPDATA", "")
            versions = Path(local) / "Roblox" / "Versions"
            if versions.exists():
                for entry in sorted(versions.iterdir(), reverse=True):
                    exe = entry / "RobloxStudioBeta.exe"
                    if exe.exists():
                        subprocess.Popen([str(exe)], creationflags=0x00000008)  # DETACHED_PROCESS
                        return True
        except Exception:
            pass
        return False

    if key == "claude":
        kill_process("Claude.exe")
        try:
            local = os.environ.get("LOCALAPPDATA", "")
            exe = Path(local) / "Programs" / "claude-desktop" / "Claude.exe"
            if not exe.exists():
                exe = Path(local) / "AnthropicClaude" / "Claude.exe"
            if exe.exists():
                subprocess.Popen([str(exe)], creationflags=0x00000008)
                return True
        except Exception:
            pass
        return False

    if key == "cursor":
        kill_process("Cursor.exe")
        try:
            local = os.environ.get("LOCALAPPDATA", "")
            exe = Path(local) / "Programs" / "cursor" / "Cursor.exe"
            if exe.exists():
                subprocess.Popen([str(exe)], creationflags=0x00000008)
                return True
        except Exception:
            pass
        return False

    return False
