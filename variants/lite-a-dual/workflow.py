"""Rebuild (--route) or verify the isolated A candidate with compact stage logs.

Run using a normal Python. No original-board files are modified. --route can
take several minutes and intentionally replaces this variant's generated CAD.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys

H=Path(__file__).resolve().parent
KP=Path('C:/Program Files/KiCad/10.0/bin/python.exe')
CLI=KP.parent/'kicad-cli.exe'
SIM=H/'kicad/sim'
def stage(name,args):
    log=SIM/('workflow-'+name+'.log')
    with log.open('w',encoding='utf8') as f:
        p=subprocess.run(list(map(str,args)),cwd=H,stdout=f,stderr=subprocess.STDOUT)
    print(name, 'OK' if p.returncode==0 else 'FAILED',flush=True)
    if p.returncode:raise RuntimeError(str(log))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--route',action='store_true');ap.add_argument('--export',action='store_true');args=ap.parse_args()
    if args.route:
        # Canonical local rebuild preserves reviewed routing and source wrappers.
        # Historical setup/repair scripts mutate qualified footprints and are
        # intentionally excluded from the release workflow.
        stage('qualified-local-stage',[KP,H/'kicad/gen/make_pcb.py'])
    pcb=H/'kicad/tab5-fpga-carrier.kicad_pcb'
    sch=H/'kicad/tab5-fpga-carrier.kicad_sch'
    stage('bom',[sys.executable,H/'kicad/gen/make_bom.py','--offline'])
    stage('schematic',[sys.executable,H/'kicad/gen/make_sch.py'])
    stage('drc',[CLI,'pcb','drc','--severity-all','--format','json','-o',SIM/'drc_r3.json',pcb])
    drc=json.loads((SIM/'drc_r3.json').read_text(encoding='utf8'))
    assert not drc['violations'] and not drc['unconnected_items'],'DRC or connection errors remain'
    stage('erc',[CLI,'sch','erc','--severity-error','--format','json','-o',SIM/'erc-error.json',sch])
    erc=json.loads((SIM/'erc-error.json').read_text(encoding='utf8'))
    assert not [v for s in erc['sheets'] for v in s['violations']],'ERC errors remain'
    for name in ('check_parallel_power','check_power_dc','check_d1_bias','check_esd_footprint','check_ground_reference','check_classification','check_continuity','check_ldo_loops'):
        stage(name,[KP,SIM/(name+'.py')])
    stage('channel-extract',[KP,SIM/'tmds_channel.py','--extract'])
    stage('channel',[sys.executable,SIM/'tmds_channel.py'])
    stage('sparam',[sys.executable,SIM/'tmds_sparam.py'])
    if args.export:stage('export',[KP,H/'kicad/gen/export_poc_package.py'])
    print('A verification passed; physical bringup and supplier assembly review remain.')

if __name__=='__main__':main()
