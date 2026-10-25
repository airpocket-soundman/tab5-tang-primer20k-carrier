"""openEMS helpers for the carrier-board HDMI study (run with the openEMS python 3.13 venv).

  %LOCALAPPDATA%/openems_venv/Scripts/python.exe  (CSXCAD_INSTALL_PATH=%LOCALAPPDATA%/openEMS_dl/ex/openEMS)

Stackup JLC04161H-7628, z measured from the bottom of B.Cu (mm):
  B.Cu 0..0.035 | prepreg 0.2104 | In2 | core 1.065 | In1 (GND plane) | prepreg 0.2104 | F.Cu (top)
"""
import os

import numpy as np

EPS0 = 8.854187817e-12
Z_BCU = (0.0, 0.035)
Z_IN2 = (0.2454, 0.2629)
Z_IN1 = (1.3279, 1.3454)
Z_FCU = (1.5558, 1.5908)
LAYER_Z = {"B.Cu": Z_BCU, "In2.Cu": Z_IN2, "In1.Cu": Z_IN1, "F.Cu": Z_FCU}
ER_PREPREG, ER_CORE, TAND = 4.4, 4.6, 0.02
ZTOP = 1.5908


def setup_env():
    os.environ.setdefault("CSXCAD_INSTALL_PATH", os.path.join(os.environ["LOCALAPPDATA"], "openEMS_dl", "ex", "openEMS"))
    p = os.environ["CSXCAD_INSTALL_PATH"]
    os.add_dll_directory(p)
    os.environ["PATH"] = p + os.pathsep + os.environ["PATH"]


def kappa(er, f0=1e9):
    """Conductivity (S/m) giving the loss tangent TAND at f0."""
    return 2 * np.pi * f0 * EPS0 * er * TAND


def build(prims, ports, domain, f_max=3.5e9, res=0.1, nr_ts=60000, end_crit=1e-4, pml_cells=8, extra_lines_x=(), extra_lines_y=(),
          name="sim", planes=("In1.Cu",), margin_z_air=2.5):
    """prims: list of ('poly', layer, [(x,y),...] (closed outline), ) | ('via', x, y, drill_d, pad_d) | ('box', layer, x0,y0,x1,y1)
    ports: list of dict(nr, x0,y0,x1,y1, dir=None, excite) : vertical lumped port between F.Cu top and In1 plane at the given xy box.
    domain: (x0,y0,x1,y1) mm."""
    setup_env()
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    FDTD = openEMS(NrTS=nr_ts, EndCriteria=end_crit)
    FDTD.SetGaussExcite(f_max / 2, f_max / 2)
    FDTD.SetBoundaryCond(["MUR"] * 6)
    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(1e-3)
    x0, y0, x1, y1 = domain

    pec = CSX.AddMetal("pec")
    pre = CSX.AddMaterial("prepreg", epsilon=ER_PREPREG, kappa=kappa(ER_PREPREG))
    core = CSX.AddMaterial("core", epsilon=ER_CORE, kappa=kappa(ER_CORE))
    # dielectric slabs
    pre.AddBox([x0, y0, Z_BCU[1]], [x1, y1, Z_IN2[0]], priority=1)
    core.AddBox([x0, y0, Z_IN2[1]], [x1, y1, Z_IN1[0]], priority=1)
    pre.AddBox([x0, y0, Z_IN1[1]], [x1, y1, Z_FCU[0]], priority=1)
    for pl in planes:
        z0, z1 = LAYER_Z[pl]
        pec.AddBox([x0, y0, z0], [x1, y1, z1], priority=10)
    for pr in prims:
        kind = pr[0]
        if kind == "poly":
            _, layer, pts = pr
            z0, z1 = LAYER_Z[layer]
            pec.AddLinPoly(np.array(pts).T, "z", z0, z1 - z0, priority=20)
        elif kind == "box":
            _, layer, a, b, c, d = pr
            z0, z1 = LAYER_Z[layer]
            pec.AddBox([a, b, z0], [c, d, z1], priority=20)
        elif kind == "via":
            _, x, y, drill, pad = pr
            pec.AddCylinder([x, y, Z_BCU[0]], [x, y, Z_FCU[1]], drill / 2 + 0.025, priority=20)       # plated barrel
    # ports (vertical, from the In1 plane up to the F.Cu trace)
    port_objs = []
    for p in ports:
        z_lo, z_hi = Z_IN1[1], Z_FCU[0]
        port_objs.append(FDTD.AddLumpedPort(p["nr"], 50, [p["x0"], p["y0"], z_lo], [p["x1"], p["y1"], z_hi + 0.0], "z", excite=p["excite"],
                                            priority=30))
        pec.AddBox([p["x0"], p["y0"], Z_FCU[0]], [p["x1"], p["y1"], Z_FCU[1]], priority=21)
    # mesh
    lines_x = {x0, x1} | set(extra_lines_x)
    lines_y = {y0, y1} | set(extra_lines_y)
    for p in ports:
        lines_x |= {p["x0"], p["x1"]}
        lines_y |= {p["y0"], p["y1"]}
    mesh.AddLine("x", sorted(lines_x))
    mesh.AddLine("y", sorted(lines_y))
    zl = sorted({Z_BCU[0], Z_BCU[1], Z_IN2[0], Z_IN2[1], Z_IN1[0], Z_IN1[1], Z_FCU[0], Z_FCU[1], ZTOP + margin_z_air, -2.0})
    zz = []
    for a_, b_ in zip(zl[:-1], zl[1:]):
        h = b_ - a_
        n = max(int(np.ceil(h / 0.07)), 1) if h < 1.2 else max(int(np.ceil(h / 0.3)), 1)
        zz += list(np.linspace(a_, b_, n, endpoint=False))
    zz.append(zl[-1])
    mesh.AddLine("z", zz)
    air = 2.5
    mesh.AddLine("x", [x0 - air, x1 + air])
    mesh.AddLine("y", [y0 - air, y1 + air])
    mesh.SmoothMeshLines("x", res, 1.4)
    mesh.SmoothMeshLines("y", res, 1.4)
    mesh.SmoothMeshLines("z", 0.3, 1.4)
    return FDTD, CSX, port_objs


def run(FDTD, CSX, workdir, f_max=3.5e9, nf=300, cleanup=True, quiet=True):
    os.makedirs(workdir, exist_ok=True)
    CSX.Write2XML(os.path.join(workdir, "sim.xml"))
    FDTD.Run(workdir, cleanup=cleanup, verbose=1 if quiet else 3)
