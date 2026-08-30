@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a V6.5.4 backup .db file onto this BAT or run: RESTORE_SCOREMAX_V6_5_4.bat path-to-backup.db
  goto :end
)
python scoremax_internal_live_backup_v654.py restore "%~1"
:end
pause
