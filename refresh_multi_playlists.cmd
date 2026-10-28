@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist "data\multi" mkdir "data\multi"
python refresh_multi_playlists.py %* >> "data\multi\refresh.log" 2>&1
exit /b %ERRORLEVEL%
