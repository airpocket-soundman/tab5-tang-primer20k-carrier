"""Local Specctra round-trip; KiCad remains the source and review tool."""
from pathlib import Path
import json
import pcbnew
import design,sexp
K=Path(__file__).resolve().parents[1]
pcb=K/(design.PROJECT+'.kicad_pcb')
b=pcbnew.LoadBoard(str(pcb))
for t in b.GetTracks():t.SetLocked(True)
old={t.m_Uuid.AsString():t.GetNetname() for t in b.GetTracks()}
out=K/'sim/r5.dsn'
assert pcbnew.ExportSpecctraDSN(b,str(out))
changes=[(t.m_Uuid.AsString(),old[t.m_Uuid.AsString()],t.GetNetname()) for t in b.GetTracks() if old[t.m_Uuid.AsString()]!=t.GetNetname()]
assert not changes,('DSN export reassigned preserved copper',changes)
pcbnew.SaveBoard(str(pcb),b)
s=sexp.parse(out.read_text().replace('(string_quote ")',''))
network=sexp.first(s,'network')
classes=sexp.find(network,'class')
allnets={str(n) for n in b.GetNetsByName().keys()}-{''}
r4board=pcbnew.LoadBoard(str(K.parents[3]/'single-sided-r4/full/design/kicad/tab5-fpga-carrier.kicad_pcb'))
r4refs={fp.GetReference() for fp in r4board.GetFootprints()}
changed={'J2'}
affected={'VIN','+5V','DC_IN','VBUS_PD','CC1','CC2'}
for c in design.build():
    if c.ref not in r4refs or c.ref in changed:affected.update(n for n in c.pins.values() if n)
power={'+5V','BUCK_5V','TAB_HVIN','VBUS_PD','DC_IN','VIN'} & allnets
switch=set()
for c in classes:network.remove(c)
def cls(name,nets,width):
    return ['class',sexp.Str(name)]+[sexp.Str(n) for n in sorted(nets)]+[
      ['circuit',['use_via',sexp.Str('Via[0-3]_600:300_um')]],['rule',['width',str(width)],['clearance','127']]]
network.extend([cls('r5signals',affected-power-{'GND'},127),cls('r5power',power,500),cls('Preserved',allnets-affected-power|{'GND'},127)])
# Keep the r4 continuous reference layer free of new signal routing.
for layer in sexp.find(sexp.first(s,'structure'),'layer'):
    if layer[1]=='In1.Cu':sexp.first(layer,'type')[1]='power'
out.write_text(sexp.dump(s)+'\n')
(K/'sim/routing-export.json').write_text(json.dumps({'source':'KiCad10','input':str(pcb),'preserved_copper_net_reassignments':changes,'affected_nets':sorted(affected),'ignore_class':'Preserved','plane_layer':'In1.Cu'},indent=2)+'\n')
print('DSN written; existing copper locked and net identity checked')
