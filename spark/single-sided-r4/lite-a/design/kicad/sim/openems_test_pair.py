"""Validation: straight coupled microstrip pair (w=0.2, gap=0.13) -> Zdiff from the 3D solver vs the 2D solver (~107 ohm)."""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import openems_lib as L
L.setup_env()
from openEMS.physical_constants import C0

W, GAP, LEN = 0.2, 0.13, 14.0
cx = 0.0
off = (W + GAP) / 2
y0, y1 = 0.0, LEN
prims = []
for sgn in (-1, 1):
    x = cx + sgn * off
    prims.append(("box", "F.Cu", x - W / 2, y0, x + W / 2, y1))
ports = []
for k, sgn in enumerate((-1, 1)):
    x = cx + sgn * off
    ports.append(dict(nr=k + 1, x0=x - W / 2, x1=x + W / 2, y0=y0, y1=y0 + 0.1, excite=1 if True else 0))
    ports.append(dict(nr=k + 3, x0=x - W / 2, x1=x + W / 2, y0=y1 - 0.1, y1=y1, excite=0))
for p in ports:
    p["excite"] = 1 if p["nr"] == 1 else 0
dom = (-2.5, y0, 2.5, y1)
lines_x = [cx + s * off + d for s in (-1, 1) for d in (-W / 2, W / 2)]
FDTD, CSX, pobjs = L.build(prims, ports, dom, f_max=3.5e9, res=0.1, extra_lines_x=lines_x, planes=("In1.Cu",))
wd = os.path.join(os.environ["TEMP"], "oems_test_pair")
t = time.time()
L.run(FDTD, CSX, wd)
print("run %.0fs" % (time.time() - t))
f = np.linspace(0.1e9, 3.5e9, 120)
res = []
for k in range(1, 5):
    pobjs[k - 1].CalcPort(wd, f, ref_impedance=50)
# full 4x4 S needs 4 excitations; with single excitation we get column 1 only. Use symmetric structure: odd-mode estimate.
s11 = pobjs[0].uf_ref / pobjs[0].uf_inc
s21 = pobjs[1].uf_ref / pobjs[0].uf_inc      # coupling to the partner at the same end
s31 = pobjs[2].uf_ref / pobjs[0].uf_inc
s41 = pobjs[3].uf_ref / pobjs[0].uf_inc
np.save(os.path.join(wd, "col1.npy"), np.array([s11, s21, s31, s41]))
print("S11 %.1f dB  S21 %.1f dB  S31 %.1f dB  S41 %.1f dB (mean over 0.5-2 GHz)" % tuple(
    20 * np.log10(np.abs(a[(f > 0.5e9) & (f < 2e9)]).mean()) for a in (s11, s21, s31, s41)))
