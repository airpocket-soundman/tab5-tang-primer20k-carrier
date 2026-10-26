import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import openems_lib as L
L.setup_env()
W, LEN = float(sys.argv[1]), 10.0
prims = [("box", "F.Cu", -W / 2, 0, W / 2, LEN)]
ports = [dict(nr=1, x0=-W / 2, x1=W / 2, y0=0, y1=0.1, excite=1), dict(nr=2, x0=-W / 2, x1=W / 2, y0=LEN - 0.1, y1=LEN, excite=0)]
FDTD, CSX, po = L.build(prims, ports, (-2.5, 0, 2.5, LEN), f_max=3.5e9, res=float(sys.argv[2]), nr_ts=30000, extra_lines_x=[-W / 2, W / 2, -W / 2 - .05, W / 2 + .05])
wd = os.path.join(os.environ["TEMP"], "oems_test_single")
t = time.time(); L.run(FDTD, CSX, wd); print("run %.0fs" % (time.time() - t))
f = np.linspace(0.1e9, 3.5e9, 120)
for p in po: p.CalcPort(wd, f, ref_impedance=50)
s11 = po[0].uf_ref / po[0].uf_inc; s21 = po[1].uf_ref / po[0].uf_inc
Z = 50 * np.sqrt(((1 + s11) ** 2 - s21 ** 2) / ((1 - s11) ** 2 - s21 ** 2))
m = (f > 0.5e9) & (f < 2e9)
print("w=%.3f: Z0 = %.1f ohm  S11 %.1f dB" % (W, np.real(Z[m]).mean(), 20 * np.log10(np.abs(s11[m])).mean()))
