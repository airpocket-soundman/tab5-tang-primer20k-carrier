"""Pin-level NPU-DOT-v0 tests with independent integer oracle; no hardware."""
from pathlib import Path
import argparse,random,struct,subprocess,os,json
ROOT=Path(__file__).resolve().parents[2]
def generate():
 base=(ROOT/'link/tests/tb_link_bringup.v').read_text().split('    initial begin')[0]
 base=base.replace('tb_link_bringup','tb_npu_link').replace('.TIMEOUT_CYCLES(5000)','.NPU_ENABLE(1),.TIMEOUT_CYCLES(5000)')
 base=base.replace('if(!ready || !data_oe)', 'for(n=0;n<2000 && !ready;n=n+1) #10;\n            if(!ready || !data_oe)')
 lines=['#100;reset_n=1;#100;arm=1;#100;'];count=0
 def cmd(op,val=0,status=0,result=None,corrupt=False):
  nonlocal count
  lines.append(f"send_request(8'h{op:02x},8'h{val&255:02x},8'h{val>>8&255:02x},{int(corrupt)});read_response();")
  lines.append(f"if(r[1]!==8'd{status}) $fatal(1,\"status command {count} got %d\",r[1]);")
  if result is not None:lines.append(f"if({{r[5],r[4]}}!==16'h{result&65535:04x}) $fatal(1,\"value command {count}\");")
  count+=1
 def cfg(bias,mult,shift,izp,ozp,lo,hi,length):
  v=struct.pack('<iihBhhhI',bias,mult,izp,shift,ozp,lo,hi,length)
  assert len(v)==21
  for i,b in enumerate(v):cmd(0x51,i|(b<<8))
 cmd(0x50,result=0x4e01);cmd(0x52,status=3);cmd(0x51,21,status=3);cmd(0x10,status=2)
 rng=random.Random(20261106)
 for j in range(32):
  cmd(0x55);pairs=[(rng.randrange(-128,128),rng.randrange(-128,128)) for _ in range([0,1,27,128][j%4])]
  bias=rng.randrange(-1000,1001);izp=rng.randrange(-128,128);mult=[0,1,3,2147483647][j%4];shift=[0,1,8,31,62][j%5];ozp=-7;lo,hi=(-128,127) if j%2 else (0,127)
  cfg(bias,mult,shift,izp,ozp,lo,hi,len(pairs));cmd(0x52)
  acc=bias
  for a,w in pairs:acc+=(a-izp)*w;cmd(0x53,(a&255)|((w&255)<<8))
  cmd(0x5a,result=acc);cmd(0x5b,result=(acc&0xffffffff)>>16)
  prod=acc*mult;mag=abs(prod);mag=(mag+(1<<(shift-1)) if shift else mag)>>shift;q=max(lo,min(hi,(-mag if prod<0 else mag)+ozp))
  cmd(0x56);lines.append('if({r[5],r[4]}==0) $fatal(1,"zero job cycles");');cmd(0x58)
  cmd(0x54,result=q);cmd(0x54,status=4);cmd(0x53,status=4)
 # reject high shift before narrowing; parameter faults, overflow, abort recovery
 for shift,mult,izp,ozp,lo,hi,length in [(128,1,0,0,-128,127,1),(0,-1,0,0,-128,127,1),(0,1,128,0,-128,127,1),(0,1,0,128,-128,127,1),(0,1,0,0,10,-10,1),(0,1,0,0,-128,127,1025)]:
  cmd(0x55);cfg(0,mult,shift,izp,ozp,lo,hi,length)
  # Core invalid config faults after accepted begin, adapter rejects narrow/length itself.
  cmd(0x52,status=3 if shift>62 or length>1024 else 0)
  if shift<=62 and length<=1024:cmd(0x54,status=3)
 for bias,a,w in [(2147483647,1,1),(-2147483648,1,-1)]:
  cmd(0x55);cfg(bias,1,0,0,0,-128,127,1);cmd(0x52);cmd(0x53,(a&255)|((w&255)<<8));cmd(0x5a,status=5);cmd(0x54,status=5)
 cmd(0x55);cfg(3,1,0,0,0,-128,127,1);cmd(0x52);cmd(0x54,status=7);cmd(0x52,status=3)
 cmd(0x55);cmd(0x51,0x1200,corrupt=True,status=1);cmd(0x52,status=3)
 lines+=['arm=0;#1;if(data_oe || ready)$fatal(1,"disarm OE");',f'$display("PASS NPU pin-level commands={count}, jobs=32, faults/CRC/watchdog");$finish;']
 return base+'    initial begin\n'+'\n'.join(lines)+'\n    end\n initial begin #100000000;$fatal(1,"global timeout");end\nendmodule\n',count

def main():
 p=argparse.ArgumentParser();p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 tb,count=generate();(a.output/'tb_npu_link.v').write_text(tb);binary=a.output/'test.vvp';env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','')
 sources=[ROOT/'link/rtl/link_bringup.v',*list((ROOT/'npu/rtl').glob('*.v')),a.output/'tb_npu_link.v'];logs=[]
 for c in [[a.iverilog,'-g2012','-Wall','-s','tb_npu_link','-o',str(binary),*map(str,sources)],[a.vvp,str(binary)]]:
  r=subprocess.run(c,env=env,capture_output=True,text=True,timeout=180);logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1]
 (a.output/'run.log').write_text('\n'.join(logs));(a.output/'result.json').write_text(json.dumps({'passed':True,'commands':count,'device_access':'none','output':logs[-1]},indent=2));print(logs[-1])
if __name__=='__main__':main()
