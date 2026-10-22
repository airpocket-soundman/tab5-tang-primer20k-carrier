"""Grid A* router (two signal layers F.Cu / B.Cu, through vias). GND is handled by planes + pours.

All dimensions in mm; grid pitch GRID. Track width default 0.2, clearance 0.2.
"""
import heapq
import math
import time

import numpy as np
import pcbnew

import design

GRID = 0.1
CLR = 0.15
TW = 0.15
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 12.0
NL = 3
LAYER_NAMES = ["F.Cu", "In2.Cu", "B.Cu"]
SKIP = {"GND"}


def dilate(mask, r):
    """Square dilation of a boolean mask by r cells (integral image)."""
    if r <= 0:
        return mask.copy()
    H, W = mask.shape
    pad = np.pad(mask.astype(np.int32), ((r + 1, r), (r + 1, r)))
    S = pad.cumsum(0).cumsum(1)
    win = 2 * r + 1
    tot = S[win:win + H, win:win + W] - S[0:H, win:win + W] - S[win:win + H, 0:W] + S[0:H, 0:W]
    return tot > 0


class Router:
    def __init__(self, board, x0, y0, x1, y1):
        self.board = board
        self.x0, self.y0 = x0, y0
        self.W = int(round((x1 - x0) / GRID)) + 1
        self.H = int(round((y1 - y0) / GRID)) + 1
        self.occ = [np.zeros((self.H, self.W), dtype=np.int16) for _ in range(NL)]
        self.netid = {}
        self.names = {}
        self.pads = {}           # net name -> list of (x, y, layers, ref)
        self.max_exp = 150000
        self.tracks = []         # (net, layer, [(x,y),...], width)
        self.vias = []           # (net, x, y)

    # ------------------------------------------------------------ helpers
    def nid(self, name):
        if name not in self.netid:
            self.netid[name] = len(self.netid) + 1
            self.names[self.netid[name]] = name
        return self.netid[name]

    def cell(self, x, y):
        return int(round((x - self.x0) / GRID)), int(round((y - self.y0) / GRID))

    def xy(self, cx, cy):
        return self.x0 + cx * GRID, self.y0 + cy * GRID

    def stamp_rect(self, layer, rx0, ry0, rx1, ry1, n, infl):
        cx0, cy0 = self.cell(rx0 - infl, ry0 - infl)
        cx1, cy1 = self.cell(rx1 + infl, ry1 + infl)
        cx0, cy0 = max(cx0, 0), max(cy0, 0)
        cx1, cy1 = min(cx1, self.W - 1), min(cy1, self.H - 1)
        if cx0 > cx1 or cy0 > cy1:
            return
        sub = self.occ[layer][cy0:cy1 + 1, cx0:cx1 + 1]
        free = sub == 0
        bad = (sub != 0) & (sub != n)
        sub[free] = n
        sub[bad] = -1

    def stamp_disc(self, layer, x, y, n, rad):
        cx, cy = self.cell(x, y)
        r = int(math.ceil(rad / GRID))
        ys, xs = np.ogrid[-r:r + 1, -r:r + 1]
        mask = (xs * xs + ys * ys) * GRID * GRID <= rad * rad
        y0, y1 = max(cy - r, 0), min(cy + r + 1, self.H)
        x0, x1 = max(cx - r, 0), min(cx + r + 1, self.W)
        m = mask[y0 - (cy - r):y1 - (cy - r), x0 - (cx - r):x1 - (cx - r)]
        sub = self.occ[layer][y0:y1, x0:x1]
        free = (sub == 0) & m
        bad = (sub != 0) & (sub != n) & m
        sub[free] = n
        sub[bad] = -1

    def stamp_path(self, layer, pts, n, w):
        rad = CLR + w / 2 + TW / 2
        for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
            steps = max(int(max(abs(xb - xa), abs(yb - ya)) / GRID), 1)
            for i in range(steps + 1):
                t = i / steps
                self.stamp_disc(layer, xa + (xb - xa) * t, ya + (yb - ya) * t, n, rad)

    # ------------------------------------------------------------ load board
    def load(self, outline):
        x0, y0, x1, y1 = outline
        # board edge keep-out (copper to edge 0.3 + half track)
        m = int(round(0.5 / GRID))
        for l in range(NL):
            self.occ[l][:m, :] = -1
            self.occ[l][-m:, :] = -1
            self.occ[l][:, :m] = -1
            self.occ[l][:, -m:] = -1
        items = []
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                name = pad.GetNetname()
                bb = pad.GetBoundingBox()
                rect = (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()),
                        pcbnew.ToMM(bb.GetBottom()))
                layers = []
                if pad.IsOnLayer(pcbnew.F_Cu):
                    layers.append(0)
                if pad.IsOnLayer(pcbnew.B_Cu):
                    layers.append(NL - 1)
                if len(layers) == 2:           # plated through-hole: copper on every layer
                    layers = list(range(NL))
                hole_only = pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
                if hole_only:
                    layers = list(range(NL))
                if hole_only:
                    n = -1
                elif name:
                    n = self.nid(name)
                else:
                    self._anon = getattr(self, '_anon', 20000) + 1
                    n = self._anon
                items.append((n, layers, rect))
                if n != -1 and name and name != "GND":
                    p = pad.GetPosition()
                    self.pads.setdefault(name, []).append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), tuple(layers),
                                                           fp.GetReference() + "." + pad.GetNumber()))
        # pass 1: inflated clearance zones (conflicts -> -1)
        for n, layers, (rx0, ry0, rx1, ry1) in items:
            for l in layers:
                if n == -1:
                    cx0, cy0 = self.cell(rx0 - 0.5, ry0 - 0.5)
                    cx1, cy1 = self.cell(rx1 + 0.5, ry1 + 0.5)
                    self.occ[l][max(cy0, 0):cy1 + 1, max(cx0, 0):cx1 + 1] = -1
                else:
                    self.stamp_rect(l, rx0, ry0, rx1, ry1, n, CLR + TW / 2)
        # pass 2: pad copper itself always belongs to its own net
        for n, layers, (rx0, ry0, rx1, ry1) in items:
            if n == -1:
                continue
            for l in layers:
                cx0 = int(math.ceil((rx0 - self.x0) / GRID - 1e-9))
                cy0 = int(math.ceil((ry0 - self.y0) / GRID - 1e-9))
                cx1 = int(math.floor((rx1 - self.x0) / GRID + 1e-9))
                cy1 = int(math.floor((ry1 - self.y0) / GRID + 1e-9))
                if cx1 < cx0:
                    cx0 = cx1 = int(round(((rx0 + rx1) / 2 - self.x0) / GRID))
                if cy1 < cy0:
                    cy0 = cy1 = int(round(((ry0 + ry1) / 2 - self.y0) / GRID))
                self.occ[l][max(cy0, 0):cy1 + 1, max(cx0, 0):cx1 + 1] = n

    # ------------------------------------------------------------ A*
    def prepare(self, n, w):
        foreign = [(self.occ[l] != 0) & (self.occ[l] != n) for l in range(NL)]
        r = int(round((VIA_D / 2 + CLR + TW / 2) / GRID))
        self._viafree = ~dilate(np.any(foreign, axis=0), r)
        extra = max(0, int(round((w - TW) / 2 / GRID)))
        self._widefree = [~dilate(f, extra) for f in foreign] if extra else None

    def via_ok(self, cx, cy, n):
        return bool(self._viafree[cy, cx])

    def astar(self, n, starts, targets, w, bbox, via_cost):
        """starts: list of (layer,cx,cy); targets: list of boolean masks per layer (full size)."""
        bx0, by0, bx1, by1 = bbox
        extra = max(0, int(round((w - TW) / 2 / GRID)))
        occ = self.occ
        tg = targets
        # target bbox heuristic
        ty, tx = np.nonzero(np.any(tg, axis=0))
        if len(tx) == 0:
            return None
        tx0, tx1, ty0, ty1 = tx.min(), tx.max(), ty.min(), ty.max()

        def h(cx, cy):
            dx = max(tx0 - cx, 0, cx - tx1)
            dy = max(ty0 - cy, 0, cy - ty1)
            return (max(dx, dy) + 0.414 * min(dx, dy))

        g = {}
        came = {}
        heap = []
        cnt = 0
        for s in starts:
            g[s] = 0.0
            heapq.heappush(heap, (h(s[1], s[2]), cnt, s))
            cnt += 1
        nbrs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414),
                (-1, 1, 1.414), (-1, -1, 1.414)]
        expansions = 0
        while heap:
            f, _, s = heapq.heappop(heap)
            gs = g[s]
            l, cx, cy = s
            if f - h(cx, cy) > gs + 1e-6:
                continue
            if tg[l][cy, cx]:
                path = [s]
                while path[-1] in came:
                    path.append(came[path[-1]])
                return path[::-1]
            expansions += 1
            if expansions > self.max_exp:
                return None
            for dx, dy, c in nbrs:
                nx, ny = cx + dx, cy + dy
                if nx < bx0 or ny < by0 or nx > bx1 or ny > by1:
                    continue
                v = occ[l][ny, nx]
                if v != 0 and v != n:
                    continue
                if self._widefree is not None and not self._widefree[l][ny, nx]:
                    continue
                if dx and dy:
                    # avoid cutting corners
                    a = occ[l][cy, nx]
                    b = occ[l][ny, cx]
                    if (a != 0 and a != n) or (b != 0 and b != n):
                        continue
                ns = (l, nx, ny)
                ng = gs + c
                if ng < g.get(ns, 1e18):
                    g[ns] = ng
                    came[ns] = s
                    heapq.heappush(heap, (ng + h(nx, ny), cnt, ns))
                    cnt += 1
            # via (through): move to any other layer at this cell
            if self.via_ok(cx, cy, n):
                for o in range(NL):
                    if o == l:
                        continue
                    ok = True
                    for k in range(NL):
                        v2 = occ[k][cy, cx]
                        if v2 != 0 and v2 != n:
                            ok = False
                            break
                    if not ok:
                        continue
                    ns = (o, cx, cy)
                    ng = gs + via_cost
                    if ng < g.get(ns, 1e18):
                        g[ns] = ng
                        came[ns] = s
                        heapq.heappush(heap, (ng + h(cx, cy), cnt, ns))
                        cnt += 1
        return None

    def _wide_ok(self, l, cx, cy, n, r):
        if cx - r < 0 or cy - r < 0 or cx + r >= self.W or cy + r >= self.H:
            return False
        sub = self.occ[l][cy - r:cy + r + 1, cx - r:cx + r + 1]
        return not np.any((sub != 0) & (sub != n))

    # ------------------------------------------------------------ net routing
    def route_net(self, name, w=TW, via_cost=VIA_COST):
        lst = self.pads.get(name, [])
        if len(lst) < 2:
            return True
        n = self.nid(name)
        self.prepare(n, w)
        pts = [(x, y, layers) for (x, y, layers, _) in lst]
        # MST-like order: start with pad 0
        connected = [0]
        remaining = list(range(1, len(pts)))
        tree = [np.zeros((self.H, self.W), dtype=bool) for _ in range(NL)]

        def add_pad_to_tree(i):
            x, y, layers = pts[i]
            cx, cy = self.cell(x, y)
            for l in layers:
                tree[l][cy, cx] = True

        add_pad_to_tree(0)
        ok = True
        while remaining:
            # nearest remaining to connected set
            best = None
            for j in remaining:
                for i in connected:
                    d = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
                    if best is None or d < best[0]:
                        best = (d, j)
            _, j = best
            x, y, layers = pts[j]
            cx, cy = self.cell(x, y)
            starts = [(l, cx, cy) for l in layers]
            path = None
            for margin in (5, 14, 40):
                ty, tx = np.nonzero(np.any(tree, axis=0))
                bx0 = max(min(tx.min(), cx) - int(margin / GRID), 0)
                bx1 = min(max(tx.max(), cx) + int(margin / GRID), self.W - 1)
                by0 = max(min(ty.min(), cy) - int(margin / GRID), 0)
                by1 = min(max(ty.max(), cy) + int(margin / GRID), self.H - 1)
                path = self.astar(n, starts, tree, w, (bx0, by0, bx1, by1), via_cost)
                if path:
                    break
            if not path:
                ok = False
                remaining.remove(j)
                continue
            self.commit(name, n, path, w, (x, y))
            self.prepare(n, w)
            for (l, px, py) in path:
                tree[l][py, px] = True
            add_pad_to_tree(j)
            connected.append(j)
            remaining.remove(j)
        return ok

    def commit(self, name, n, path, w, padxy):
        # split into per-layer polylines
        seg = []
        cur_l = path[0][0]
        cur = [self.xy(path[0][1], path[0][2])]
        prev = path[0]
        for s in path[1:]:
            if s[0] != prev[0]:
                self.vias.append((name, *self.xy(prev[1], prev[2])))
                for k in range(NL):
                    self.stamp_disc(k, *self.xy(prev[1], prev[2]), n, VIA_D / 2 + CLR + TW / 2)
                seg.append((cur_l, cur))
                cur_l = s[0]
                cur = [self.xy(s[1], s[2])]
            else:
                cur.append(self.xy(s[1], s[2]))
            prev = s
        seg.append((cur_l, cur))
        for l, pts in seg:
            pts = simplify(pts)
            if len(pts) >= 2:
                for sub_pts, sub_w in taper(pts, w):
                    self.tracks.append((name, l, sub_pts, sub_w))
                self.stamp_path(l, pts, n, w)

    def gnd_pads(self):
        out = []
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() != "GND":
                    continue
                if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                    continue
                layer = 0 if pad.IsOnLayer(pcbnew.F_Cu) else NL - 1
                p = pad.GetPosition()
                out.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), layer, fp.GetReference() + "." + pad.GetNumber()))
        return out

    def stitch_gnd(self):
        n = self.nid("GND")
        self.prepare(n, TW)
        done = fail = 0
        for (x, y, layer, ref) in self.gnd_pads():
            cx, cy = self.cell(x, y)
            heap = [(0.0, 0, (layer, cx, cy))]
            g = {(layer, cx, cy): 0.0}
            came = {}
            cnt = 1
            found = None
            while heap:
                c0, _, s_ = heapq.heappop(heap)
                l, px, py = s_
                if c0 > 45:
                    break
                if self._viafree[py, px] and all(self.occ[k][py, px] in (0, n) for k in range(NL)):
                    found = s_
                    break
                for dx, dy, c in ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0)):
                    nx, ny = px + dx, py + dy
                    if nx < 0 or ny < 0 or nx >= self.W or ny >= self.H:
                        continue
                    v = self.occ[l][ny, nx]
                    if v != 0 and v != n:
                        continue
                    ns = (l, nx, ny)
                    if c0 + c < g.get(ns, 1e18):
                        g[ns] = c0 + c
                        came[ns] = s_
                        heapq.heappush(heap, (c0 + c, cnt, ns))
                        cnt += 1
            if not found:
                fail += 1
                continue
            path = [found]
            while path[-1] in came:
                path.append(came[path[-1]])
            path = path[::-1]
            pts = simplify([self.xy(p[1], p[2]) for p in path])
            if len(pts) >= 2:
                self.tracks.append(("GND", layer, pts, TW))
                self.stamp_path(layer, pts, n, TW)
            vx, vy = self.xy(found[1], found[2])
            self.vias.append(("GND", vx, vy))
            for k in range(NL):
                self.stamp_disc(k, vx, vy, n, VIA_D / 2 + CLR + TW / 2)
            self.prepare(n, TW)
            done += 1
        print("GND stitch: %d done, %d failed" % (done, fail), flush=True)


