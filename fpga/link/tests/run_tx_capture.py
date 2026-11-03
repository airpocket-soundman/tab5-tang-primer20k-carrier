import argparse,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');a=p.parse_args()
with tempfile.TemporaryDirectory() as t:
 exe=Path(t)/'test';subprocess.run([a.iverilog,'-g2012','-s','tb_tx_capture','-o',str(exe),str(ROOT/'link/rtl/link_bringup.v'),str(ROOT/'link/tests/tb_tx_capture.v')],check=True)
 subprocess.run([a.vvp,str(exe)],check=True,timeout=30)
