"""Build-only materialization of exact frozen receiver code; native startup unchanged."""
from pathlib import Path
import hashlib,sys,zipfile
root=Path(__file__).resolve().parents[1]
archive=root/'engineering/grouped_recovery_20261128_v3/SM_Consolidated_Receiver_20261128_V3.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='00ad354f025441da3c15d5508a9ef568ab4c7dd962a5b7bb1d857a7df14bbdbb','FROZEN_RECEIVER_ARCHIVE_DRIFT'
with zipfile.ZipFile(archive)as z:
 for n in z.namelist():assert not Path(n).is_absolute()and'..'not in Path(n).parts
 z.extractall(root/'engineering/grouped_recovery_20261128_v3')
sys.path.insert(0,str(root/'engineering/grouped_recovery_20261128_v3/candidate'))
from build_scoremax import main
print(main(root))