def taper(pts, w, neck=0.25, length=1.2):
    """Narrow the first/last `length` mm of a wide track so it can enter fine-pitch pads."""
    if w <= neck + 1e-6 or len(pts) < 2:
        return [(pts, w)]
    segs = []
    pts = list(pts)

    def cut(a, b, d):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        t = min(d / L, 1.0) if L > 0 else 1.0
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), L

    # head
    c, L = cut(pts[0], pts[1], length)
    head = [pts[0], c]
    if L > length + 0.05:
        pts[0] = c
    else:
        pts = pts[1:]
        if len(pts) < 2:
            return [(head, neck)]
    # tail
    c2, L2 = cut(pts[-1], pts[-2], length)
    tail = [c2, pts[-1]]
    if L2 > length + 0.05:
        pts[-1] = c2
    else:
        pts = pts[:-1]
        if len(pts) < 1:
            return [(head, neck), (tail, neck)]
    out = [(head, neck)]
    if len(pts) >= 2:
        out.append((pts, w))
    elif len(pts) == 1 and (abs(pts[0][0] - head[-1][0]) > 1e-6 or abs(pts[0][1] - head[-1][1]) > 1e-6):
        out.append(([head[-1], pts[0]], w))
    out.append((tail, neck))
    return out


def simplify(pts):
    """Merge collinear points."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = out[-1], pts[i], pts[i + 1]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
            out.append(b)
    out.append(pts[-1])
    return out


ORDER_W = {"VIN": 0.8, "DC_RAW": 0.8, "DC_IN": 0.8, "VBUS_PD": 0.4, "+5V": 0.6, "BUCK_PH": 0.8, "HDMI_5V": 0.3,
           "+3V3": 0.3}


PRIORITY = ["HDMI_CKP", "HDMI_5V", "F_D0", "F_D1", "P1_0", "P1_2", "M_AUX0", "F_HSDA", "PD_VDD", "PD_VBUS_S"]


def run(b, comps):
    t0 = time.time()
    x0, y0, x1, y1 = design.BOARD
    r = Router(b.board, x0, y0, x1, y1)
    r.load(design.BOARD)
    nets = [n for n in r.pads if n not in SKIP]
    # order: wide power first, then HDMI, then by bbox size ascending
    def key(n):
        if n in ORDER_W:
            return (0, -ORDER_W[n])
        if n in PRIORITY:
            return (1, PRIORITY.index(n))
        if n.startswith("HDMI_D") or n.startswith("HDMI_CK"):
            return (2, 0)
        xs = [p[0] for p in r.pads[n]]
        ys = [p[1] for p in r.pads[n]]
        return (3, (max(xs) - min(xs)) + (max(ys) - min(ys)))
    nets.sort(key=key)
    failed = []
    for idx, n in enumerate(nets):
        w = ORDER_W.get(n, TW)
        print("[%d/%d] %s (%d pads) t=%.0fs" % (idx + 1, len(nets), n, len(r.pads[n]), time.time() - t0), flush=True)
        vc = 40.0 if n.startswith("HDMI_D") or n.startswith("HDMI_CK") else VIA_COST
        if not r.route_net(n, w, vc):
            failed.append(n)
    if failed:
        r.max_exp = 500000
        again = []
        for n in failed:
            print("retry", n, flush=True)
            w = ORDER_W.get(n, TW)
            if not r.route_net(n, w, 8.0):
                again.append(n)
        failed = again
    print("routed %d nets, failed %d: %s (%.1fs)" % (len(nets) - len(failed), len(failed), failed, time.time() - t0))
    r.stitch_gnd()
    seen = set()
    uv = []
    for v in r.vias:
        k = (v[0], round(v[1], 3), round(v[2], 3))
        if k not in seen:
            seen.add(k)
            uv.append(v)
    r.vias = uv
    for (name, l, pts, w) in r.tracks:
        b.track(name, LAYER_NAMES[l], pts, w)
    for (name, x, y) in r.vias:
        b.via(name, x, y, VIA_D, VIA_DRILL)
    return r
