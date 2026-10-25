"""KiCad <-> DSN/SES bridge. Never overwrite the input PCB on export.

KiCad Python: freeroute_io.py export input.kicad_pcb candidate.dsn
KiCad Python: freeroute_io.py import input.kicad_pcb result.ses result.kicad_pcb
Existing TMDS and BUCK_PH/BOOT traces are locked before DSN export.
"""
from pathlib import Path
import sys
import re
import pcbnew

mode, source, target = sys.argv[1:4]
board=pcbnew.LoadBoard(str(Path(source).resolve()))
if mode == 'export':
    for t in board.GetTracks():
        n=t.GetNetname()
        if n.startswith('HDMI_D') or n.startswith('HDMI_CK') or n in ('BUCK_PH','BUCK_BOOT'):
            t.SetLocked(True)
    assert pcbnew.ExportSpecctraDSN(board,str(Path(target).resolve()))
    path=Path(target)
    dsn=path.read_text(encoding='utf-8')
    # KiCad's export gives an SMD-SMD override of one quarter of the default
    # gap. Restore the actual board rule; do not loosen DRC to ease routing.
    dsn=re.sub(r'\(clearance [0-9.]+ \(type smd_smd\)\)', '(clearance 127 (type smd_smd))', dsn)
    # Keep the uninterrupted In1 GND reference available only to planes.
    dsn=dsn.replace('(circuit\n', '(circuit\n        (use_layer F.Cu In2.Cu B.Cu)\n')
    path.write_text(dsn,encoding='utf-8')
    print('Exported',target)
elif mode == 'import':
    assert len(sys.argv)==5
    assert pcbnew.ImportSpecctraSES(board,str(Path(target).resolve()))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(Path(sys.argv[4]).resolve()),board)
    print('Imported',target,'to',sys.argv[4])
else:
    raise ValueError(mode)
