@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 goto installed
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto bundled
echo Python 3.10 or later is required. Install Python and try again.
pause
exit /b 1
:installed
py -3 -m bmo.app
goto end
:bundled
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m bmo.app
:end
pause
