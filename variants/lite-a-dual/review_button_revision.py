"""Independent comparison to last published A; KiCad Python, baseline argument."""
from pathlib import Path
import hashlib,json,sys,subprocess
import pcbnew
H=Path(__file__).resolve().parent;R=H.parents[1]
old=pcbnew.LoadBoard(sys.argv[1]);new=pcbnew.LoadBoard(str(H/'kicad/tab5-fpga-carrier.kicad_pcb'))
def tracks(b):
 return sorted((t.GetNetname(),t.GetClass(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth()) for t in b.GetTracks() if t.GetNetname() not in ['TAB_RST','F_BTN0'])
def pads(b):
 return sorted((f.GetReference(),p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y,p.GetSize().x,p.GetSize().y) for f in b.GetFootprints() if f.GetReference() not in ['SW1','SW2'] for p in f.Pads())
assert tracks(old)==tracks(new),'Unrelated track changed'
assert pads(old)==pads(new),'Unrelated pad changed'
drc=json.loads((R/'variants/validation/lite-a-dual-drc.json').read_text(encoding='utf8'))
assert not drc['violations'] and not drc['unconnected_items']
erc=json.loads(Path('D:/tmp/buttons-erc.json').read_text(encoding='utf8'))
errors=[v for s in erc['sheets'] for v in s['violations'] if v['severity']=='error'];assert not errors
versions={}
for n in ['tab5-linux-fpga','tab5-fpga-gpu','esp32p4-linux-fpga-memory']:
 versions[n]=subprocess.check_output(['git','-C',str(Path('D:/github/airpocket-soundman')/n),'rev-parse','HEAD'],text=True).strip()
report={'date':'2026-10-25','scope':'A only; user requested Akizuki-first manual buttons and full HDMI PCBA',
 'before_sha256_LF':hashlib.sha256(Path(sys.argv[1]).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
 'after_sha256_LF':hashlib.sha256((H/'kicad/tab5-fpga-carrier.kicad_pcb').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
 'all_tracks_except_button_reset_unchanged':True,'all_other_pads_unchanged':True,
 'switch':'TS-06104 H4.3mm / Akizuki115969; normally open momentary, A/B common=1 C/D common=2',
 'drawing':'reference/TS-06104.pdf p8; 1.8x1.0mm pads, centers X+/-4.1 Y+/-2.25mm',
 'drc_violations':0,'unconnected_items':0,'erc_errors':0,'erc_warnings':sum(len(s['violations']) for s in erc['sheets']),
 'simulation_disposition':'No new transient simulation claimed. Existing parallel, power and HDMI circuit/track models retained because those nets and other pads are identical. GND fill changes locally around manual switch pads; DRC and mechanical envelope rerun. New button/reset local routes checked for connectivity. Hardware bringup still required.',
 'mechanical':'Core envelope swept with manufacturer4.3mm button height; pass in mechanical/clearance.json',
 'related_repositories':versions,'requirements_disposition':'README/goals, Linux DT/mock transport, GPU plan/display/RTL and memory research plan reviewed. No bus pins, protocol, supply values or separate-bitstream assumptions changed; physical driver/DDR3/GPU remains unverified.',
 'manual_exception':'SW3 CTS206-1S remains DigiKey. J1 Akizuki candidate not confirmed drop-in; PD12V can operate without J1.',
 'HDMI_PCBA':'J5 C916313 includes all19 SMT contacts and4 shell tabs; confirm supplier assembly preview'}
(R/'variants/simulation/button-revision-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Button revision independent geometry comparison PASS')
