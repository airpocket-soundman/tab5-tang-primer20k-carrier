"""Call the documented local EasyEDA bridge; code is read from an explicit file."""
import json,sys,urllib.request,urllib.error
from pathlib import Path
code=Path(sys.argv[1]).read_text(encoding='utf8')
request=urllib.request.Request('http://127.0.0.1:49620/execute',data=json.dumps({'code':code}).encode(),headers={'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(request,timeout=55) as response:result=json.load(response)
except urllib.error.HTTPError as error:
 result=json.loads(error.read().decode('utf8'))
for _ in range(2):
 if isinstance(result,str):result=json.loads(result)
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if not result.get('success'):raise SystemExit(json.dumps(result,ensure_ascii=False))
print(json.dumps(result,ensure_ascii=False,indent=2))
