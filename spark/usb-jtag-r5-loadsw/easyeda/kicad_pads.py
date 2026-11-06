import pcbnew, json
b = pcbnew.LoadBoard(r'D:\github\airpocket-soundman\tab5-tang-primer20k-carrier\.claude\worktrees\r5-ovp-switch\spark\usb-jtag-r5-loadsw\full\design\kicad\tab5-fpga-carrier-r5l.kicad_pcb')
mm = pcbnew.ToMM
out = []
for f in b.GetFootprints():
    for p in f.Pads():
        out.append([f.GetReference(), p.GetNumber(), p.GetNetname().lstrip('/'), round(mm(p.GetX()), 3), round(mm(p.GetY()), 3)])
nets = sorted(str(n).lstrip('/') for n in b.GetNetInfo().NetsByName().keys() if str(n))
json.dump({'pads': out, 'nets': nets}, open(r'D:\github\airpocket-soundman\tab5-tang-primer20k-carrier\.claude\worktrees\r5-ovp-switch\spark\usb-jtag-r5-loadsw\easyeda\import-compat\kpads.json', 'w'))
print(len(out), len(nets))
