from pathlib import Path
import subprocess,json
from prepare import prepare,HERE,FW,INDEX
prepare();out=HERE/'build';out.mkdir(exist_ok=True)
cmd=['D:/GitHub/airpocket-soundman/tab5-fpga-gpu-demo/build/test-tools/ziglang/zig.exe','c++','-std=c++17','-O2','-UNDEBUG','-ffp-contract=off','-Wall','-Wextra','-Werror','-I'+str(FW/'vendor/host/main/inference'),'-I'+str(INDEX),str(HERE/'test_binary.cpp'),'-o',str(out/'test_binary.exe')]
logs=[]
for c in [cmd,[str(out/'test_binary.exe')]]:
 r=subprocess.run(c,capture_output=True,text=True);logs.append({'command':c,'returncode':r.returncode,'output':r.stdout+r.stderr});assert r.returncode==0,logs[-1]
(out/'binary-result.json').write_text(json.dumps({'passed':True,'hardware_access':False,'commands':logs},indent=2)+'\n');print(logs[-1]['output'])
