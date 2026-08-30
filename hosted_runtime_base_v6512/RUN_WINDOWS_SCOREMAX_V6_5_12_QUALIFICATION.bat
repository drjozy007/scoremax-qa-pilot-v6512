@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=V6_5_12_WINDOWS_QUALIFICATION_EVIDENCE.txt"

> "%LOG%" echo ScoreMax V6.5.12 Synthetic Learner Isolation Rectification Qualification
>> "%LOG%" echo ================================================================
>> "%LOG%" echo Started: %DATE% %TIME%
>> "%LOG%" echo Candidate status: PENDING_FULL_RUNTIME_ACCEPTANCE
>> "%LOG%" echo.

python --version >> "%LOG%" 2>&1
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

set "SCOREMAX_ENV=test"
set "SCOREMAX_QA_SYNTHETIC_PROVISION_CONFIRM=I_UNDERSTAND_QA_ONLY"
python run_v6_5_12_acceptance.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

>> "%LOG%" echo.
>> "%LOG%" echo WINDOWS_CLEAN_EXTRACTION_ACCEPTANCE=PASS
>> "%LOG%" echo Completed: %DATE% %TIME%
echo SCOREMAX V6.5.12 WINDOWS QUALIFICATION PASSED
echo Evidence: %CD%\%LOG%
exit /b 0

:fail
>> "%LOG%" echo.
>> "%LOG%" echo WINDOWS_CLEAN_EXTRACTION_ACCEPTANCE=FAIL
>> "%LOG%" echo Failed: %DATE% %TIME%
echo SCOREMAX V6.5.12 WINDOWS QUALIFICATION FAILED
echo Do not promote this build.
exit /b 1
