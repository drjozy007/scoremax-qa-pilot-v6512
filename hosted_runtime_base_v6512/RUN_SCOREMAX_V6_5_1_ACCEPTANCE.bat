@echo off
setlocal
cd /d "%~dp0"
echo Running ScoreMax V6.5.1 integration rectification acceptance...
python smoke_tests_v6_5_integration.py || goto :fail
python smoke_tests_v6_5_1_rectification.py || goto :fail
python smoke_tests_v6_5_1_deep.py || goto :fail
python scale_test_v6_5_integration_releases.py || goto :fail
echo.
echo Focused V6.5.1 integration acceptance PASSED.
goto :end
:fail
echo.
echo Acceptance FAILED. Do not promote this build.
:end
pause
