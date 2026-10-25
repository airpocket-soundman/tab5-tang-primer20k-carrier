from pathlib import Path
import json,hashlib,sys,itertools
sys.path.insert(0,'kicad/gen');import design
OUT=Path('cost-study/2026-10-25')
cs=design.build();parts={c.ref:c for c in cs}
groups=json.loads((OUT/'quote-normalized.json').read_text())
(OUT/'quote-normalized.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf8')
(OUT/'quote-raw.json').write_bytes((OUT/'quote-raw.json').read_bytes())
fee=52.53/17;boards=5;joint=.0016
# Assembly joint counts are a planning approximation; only unique active copper pad numbers counted.
# Conservative explicit groups for removed circuits. Unchanged surcharges remain constant.
def removal(refs,joints):
 cost=loading=0
 for g in groups:
  if not g['active']:continue
  n=sum(r in refs for r in g['refs'])
  if not n:continue
  amount=g['price'] if n==len(g['refs']) else n*5*g['price']/g['qty']
  cost+=amount
  if n==len(g['refs']) and g['kind']=='Extended':loading+=fee
 return dict(parts_saving=cost,loading_saving=loading,assembly_saving=joints*5*joint,total_saving=cost+loading+joints*5*joint)
hdmi={c.ref for c in cs if c.block in ('hdmi','tmds','tmdsc') and c.ref!='J5' and not c.dnp}
H=removal(hdmi,78)
DC=removal({'J2','U1','C2','R1','R2','R3','R5','D2'},33)
PD=removal({'D1'},2)
# Basic resistor network estimates, with replacement unit prices declared assumptions.
# R7 -> 3.3k || (100k+100k), two additional 2-pad parts per board.
r7new=5*.0022+10*(.0465/15)
r7save=.03+fee-r7new-2*2*5*joint
# Eight 499R -> sixteen 1k (six pairs 0603, two pairs 0402), eight additional resistors per board.
biasnew=60*(.0425/25)+20*.0022
biassave=.08+2*fee-biasnew-8*2*5*joint
ldosave=1.882+fee-5*.15
basics=r7save+biassave+ldosave
size_save_max=31.10-2
size_save_min=31.10-(25+6.10*99/125)
rows=[]
for a,h,small,power in itertools.product([False,True],[False,True],[False,True],['dual','pd','barrel']):
 savings=(r7save+ldosave if a else 0)+(biassave if a and not h else 0)+(H['total_saving'] if h else 0)+({'dual':0,'pd':PD['total_saving'],'barrel':DC['total_saving']}[power])
 lo=151.98-savings-(size_save_max if small else 0);hi=151.98-savings-(size_save_min if small else 0)
 rows.append(dict(basic_resistor_networks=a,hdmi_unpopulated=h,pcb_99x78=small,power=power,total_5boards_excluding_socket_low=round(lo,2),total_5boards_excluding_socket_high=round(hi,2),saving_low=round(151.98-hi,2),saving_high=round(151.98-lo,2),add_socket_pcba_cost='S mandatory, unquoted; includes procurement, loading, soldering and any fixture/consignment cost'))
summary=dict(date='2026-10-25',currency='USD',quantity=5,baseline_screenshot=151.98,baseline_parts=54.881,extended_types=17,loading_total=52.53,loading_each_in_this_quote=fee,spreadsheet_raw_sum=65.352,duplicate_sku_rows_not_additive=4.113,removed_socket_historical_price=6.358,hdmi=H,pd_only=PD,barrel_only=DC,basic_R7_saving=r7save,basic_HDMI_bias_saving=biassave,basic_LDO_saving=ldosave,basic_resistors_only_saving=r7save+biassave,basic_total_saving=basics,small_board_saving_range=[size_save_min,size_save_max],L1_extended_alternative_saving=6.9225-5*.246,assumptions=['Screenshot baseline includes 5 assembled boards, excludes J4 socket and Core module. Core module was never a purchased BOM item.','XC6206P332MR-G unit $.15 is a budget allowance; output load <=50mA and no PMOD power is assumed. LDO remains unverified until redesigned/tested.',
'R7 replacement3.3k unit $.0022 and new0402 1k unit $.0022 are budget allowances, not live quotes. Existing basic unit prices reused for other resistors.','Extended fees removed once per unique SKU, never once per component or board. HDMI/basic overlap removed.','PCB best case $2 promotional standard4-layer/5pcs <=100x100. Other end keeps $25 engineering plus area-proportional board charge. Neither is a new vendor quote.','No new schematic/layout, stock reservation, quote submission, coupon, shipping or tax included. No savings from deleting required power-off isolation.','Socket PCBA is mandatory; add S to every scenario. Current socket unavailable; substitute compatibility and PCBA charges unresolved.'],scenarios=rows)
(OUT/'cost-model.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for base in ['kicad/gen','kicad/lib','manufacturing/poc-2026-10-24'] for p in Path(base).rglob('*') if p.is_file() and '__pycache__' not in str(p)}
for p in Path('kicad').glob('*.kicad_*'):
 if p.suffix not in ('.kicad_prl',):protected[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
assert protected==json.loads((OUT/'preserved-design-hashes.json').read_text()), 'Current design differs from recorded cost-study baseline'
print({k:v for k,v in summary.items() if k not in ('scenarios','assumptions')})
