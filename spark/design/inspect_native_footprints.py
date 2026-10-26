from pathlib import Path
import zipfile,json,sys
H=Path(__file__).resolve().parent
z=zipfile.ZipFile(H/'easyeda/spark-akizuki-migration-review.epro2');uid=json.loads((H/'easyeda/footprint-map.json').read_text())[sys.argv[1] if len(sys.argv)>1 else 'SW3'];active=None
text=z.read(next(n for n in z.namelist() if n.endswith('.epru'))).decode()
for l in text.splitlines():
 if '||' not in l:continue
 h,b=l.split('||',1);h=json.loads(h);b=json.loads(b.rstrip('|'))
 if h['type']=='DOCHEAD':active=b.get('uuid')
 if active==uid and h['type']=='PAD':print(b)
