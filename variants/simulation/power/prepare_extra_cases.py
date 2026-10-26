from pathlib import Path
import json
h=Path(__file__).resolve().parent
for name,c in json.loads((h/'cases/extra-cases.json').read_text()).items():
 (h/'cases'/(name+'.json')).write_text(json.dumps(c,indent=2)+'\n')
