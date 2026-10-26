"""Retain results only when all extracted SI model inputs are exactly unchanged."""
from pathlib import Path
import json,subprocess,hashlib
H=Path(__file__).resolve().parent;P=H/'simulation/parallel/extracted-paths.json'
old=json.loads(P.read_text());subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe',str(H/'simulation/parallel/extract_paths.py')],check=True);new=json.loads(P.read_text())
a=old['spark-full-pcba'];b=new['spark-full-pcba']
assert a['signals']==b['signals'] and a['coupled_parallel_spans']==b['coupled_parallel_spans']
run=json.loads((H/'simulation/parallel/spark-full-pcba-final680.json').read_text())
assert run['sourcePCBhash']==a['sourcePCBhash']
out={'ok':True,'simulated_pcb_normalized_sha256':run['sourcePCBhash'],'current_pcb_normalized_sha256':b['sourcePCBhash'],'all_extracted_signal_inputs_equal':True,'reason':'Last change adds solder-mask openings on SW3 PTH pads; no signal model input changed. Existing150-case results retained without relabeling their original source hash.','limits':'Extraction equality does not validate ground-return fields or manufacturing masks; 3D EM and hardware remain unverified.'}
(H/'simulation/parallel/current-binding.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
