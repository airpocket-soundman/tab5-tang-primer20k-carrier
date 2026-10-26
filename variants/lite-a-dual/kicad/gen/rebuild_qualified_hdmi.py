"""Deterministic reviewed local HDMI stage. Outputs temp only; requires DRC and guarded adoption.
Run AFTER any full make_pcb stage to prevent restoring the old sideband topology.
The preserved pre-HDMI snapshot is authoritative for this qualified local stage;
new unrelated board changes require a fresh audited snapshot, never silent merge.
"""
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4]
variant=Path(__file__).resolve().parents[2].name
subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe','-X','utf8',str(root/'variants/simulation/hdmi/prepare_hdmi_cad.py'),variant],check=True)
print('Temporary result only. Run DRC and adopt_hdmi_cad.py '+variant+' to apply with raw-SHA guard.')
