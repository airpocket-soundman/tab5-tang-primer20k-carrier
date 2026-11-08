"""Native exact comparison of canonical graph vs bounded-index32 with real hard-MAC test double."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,shutil
from prepare import prepare,HERE,FW
HOST=Path('D:/github/airpocket-soundman/tab5-fpga-gpu-resume-20261106')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--compiler',type=Path,default=Path('D:/GitHub/airpocket-soundman/tab5-fpga-gpu-demo/build/test-tools/ziglang/zig.exe'));p.add_argument('--output',type=Path,default=HERE/'build/native');a=p.parse_args();out=a.output.resolve();assert out.is_relative_to(HERE.resolve());out.mkdir(parents=True,exist_ok=False);generated=prepare();package=HOST/'build/rtdetr-graph-300-quant/model.rqg';inp=HOST/'build/rtdetr-graph-300/input.f32';oldgolden=HOST/'build/rtdetr-fpga-backend-final-off/output.f32'
 # Real service uses the existing generic integer kernel double, real hooks,
 # source package, image conversion and cache. The only linked replacement is graph.cpp.
 sources=[HOST/'tests/rtdetr_device_run_native.cpp',HOST/'main/inference/rtdetr_device_run.cpp',FW/'vendor/host/main/inference/rtdetr_fpga_backend.cpp'];cc=[str(a.compiler),'c++','-std=c++17','-O2','-UNDEBUG','-ffp-contract=off','-Wall','-Wextra','-Werror','-I'+str(HOST/'main'),'-I'+str(FW/'vendor/host/main/inference'),'-I'+str(HERE)]
 import numpy as np
 x=np.fromfile(inp,dtype='<f4').reshape(3,640,640);rgb=x[::-1].transpose(1,2,0).astype('u1');ppm=out/'CREW640.PPM';ppm.write_bytes(b'P6\n640 640\n255\n'+rgb.tobytes());assert (rgb.transpose(2,0,1)[::-1].astype('f4')==x).all();logs=[];passed=False
 try:
  for name,graph in [('baseline',FW/'vendor/host/main/inference/rtdetr_graph.cpp'),('index32',generated)]:
   exe=out/(name+'.exe');golden=oldgolden if name=='baseline'else out/'baseline.f32'
   for cmd in [cc+list(map(str,sources))+[str(graph),'-o',str(exe)],[str(exe),str(package),str(ppm),str(golden),str(out/(name+'.f32'))]]:
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=1200);logs.append({'command':cmd,'returncode':r.returncode,'output':r.stdout+r.stderr});(out/'commands.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8');print(r.stdout+r.stderr,flush=True);assert r.returncode==0,logs[-1]
  assert(out/'baseline.f32').read_bytes()==(out/'index32.f32').read_bytes();passed=True
 finally:
  report={'passed':passed,'hardware_access':False,'scope':'Actual full649node service with57Conv/65MM hard-MAC integer double; only graph.cpp index arithmetic differs; all1800F32bits must match, not physical board','canonical_graph_sha256':sha(FW/'vendor/host/main/inference/rtdetr_graph.cpp'),'index32_graph_sha256':sha(generated),'index32_contract_sha256':sha(HERE/'index32_contract.hpp'),'package_sha256':sha(package),'input_sha256':sha(inp),'output_sha256':sha(out/'index32.f32')if(out/'index32.f32').exists()else None};(out/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
