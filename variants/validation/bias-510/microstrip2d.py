"""2D quasi-static field solver for (coupled) microstrip on the JLCPCB 4-layer stackup.

Finite-difference Laplace solution (numpy/scipy only). Gives single-ended Z0 / eps_eff and, for a pair,
even/odd-mode impedances, Zdiff, Zcm and eps_eff per mode.

Stackup (JLC04161H-7628, 1.6 mm): L1 35 um Cu (finished), prepreg 7628 0.2104 mm (er 4.4), L2 = GND plane.
Solder mask is ignored (it lowers Zdiff by roughly 1-3 ohm).

python -X utf8 kicad/sim/microstrip2d.py            # self-check + sweep for 100 ohm diff
"""
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

C0 = 299792458.0
EPS0 = 8.8541878128e-12


def solve_energy(er, strips, h, t, dx, win_w, win_h, volt):
    """Return stored energy per metre (J/m) for conductor voltages `volt`.
    strips: list of (x_left, x_right) in mm (centred around 0). Ground plane at y=0 (bottom boundary).
    Top and side boundaries: grounded box far away (win_w / win_h in mm)."""
    nx = int(round(win_w / dx)) + 1
    ny = int(round(win_h / dx)) + 1
    xs = (np.arange(nx) - (nx - 1) / 2) * dx
    ys = np.arange(ny) * dx
    # permittivity at cell centres (nx-1, ny-1)
    xc = (xs[:-1] + xs[1:]) / 2
    yc = (ys[:-1] + ys[1:]) / 2
    jh = int(round(h / dx))
    nt = max(int(round(t / dx)), 1)
    eps = np.where(np.arange(ny - 1)[None, :] < jh, er, 1.0) * np.ones((nx - 1, ny - 1))
    n = nx * ny
    idx = np.arange(n).reshape(nx, ny)
    # fixed potentials
    fixed = np.zeros((nx, ny), bool)
    pot = np.zeros((nx, ny))
    fixed[0, :] = fixed[-1, :] = fixed[:, 0] = fixed[:, -1] = True
    for (x0, x1), v in zip(strips, volt):
        mx = (xs >= x0 - 1e-9) & (xs <= x1 + 1e-9)
        my = (np.arange(ny) >= jh) & (np.arange(ny) <= jh + nt)
        m = mx[:, None] & my[None, :]
        fixed |= m
        pot[m] = v
    # assemble: sum over 4 neighbours of eps_avg * (phi_i - phi_j) = 0
    rows, cols, vals = [], [], []
    diag = np.zeros((nx, ny))
    def add(i0, j0, i1, j1, w):
        rows.append(idx[i0, j0].ravel()); cols.append(idx[i1, j1].ravel()); vals.append(-w.ravel())
        diag[i0, j0] += w
    # x-direction links between (i,j) and (i+1,j): edge shared by cells (i,j-1),(i,j) -> average eps
    ex = np.zeros((nx - 1, ny))
    ex[:, 1:-1] = (eps[:, :-1] + eps[:, 1:]) / 2
    ex[:, 0] = eps[:, 0]; ex[:, -1] = eps[:, -1]
    add(slice(0, nx - 1), slice(0, ny), slice(1, nx), slice(0, ny), ex)
    add(slice(1, nx), slice(0, ny), slice(0, nx - 1), slice(0, ny), ex)
    ey = np.zeros((nx, ny - 1))
    ey[1:-1, :] = (eps[:-1, :] + eps[1:, :]) / 2
    ey[0, :] = eps[0, :]; ey[-1, :] = eps[-1, :]
    add(slice(0, nx), slice(0, ny - 1), slice(0, nx), slice(1, ny), ey)
    add(slice(0, nx), slice(1, ny), slice(0, nx), slice(0, ny - 1), ey)
    A = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    A = A + sp.diags(diag.ravel())
    f = fixed.ravel()
    p = pot.ravel().copy()
    free = ~f
    b = -A[free][:, f] @ p[f]
    p[free] = spla.spsolve(A[free][:, free].tocsc(), b)
    phi = p.reshape(nx, ny)
    # energy = 1/2 sum eps |grad phi|^2 (per metre, epsilon in eps0 units)
    gx = (np.diff(phi, axis=0)[:, :-1] + np.diff(phi, axis=0)[:, 1:]) / 2 / (dx * 1e-3)
    gy = (np.diff(phi, axis=1)[:-1, :] + np.diff(phi, axis=1)[1:, :]) / 2 / (dx * 1e-3)
    # the strips/ground interior is fixed (zero field inside metal); fine.
    w = 0.5 * EPS0 * np.sum(eps * (gx ** 2 + gy ** 2)) * (dx * 1e-3) ** 2
    return w


