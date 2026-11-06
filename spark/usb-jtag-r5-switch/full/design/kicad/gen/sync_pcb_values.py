"""Copy the BOM value of every part into the PCB footprint Value field (KiCad python).
Only text fields change; no copper, no placement. Prints every change."""
import csv, pcbnew
from pathlib import Path
K = Path(__file__).resolve().parents[1]
P = K / 'tab5-fpga-carrier-r5s.kicad_pcb'
vals = {r['Reference']: r['Value'] for r in csv.DictReader((K / 'bom-r5s.csv').open(encoding='utf8'))}
b = pcbnew.LoadBoard(str(P))
n = 0
for f in b.GetFootprints():
    ref = f.GetReference()
    if ref in vals and f.GetValue() != vals[ref]:
        print('value', ref, f.GetValue(), '->', vals[ref])
        f.SetValue(vals[ref]); n += 1
missing = [f.GetReference() for f in b.GetFootprints() if f.GetReference() not in vals]
print('changed', n, 'footprints without BOM row:', missing)
if n:
    b.Save(str(P))
