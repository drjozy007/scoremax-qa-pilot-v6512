@echo off
setlocal
cd /d "%~dp0"
echo Starting ScoreMax V6.5.1 Three-System Integration Rectification Internal Live...
python scoremax_internal_live_v651.py
if errorlevel 1 (
  echo.
  echo ScoreMax did not start. Run INSTALL_AND_START_SCOREMAX_V6_5_1.bat once if a package is missing.
)
pause
