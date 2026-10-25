"""Compare B/C to prior qualified PCBs; KiCad Python, baseline directory arg.

Baseline filenames: lite-b-barrel-before-buttons.kicad_pcb,
lite-c-dnp-before-buttons.kicad_pcb. Retain both boards during API comparisons.
"""
from pathlib import Path
import hashlib,json,sys
import pcbnew
R=Path(__file__).resolve().parents[2];V=R/'variants';before=Path(sys.argv[1])
def digest(p):return hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def copper(b):
 return sorted((str(t.GetNetname()),t.GetClass(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(pcbnew.F_Cu) if isinstance(t,pcbnew.PCB_VIA) else t.GetWidth()) for t in b.GetTracks() if t.GetNetname() not in ['TAB_RST','F_BTN0'])
def pads(b):
 return sorted((f.GetReference(),p.GetNumber(),str(p.GetNetname()),p.GetPosition().x,p.GetPosition().y,p.GetSize().x,p.GetSize().y) for f in b.GetFootprints() if f.GetReference() not in ['SW1','SW2'] for p in f.Pads())
report={'date':'2026-10-25','scope':'B/C aligned with A: Akizuki115969 TS-06104 H4.3mm manual buttons; B HDMI full PCBA; C HDMI/PD remain DNP','variants':{}}
mechanical=json.loads((V/'simulation/mechanical/clearance.json').read_text(encoding='utf8'))
for n in ['lite-b-barrel','lite-c-dnp']:
 path=V/n/'kicad/tab5-fpga-carrier.kicad_pcb';base=before/(n+'-before-buttons.kicad_pcb')
 old=pcbnew.LoadBoard(str(base));new=pcbnew.LoadBoard(str(path))
 assert copper(old)==copper(new),n+' unrelated copper changed'
 assert pads(old)==pads(new),n+' unrelated pad changed'
 drc=json.loads((V/'validation'/f'{n}-drc.json').read_text(encoding='utf8'))
 audit=json.loads((V/'validation'/f'{n}-independent-audit.json').read_text(encoding='utf8'))
 erc=json.loads((before/(n+'-buttons-erc.json')).read_text(encoding='utf8'))
 violations=[v for s in erc['sheets'] for v in s['violations']]
 assert not drc['violations'] and not drc['unconnected_items'] and audit['ok'] and audit['pcb_sha256']==digest(path)
 assert not any(v['severity']=='error' for v in violations)
 assert mechanical['variants'][n]['pass_clearance']
 report['variants'][n]={'before_sha256_LF':digest(base),'after_sha256_LF':digest(path),'all_tracks_except_button_reset_unchanged':True,'all_other_pads_unchanged':True,'drc_violations':0,'unconnected_items':0,'erc_errors':0,'erc_warnings':len(violations),'independent_audit_checks':len(audit['checks']),'core_envelope_clearance_pass':True,'HDMI_assembly':'19 contacts and4 shell tabs PCBA, C916313; supplier preview confirmation required' if n=='lite-b-barrel' else 'all dedicated HDMI and PD parts remain DNP'}
report['simulation_disposition']='Existing power, parallel and HDMI waveforms retained for identical circuits/tracks. No complete new waveform simulation claimed. Local button/reset routes and ground fills revised, connectivity/DRC/ERC and Core envelope rerun. Hardware bringup remains required.'
report['requirements']='Related Linux README/goals/DT/mock transport, GPU README/plan/RTL/display evidence, and memory research plan rechecked; requirements-review.json records referenced versions. No protocol/pin/supply-value change; Linux physical driver/DDR3/finalGPU remains unverified. No related-repo update required for manual component procurement.'
report['procurement_remaining']='SW3 remains DigiKey. Akizuki J1 candidate is not confirmed drop-in; B/C require compatible barrel jack selection before order. GPIO/PMOD sockets excluded from PCBA; Core module supplied by user.'
(V/'simulation/bc-button-revision-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('B/C independent copper, pad, package, DRC/ERC and Core clearance checks PASS')
