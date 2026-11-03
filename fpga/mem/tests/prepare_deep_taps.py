"""Output-only observation of exact public vendor netlist; no protected input read."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[2]
p=root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo'
b=p.read_bytes();assert hashlib.sha256(b).hexdigest()=='4d37c875c609a5fa849033d8fbea3e63d3da8270322a663deff01f44874719ed'
s=b.decode().replace('\r\n','\n');prefix='gw3_top/u_gwmc_top/'
fields=[('cmd_wptr',0,3,'gw_cmd0/waddr'),('cmd_rptr',3,3,'gw_cmd0/raddr'),('cmd_full',6,1,'@gw3_top/full'),('cmd_empty',7,1,'cmd_empty_Z'),('cmd_full_delayed',8,1,'gw_cmd0/full_r'),('cmd_full_delayed2',9,1,'gw_cmd0/full_rr'),('cmd_accept',10,1,'cmd_accept_Z'),('send_wr',11,1,'send_wr'),('write_full',12,1,'gw_wr_data0/wr_buf_full'),('write_empty',13,1,'gw_wr_data0/wr_fifo/wr_buf_empt'),('eye_cmd_owner',14,1,'eye_calib_start_cmd'),('eye_addr_owner',15,1,'eye_calib_start_addr'),('write_rptr',16,5,'gw_wr_data0/wr_fifo/rbin'),('write_wptr',21,5,'gw_wr_data0/wr_fifo/wbin')]
assigns=[];audit=[]
cells=list(re.finditer(r'^(\w+) \\([^\n]+?)\s+\(\n(.*?)^\);',s,re.M|re.S))
for name,lo,width,net in fields:
 net=net[1:] if net.startswith('@') else prefix+net
 token='\\'+net+' '
 assert token in s,net
 drivers=[]
 for c in cells:
  if re.search(r'\.(Q|F|O)\('+re.escape(token),c[3]):drivers.append({'cell':c[2].strip(),'type':c[1],'ports':c[3]})
 assert drivers,net
 # Sequential pointer/status sources all USER-clocked; combinational cones audited separately.
 for d in drivers:
  if d['type'].startswith('DFF'):assert '.CLK(clk_out)' in d['ports'],d
 assigns.append('assign deep_taps[%d+:%d] = %s;'%(lo,width,token))
 audit.append({'name':name,'bit':lo,'width':width,'net':net,'drivers':drivers})
assigns.append("assign deep_taps[63:26] = 38'b0;")
port='\tdeep_taps,\n';decl='output [63:0] deep_taps;\n';tail='\n'.join(assigns)+'\n'
out=s.replace('module MemDDR3(\n','module MemDDR3(\n'+port,1).replace('input clk;','input clk;\n'+decl,1)
end=out.rfind('endmodule');out=out[:end]+tail+out[end:]
# Remove only additions and prove every original byte/primitive unchanged.
back=out.replace(port,'',1).replace('\n'+decl,'',1).replace(tail,'',1)
assert back==s
assert back.replace("\n","\r\n").encode()==b
q=root/'build/mem-deep-input';q.mkdir(parents=True,exist_ok=True)
(q/'MemDDR3_tapped.vo').write_text(out)
(q/'tap_audit.json').write_text(json.dumps({'source_sha256':hashlib.sha256(b).hexdigest(),'original_logic_byte_exact':True,'fields':audit},indent=2)+'\n')
print('PASS output-only26 observed bits; original netlist byte-equivalent')

