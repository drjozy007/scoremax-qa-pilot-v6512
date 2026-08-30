@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a V6.5.3 backup .db file onto this BAT or run: RESTORE_SCOREMAX_V6_5_3.bat path-to-backup.db
  pause
  exit /b 2
)
python scoremax_internal_live_backup_v653.py restore "%~1"
pause
