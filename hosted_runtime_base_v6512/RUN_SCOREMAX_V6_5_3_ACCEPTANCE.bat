@echo off
setlocal
cd /d "%~dp0"
echo Running ScoreMax V6.5.3 full local acceptance...
python run_v6_5_3_acceptance.py
if errorlevel 1 goto :fail
echo.
echo ScoreMax V6.5.3 local acceptance PASSED.
goto :end
:fail
echo.
echo Acceptance FAILED. Do not promote this build.
:end
pause
