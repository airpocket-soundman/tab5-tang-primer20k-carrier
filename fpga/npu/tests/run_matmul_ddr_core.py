"""Replay the real host MatMul adapter trace through unchanged4E21 full pin core.
No device access. Native host oracle checks full QK197x64x197, the trace contains
its quantized writes, every actual Conv descriptor, and every INT32 readback.
"""
import argparse,hashlib,json,os,struct,subprocess,re
from pathlib import Path
from run_npu_ddr_core_8oc import NATIVE,OLD_TB,ROOT
MAIN=r'''
 integer ops,opn,len,nbytes,timeout;reg[7:0]expbytes[0:1023];
 initial begin
 for(i=0;i<65536;i=i+1)mem[i]=8'ha5;
 #200;reset_n=1;arm=1;#1000;pll_lock=1;ip_user_reset=0;
 timeout=0;while(!dut.memory_ready && timeout<100000)begin @(posedge clk);#1;timeout=timeout+1;end
 if(!dut.memory_ready)$fatal(1,"DDR settle");
 payload[0]=8'h11;payload[1]=8'h22;payload[2]=8'h33;payload[3]=8'h44;command(8'h75,4,0,0);
 f=$fopen("VECTORS","r");if(!f)$fatal(1,"vectors");rc=$fscanf(f,"%d",ops);
 for(j=0;j<ops;j=j+1)begin
 rc=$fscanf(f,"%d %d %d",opn,len,nbytes);if(rc!=3)$fatal(1,"vector header");
 for(i=0;i<len;i=i+1)begin rc=$fscanf(f,"%d",v);payload[i]=v;end
 for(i=0;i<nbytes;i=i+1)begin rc=$fscanf(f,"%d",v);expbytes[i]=v;end
 send_request(opn,len,0,0);read_response(nbytes);
 if(got_status!==0 || (nbytes&&got_value!==nbytes))$fatal(1,"MatMul wire status j%d op%h status%d value%d",j,opn,got_status,got_value);
 for(i=0;i<nbytes;i=i+1)if(r[8+i]!==expbytes[i])$fatal(1,"MatMul INT32 mismatch command%d byte%d got%h expected%h",j,i,r[8+i],expbytes[i]);
 end
 $display("PASS DDR MatMul MATRIX_LABEL realhosttrace commands=%0d pins+4E21+actualadapter+INT32oracle",packets);$finish;
 end
 initial begin #2000000000;$fatal(1,"global timeout");end
endmodule
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trace',type=Path,required=True);p.add_argument('--label',default='fullQK197x64x197');p.add_argument('--iverilog',required=True);p.add_argument('--vvp',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);o=a.output.resolve();cmds=[];counts={}
 for line in a.trace.read_text().splitlines():
  v=line.split();op=v[0];counts[op]=counts.get(op,0)+1
  if op=='T':cmds.append((0x68,bytes.fromhex(v[1]),b''))
  else:
   address,n=int(v[1]),int(v[2]);data=bytes.fromhex(v[3]);assert len(data)==n
   desc=struct.pack('<IH2x',address,n)
   if op=='W':assert n<=2032 and address%16==n%16==0;cmds.append((0x71,desc+data,b''))
   else:assert n<=1024 and address%16==n%16==0;cmds.append((0x70,desc,data))
 vec=o/'vectors.txt'
 with vec.open('w')as f:
  f.write(str(len(cmds))+'\n')
  for op,data,expected in cmds:f.write(f'{op} {len(data)} {len(expected)}\n'+' '.join(map(str,data))+'\n'+' '.join(map(str,expected))+'\n')
 native=NATIVE.replace('mem[0:262143]','mem[0:65535]')
 native=re.sub(r'function\[31:0\]mapped;.*?endfunction',"function[31:0]mapped;input[31:0]a;begin if(a>=32'h400000 && a<32'h410000)mapped=a-32'h400000;else mapped=32'hffffffff;end endfunction",native)
 tb=OLD_TB.split(' initial begin')[0].replace("wire[7:0]bus_data=host_oe?host_data:data_oe?data_o:8'bz;","wire[7:0]bus_data;assign bus_data=host_oe?host_data:8'bz;")
 tb=tb.replace(' npu_conv_link #(.TIMEOUT(700000)) dut(clk,reset_n,arm,bus_clk,dir,bus_data,data_o,data_oe,ready);',native).replace('n=8+words*4+2','n=8+words+2').replace('dut.state','dut.link.state')
 source=o/'tb_matmul_ddr.v';source.write_text((tb+MAIN).replace('VECTORS',vec.as_posix()).replace('MATRIX_LABEL',a.label));binary=o/'test.vvp';sources=[ROOT/'npu/rtl'/n for n in ['npu_ddr_core_8oc.v','npu_ddr_sys.v','npu_ddr_arbiter.v','npu_ddr_tile_loader_8oc.v','conv_tile_engine_8oc.v']]+[ROOT/'mem/rtl'/n for n in ['memv1_bridge.v','mem_adapter.v','memv1_crc32b.v']];logs=[];env=dict(os.environ);env['PATH']=str(Path(a.iverilog).parent)+os.pathsep+env.get('PATH','');result={'passed':False,'commands':len(cmds),'matrix_label':a.label,'trace_counts':counts,'trace_sha256':hashlib.sha256(a.trace.read_bytes()).hexdigest(),'scope':'RTL model only, no device/PHY, unchanged4E21 engine'}
 try:
  for cmd in [[a.iverilog,'-g2012','-Wall','-s','tb_conv_link','-o',str(binary),*map(str,sources),str(source)],[a.vvp,str(binary)]]:
   r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=1200);logs.append(r.stdout+r.stderr);assert r.returncode==0,logs[-1]
  result.update(passed=True,source_sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest()for x in sources},output=logs[-1]);print(logs[-1])
 finally:(o/'result.json').write_text(json.dumps(result,indent=2)+'\n');(o/'run.log').write_text('\n'.join(logs))
if __name__=='__main__':main()
