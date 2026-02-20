@echo off
REM Build RoVibe MCP Installer using PyInstaller
REM Run this from the installer/ directory

pip install pyinstaller

pyinstaller --onefile --noconsole ^
    --name "RoVibe-Installer" ^
    --icon=logo.ico ^
    --add-data "rovibe-mcp.exe;." ^
    --add-data "MCPStudioPlugin.rbxm;." ^
    --add-data "logo.ico;." ^
    installer.py

echo.
echo Build complete! Output: dist\RoVibe-Installer.exe
pause
