@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=V6_5_4_WINDOWS_QUALIFICATION_EVIDENCE.txt"

> "%LOG%" echo ScoreMax V6.5.4 Supported-Windows Clean-Extraction Qualification
>> "%LOG%" echo ============================================================
>> "%LOG%" echo Started: %DATE% %TIME%
>> "%LOG%" echo Candidate status: PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION
>> "%LOG%" echo.

ver >> "%LOG%" 2>&1
where python >> "%LOG%" 2>&1
python --version >> "%LOG%" 2>&1
if errorlevel 1 goto :fail
python -c "import platform,sys; print('platform=',platform.platform()); print('python=',sys.version); print('executable=',sys.executable)" >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

>> "%LOG%" echo.
>> "%LOG%" echo === Dependency check ===
python -m pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

>> "%LOG%" echo.
>> "%LOG%" echo === Full deterministic acceptance ===
python run_v6_5_4_acceptance.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

>> "%LOG%" echo.
>> "%LOG%" echo === Windows path / import sanity ===
python -c "from pathlib import Path; import app,scoremax_integration_v1; print('candidate_root=',Path.cwd()); print('app_release=',getattr(app,'SCOREMAX_RELEASE','unknown')); print('integration_release=',getattr(scoremax_integration_v1,'SCOREMAX_INTEGRATION_RELEASE','unknown'))" >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

>> "%LOG%" echo.
>> "%LOG%" echo WINDOWS_CLEAN_EXTRACTION_ACCEPTANCE=PASS
>> "%LOG%" echo Completed: %DATE% %TIME%
echo.
echo ============================================================
echo SCOREMAX V6.5.4 WINDOWS QUALIFICATION PASSED
echo Evidence: %CD%\%LOG%
echo ============================================================
exit /b 0

:fail
>> "%LOG%" echo.
>> "%LOG%" echo WINDOWS_CLEAN_EXTRACTION_ACCEPTANCE=FAIL
>> "%LOG%" echo Failed: %DATE% %TIME%
echo.
echo ============================================================
echo SCOREMAX V6.5.4 WINDOWS QUALIFICATION FAILED
echo Evidence: %CD%\%LOG%
echo Do not promote this build.
echo ============================================================
exit /b 1
