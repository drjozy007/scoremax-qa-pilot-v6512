@echo off
setlocal
cd /d "%~dp0"
echo Installing ScoreMax V6.5.1 requirements...
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo.
echo Starting ScoreMax V6.5.1...
python scoremax_internal_live_v651.py
goto :end
:fail
echo.
echo Requirement installation failed. Review the output above.
:end
pause
