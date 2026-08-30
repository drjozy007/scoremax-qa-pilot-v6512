# ScoreMax V6.3 Admin Recovery

The fresh local/internal installation creates a random one-time `admin` password. Save it when first shown.

If the password is lost, run `reset_scoremax_admin_password.bat` from the extracted ScoreMax folder. The utility:

- locates the local database (`SCOREMAX_DB` if set, otherwise `scoremax_v4.db` beside the utility),
- creates a timestamped database backup before changing anything,
- resets only the Platform Admin password,
- increments `session_version` where available so existing Admin sessions are invalidated,
- runs `PRAGMA integrity_check` after the change.

This recovery utility is for the local/internal SQLite installation. Production recovery must use the production database/secret-management process rather than copying a live database to a laptop.
