@echo off
REM Build RoVibe MCP Installer using PyInstaller
REM Run this from the installer/ directory

pip install -r requirements.txt

pyinstaller --onefile --noconsole ^
    --name "RoVibe-Installer" ^
    --icon=logo.ico ^
    --add-data "rovibe-mcp.exe;." ^
    --add-data "MCPStudioPlugin.rbxm;." ^
    --hidden-import customtkinter ^
    --collect-all customtkinter ^
    installer.py

echo.
echo Build complete! Output: dist\RoVibe-Installer.exe
pause
