@echo off
rem Double-click to start Manim Studio in its own window (Edge or Chrome app mode).
rem Close this console window to stop the studio. If it is already running, this
rem only opens another window onto it.
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m studio.server --app %*
if errorlevel 1 pause
