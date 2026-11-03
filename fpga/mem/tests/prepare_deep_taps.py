"""Output-only observation of exact public vendor netlist; no protected input read."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[2]
p=root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo'
b=p.read_bytes();assert hashlib.sha256(b).hexdigest()=='4d37c875c609a5fa849033d8fbea3e63d3da8270322a663deff01f44874719ed'
s=b.decode().replace('\r\n','\n');prefix='gw3_top/u_gwmc_top/'
fields=[('cmd_wptr',0,3,'gw_cmd0/waddr'),('cmd_rptr',3,3,'gw_cmd0/raddr'),('cmd_full',6,1,'@gw3_top/full'),('cmd_empty',7,1,'cmd_empty_Z'),('cmd_full_delayed',8,1,'gw_cmd0/full_r'),('cmd_full_delayed2',9,1,'gw_cmd0/full_rr'),('cmd_accept',10,1,'cmd_accept_Z'),('send_wr',11,1,'send_wr'),('write_full',12,1,'gw_wr_data0/wr_buf_full'),('write_empty',13,1,'gw_wr_data0/wr_fifo/wr_buf_empt'),('eye_cmd_owner',14,1,'eye_calib_start_cmd'),('eye_addr_owner',15,1,'eye_calib_start_addr'),('write_rptr',16,5,'gw_wr_data0/wr_fifo/rbin'),('write_wptr',21,5,'gw_wr_data0/wr_fifo/wbin')]
fields += [('head_write',26,1,'cmd_buf_dou [27]'),('head_read',27,1,'cmd_buf_dou [28]'),
 ('pre_info_valid',28,1,'gwmc_bank_ctrl/pre_info_valid'),('issue_write',29,1,'n219_4'),('issue_read',30,1,'n219_5'),
 ('init_done',31,1,'gwmc_bank_ctrl/init_done_r'),('bank_state',32,26,'gwmc_bank_ctrl/gwmc_pstate'),
 ('refresh_request',58,1,'refresh_request_Z'),('self_refresh_request',59,1,'sre_request_Z'),
 ('idle1',60,1,'idle1'),('idle2',61,1,'idle2'),('idle3',62,1,'idle3'),('init_enable',63,1,'n107_3')]

assigns=[];audit=[]
cells=list(re.finditer(r'^(\w+) \\([^\n]+?)\s+\(\n(.*?)^\);',s,re.M|re.S))
for name,lo,width,net in fields:
 net=net[1:] if net.startswith('@') else prefix+net
 token='\\'+net+' '
 if ' [' in net:token='\\'+net.split(' [')[0]+' ['+net.split(' [')[1]
 assert token in s,net
 drivers=[]
 for c in cells:
  if re.search(r'\.(Q|F|O)\('+re.escape(token),c[3]):drivers.append({'cell':c[2].strip(),'type':c[1],'ports':c[3]})
 if not drivers and ' [' in net:
  base=net.split(' [')[0];drivers=[{'cell':c[2].strip(),'type':c[1],'ports':c[3]} for c in cells if re.search(r'\.DO\([^\n]*'+re.escape('\\'+base+' '),c[3])]
 assert drivers,net
 # Sequential pointer/status sources all USER-clocked; combinational cones audited separately.
 for d in drivers:
  if d['type'].startswith(('DFF','RAM16')):assert '.CLK(clk_out)' in d['ports'],d
 if name=='bank_state':
  assigns.append("assign deep_taps[%d+:%d] = %s & 26'h0277efed;"%(lo,width,token))
 else:assigns.append('assign deep_taps[%d+:%d] = %s;'%(lo,width,token))
 audit.append({'name':name,'bit':lo,'width':width,'net':net,'drivers':drivers})
assert sum(x[2] for x in fields)==64
port='\tdeep_taps,\n';decl='output [63:0] deep_taps;\n';tail='\n'.join(assigns)+'\n'
out=s.replace('module MemDDR3(\n','module MemDDR3(\n'+port,1).replace('input clk;','input clk;\n'+decl,1)
end=out.rfind('endmodule');out=out[:end]+tail+out[end:]
# Remove only additions and prove every original byte/primitive unchanged.
back=out.replace(port,'',1).replace('\n'+decl,'',1).replace(tail,'',1)
assert back==s
assert back.replace("\n","\r\n").encode()==b
# The declared state vector has no whole-vector, dynamic-index, or range use.
# Prove each unavailable position has no original reference or driver, rather
# than assuming aliases for separately named idle flip-flops.
state_token='\\'+prefix+'gwmc_bank_ctrl/gwmc_pstate '
state_uses=[]
for m in re.finditer(re.escape(state_token),s):
 suffix=s[m.end():].split('\n',1)[0]
 if suffix==';':continue
 bit=re.match(r'\[(\d+)\]',suffix)
 assert bit,('whole-vector/dynamic-index state reference',suffix)
 state_uses.append(int(bit[1]))
holes=[1,4,12,19,23,24]
assert sorted(set(range(26))-set(state_uses))==holes
valid_mask=sum(1<<i for i in set(state_uses));assert valid_mask==0x0277efed
for bit in set(state_uses):
 q='\\'+prefix+'gwmc_bank_ctrl/gwmc_pstate ['+str(bit)+']'
 ds=[c for c in cells if '.Q('+q+')' in c[3]]
 assert len(ds)==1 and '.CLK(clk_out)' in ds[0][3],(bit,ds)
state_audit={'valid_mask_hex':'0x0277EFED','unavailable_positions':holes,
 'explicit_zero_raw_bits':[32+i for i in holes],'no_whole_vector_or_dynamic_index_use':True,
 'original_reference_counts':{str(i):state_uses.count(i) for i in range(26)}}
def scalar_cone(net,seen=None):
 seen=set() if seen is None else seen
 if net in seen:return []
 seen.add(net)
 token='\\'+net+' '
 matches=[c for c in cells if re.search(r'\.(Q|F|O)\('+re.escape(token)+r'\)',c[3])]
 assert len(matches)==1,(net,len(matches))
 c=matches[0]
 if c[1].startswith('DFF'):
  assert '.CLK(clk_out)' in c[3],(net,c[2]);return [c[2].strip()]
 assert c[1].startswith(('LUT','MUX','INV')),(net,c[1])
 result=[]
 for port,value in re.findall(r'\.(I\d*|S\d*)\(([^\n]*)\)',c[3]):
  if value in ['GND','VCC']:continue
  assert value.startswith('\\'),(net,port,value)
  value=value[1:].strip()
  if ' [' in value:
   base=value.split(' [')[0];bit=value.split(' [')[1].split(']')[0]
   ds=[d for d in cells if re.search(r'\.Q\('+re.escape('\\'+base+' ['+bit+']')+r'\)',d[3])]
   assert len(ds)==1 and '.CLK(clk_out)' in ds[0][3],(net,value,ds)
   result.append(ds[0][2].strip())
  else:result+=scalar_cone(value,seen)
 return sorted(set(result))
cones={name:scalar_cone(prefix+net) for name,_,_,net in fields if name in ['issue_write','issue_read','init_enable']}
q=root/'build/mem-deep-input';q.mkdir(parents=True,exist_ok=True)
(q/'MemDDR3_tapped.vo').write_text(out)
(q/'tap_audit.json').write_text(json.dumps({'source_sha256':hashlib.sha256(b).hexdigest(),'original_logic_byte_exact':True,'fields':audit,'combinational_clock_boundaries':cones,'state_availability':state_audit},indent=2)+'\n')
print('PASS output-only64 observed bits; original netlist byte-equivalent')