def cap_matrix(er, strips, h, t, dx=None, win_w=None, win_h=None):
    dx = dx or h / 20.0
    nS = len(strips)
    win_w = win_w or (max(abs(s[0]) for s in strips) + 10 * h + 2.0) * 2
    win_h = win_h or (h + t + 10 * h)
    W = {}
    for i in range(nS):
        v = [0.0] * nS; v[i] = 1.0
        W[(i,)] = solve_energy(er, strips, h, t, dx, win_w, win_h, v)
    C = np.zeros((nS, nS))
    for i in range(nS):
        C[i, i] = 2 * W[(i,)]
    for i in range(nS):
        for j in range(i + 1, nS):
            v = [0.0] * nS; v[i] = 1.0; v[j] = 1.0
            wij = solve_energy(er, strips, h, t, dx, win_w, win_h, v)
            C[i, j] = C[j, i] = wij - W[(i,)] - W[(j,)]
    return C


def single(w, h=0.2104, t=0.035, er=4.4, dx=None):
    s = [(-w / 2, w / 2)]
    C = cap_matrix(er, s, h, t, dx)[0, 0]
    C0 = cap_matrix(1.0, s, h, t, dx)[0, 0]
    z0 = 1 / (299792458.0 * np.sqrt(C * C0))
    return z0, C / C0


def pair(w, gap, h=0.2104, t=0.035, er=4.4, dx=None):
    s = [(-gap / 2 - w, -gap / 2), (gap / 2, gap / 2 + w)]
    C = cap_matrix(er, s, h, t, dx)
    Ca = cap_matrix(1.0, s, h, t, dx)
    out = {}
    for name, sign in (("even", 1), ("odd", -1)):
        ce = C[0, 0] + sign * C[0, 1]
        ca = Ca[0, 0] + sign * Ca[0, 1]
        out[name] = (1 / (299792458.0 * np.sqrt(ce * ca)), ce / ca)
    out["zdiff"] = 2 * out["odd"][0]
    out["zcm"] = out["even"][0] / 2
    return out


if __name__ == "__main__":
    # self-check against Hammerstad: w/h=1 on er=4.4 -> Z0 ~ 50 ohm-ish (w=0.2104)
    z, ee = single(0.3)
    print("single w=0.30 mm: Z0=%.1f ohm eps_eff=%.2f" % (z, ee))
    z, ee = single(0.2104)
    print("single w=0.2104 mm (w/h=1): Z0=%.1f ohm eps_eff=%.2f (Hammerstad ~ 50-52 ohm, 3.3)" % (z, ee))
    print("pair sweep (h=0.2104 mm, t=35 um, er=4.4):  w / gap -> Zdiff, Zodd, Zeven, eps_eff(odd)")
    for w, g in ((0.127, 0.127), (0.127, 0.2), (0.15, 0.15), (0.15, 0.2), (0.2, 0.2), (0.2, 0.15), (0.1, 0.1)):
        r = pair(w, g)
        print("  %.3f / %.3f -> Zdiff %.1f  Zodd %.1f  Zeven %.1f  eps_odd %.2f" % (
            w, g, r["zdiff"], r["odd"][0], r["even"][0], r["odd"][1]))
