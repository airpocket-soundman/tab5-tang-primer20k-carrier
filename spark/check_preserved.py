from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent;data=json.loads((H/'sources/preserved-design-hashes.json').read_text(encoding='utf8'));root=Path(data['root'])
changed=[name for name,digest in data['files'].items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest]
out={'ok':not changed,'files_checked':len(data['files']),'changed':changed,'scope':'Pre-task source design snapshot, read-only validation'}
(H/'sources/preservation-check.json').write_text(json.dumps(out,indent=2)+'\n');print(out);raise SystemExit(0 if out['ok'] else 1)
