@echo off
setlocal
cd /d "%~dp0"
echo Installing ScoreMax V6.5.3 requirements...
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo.
echo Starting ScoreMax V6.5.3 integration worker...
start "ScoreMax Integration Worker V6.5.3" /B python scoremax_integration_dispatch_v1.py --worker --evidence --limit 100
echo Starting ScoreMax V6.5.3 web platform...
python scoremax_internal_live_v653.py
goto :end
:fail
echo.
echo Requirement installation failed. Review the output above.
:end
pause
