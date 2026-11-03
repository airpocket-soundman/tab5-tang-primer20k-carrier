"""Exact public-VO input/delayed-full cone; not a complete DDR/FIFO model."""
from pathlib import Path
import re,hashlib,json
root=Path(__file__).resolve().parents[2];p=root/'build/mem-bist-ip/generated/MemDDR3/MemDDR3.vo'
b=p.read_bytes();assert hashlib.sha256(b).hexdigest()=='4d37c875c609a5fa849033d8fbea3e63d3da8270322a663deff01f44874719ed'
s=b.decode().replace('\r\n','\n');cells={m[2].strip():(m[1],m[3]) for m in re.finditer(r'^(\w+) \\([^\n]+?)\s+\(\n(.*?)^\);',s,re.M|re.S)}
names=['gw3_top/u_gwmc_top/n8_s0','gw3_top/u_gwmc_top/app_en_s0','gw3_top/u_gwmc_top/gw_cmd0/n468_s1','gw3_top/u_gwmc_top/gw_cmd0/full_r_s0','gw3_top/u_gwmc_top/gw_cmd0/full_rr_s0','gw3_top/u_gwmc_top/gw_wr_data0/n756_s0','gw3_top/u_gwmc_top/gw_wr_data0/wr_wrbuf_s0']
for n in names:assert n in cells
assert "n8_s0 .INIT=8'hAC" in s and "n468_s1 .INIT=8'h70" in s and "n756_s0 .INIT=16'hF088" in s
assert '.I1(cmd_en)' in cells[names[0]][1]
assert '.CLK(clk_out)' in cells[names[1]][1]
# Eye-owner0: LUTAC passes cmd_en, LUTF088 passes wr_data_end&&wr_data_en.
for en in range(2):
 assert ((0xac>>(en<<1))&1)==en
 assert ((0xf088>>(en|(en<<1)))&1)==en
for fullr in range(2):
 for fullrr in range(2):
  for en in range(2):assert ((0x70>>(fullr|(fullrr<<1)|(en<<2)))&1)==(en and not(fullr and fullrr))
# Prescribed full transition isolates front acceptance from two full-delay stages.
# It is NOT a reconstructed controller full-state implementation.
app_old=app_new=fullr=fullrr=0;rows=[];old_extra=new_extra=0
for cycle,full in enumerate([0,0,1,1,1,1,1,1,0,0]):
 ready=1-full;old_en=1;new_en=ready
 old_extra+=int(full and old_en);new_extra+=int(full and new_en)
 rows.append(dict(cycle=cycle,full=full,ready=ready,old_cmd_en=old_en,new_cmd_en=new_en,
  old_registered_app_en=app_old,new_registered_app_en=app_new,full_r=fullr,full_rr=fullrr,
  old_ram_wre=app_old and not(fullr and fullrr),new_ram_wre=app_new and not(fullr and fullrr)))
 app_old,app_new,fullr,fullrr=old_en,new_en,full,fullr
assert old_extra==6 and new_extra==0
out={'scope':'public input/delayed-full cone; no proof of whole-controller overflow or root-cause fix',
 'generated_vo_sha256':hashlib.sha256(b).hexdigest(),'extra_registered_requests_while_ready0':{'old':old_extra,'strict_ready':new_extra},
 'equations':{'command_entry_eye0':'app_en_next=cmd_en','command_RAM_WRE':'app_en && !(full_r && full_rr)','write_entry_eye0':'wr_wrbuf_next=wr_data_en && wr_data_end'},
 'cells':{n:{'type':cells[n][0],'ports':cells[n][1]} for n in names},'prescribed_full_history':rows}
q=root/'build/mem-tests/ready_entry_cone.json';q.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print('PASS actual VO entry cone: old6 extra registered requests with ready0; strict0; whole FIFO/root cause not modeled')
