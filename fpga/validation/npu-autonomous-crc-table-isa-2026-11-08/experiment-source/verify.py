from pathlib import Path
import subprocess,json,zlib,hashlib,struct
HERE=Path(__file__).resolve().parent
out=HERE/'build/native';out.mkdir(parents=True,exist_ok=True)
package=Path('D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106/build/rtdetr-graph-300-quant/model.rqg')
compiler='D:/GitHub/airpocket-soundman/tab5-fpga-gpu-demo/build/test-tools/ziglang/zig.exe'
cmd=[compiler,'c++','-std=c++17','-O2','-UNDEBUG','-Wall','-Wextra','-Werror',str(HERE/'test_crc.cpp'),'-o',str(out/'test.exe')]
r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,r.stdout+r.stderr
r=subprocess.run([str(out/'test.exe'),str(package)],capture_output=True,text=True);assert r.returncode==0,r.stdout+r.stderr
b=package.read_bytes();assert hashlib.sha256(b).hexdigest()=='775b42010c82da0d464db21812563122539b090bc236af7c610eba0f1257d251';h=struct.unpack_from('<16I',b);expected=zlib.crc32(b[h[6]:h[6]+h[7]]);assert expected==h[10],(hex(expected),h)
assert ('crc=%08x'%expected)in r.stdout
result={'passed':True,'native_output':r.stdout,'package_bytes':len(b),'payload_bytes':h[7],'expected_header_crc':h[10],'independent_zlib_crc':expected,'package_sha256':hashlib.sha256(b).hexdigest(),'scope':'C++ table vs original bitwise plus Python zlib pinned payload; chunk boundaries/cancel calls/out unchanged on failures; not fullNN or board proof','hardware_access':False}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
