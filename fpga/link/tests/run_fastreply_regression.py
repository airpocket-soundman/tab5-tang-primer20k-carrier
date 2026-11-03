"""Run unchanged untagged golden vectors with the experimental TDP/RAW option enabled."""
import argparse,importlib.util,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');a=p.parse_args()
original=subprocess.run

def run(command,*args,**kwargs):
 if str(command[0])==a.iverilog and '-s' in command:
  command=list(command);top=command[command.index('-s')+1]
  command[1:1]=[f'-P{top}.FAST_REPLY_ENABLE=1'];command.append(str(ROOT/'link/rtl/link_reply_raw.v'))
 return original(command,*args,**kwargs)
subprocess.run=run
for name in ['run_triangle_rows','run_fractal_tile','run_triangle_bbox','run_triangle_tile']:
 spec=importlib.util.spec_from_file_location(name,ROOT/'gfx/tests'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 sys.argv=[name,'--iverilog',a.iverilog,'--vvp',a.vvp];m.main()
print('PASS legacy full golden suite with experimental FAST_REPLY_ENABLE=1; no hardware access')
