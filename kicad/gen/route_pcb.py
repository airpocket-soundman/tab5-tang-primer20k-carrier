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
CLR = 0.127
TW = 0.127
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 12.0
ZONE_COST = 4.0
BUS_PREFIXES = ('F_D', 'M_D', 'F_RDY', 'M_RDY', 'F_AUX', 'M_AUX', 'F_EXT', 'M_EXT', 'F_CLK', 'M_CLK')
BUS_ZONE = (43.0, 26.0, 53.0, 57.0)      # fan-out channel reserved for the bus nets (x0, y0, x1, y1)
SOFT_PEN = 18.0
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
        self.perm = []
        self.base = None
        self.trk = None
        self.sm = []
        self._culprits = set()
        self.soft = False
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

    def stamp_disc(self, layer, x, y, n, rad, dyn=False):
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
        if dyn and self.trk is not None:
            rem = m.copy()
            for k in range(3):
                t = self.trk[layer][k][y0:y1, x0:x1]
                rem &= ~((t == n) & rem)
                put = (t == 0) & rem
                t[put] = n
                rem &= ~put

    def stamp_path(self, layer, pts, n, w, dyn=False):
        rad = CLR + w / 2 + TW / 2
        for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
            steps = max(int(max(abs(xb - xa), abs(yb - ya)) / GRID), 1)
            for i in range(steps + 1):
                t = i / steps
                self.stamp_disc(layer, xa + (xb - xa) * t, ya + (yb - ya) * t, n, rad, dyn)

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
        self.base = [o.copy() for o in self.occ]
        self.trk = [[np.zeros((self.H, self.W), dtype=np.int16) for _ in range(3)] for _ in range(NL)]

    def rebuild(self):
        self.occ = [b.copy() for b in self.base]
        self.trk = [[np.zeros((self.H, self.W), dtype=np.int16) for _ in range(3)] for _ in range(NL)]
        for it in self.sm:
            n = self.nid(it[1])
            if it[0] == "v":
                for k in range(NL):
                    self.stamp_disc(k, it[2], it[3], n, VIA_D / 2 + CLR + TW / 2, True)
            else:
                self.stamp_path(it[2], it[3], n, it[4], True)

    def rip_net(self, name):
        self.tracks = [t for t in self.tracks if t[0] != name]
        self.vias = [v for v in self.vias if v[0] != name]
        self.sm = [m for m in self.sm if m[1] != name]

    # ------------------------------------------------------------ A*
    def prepare(self, n, w):
        src = self.base if self.soft else self.occ
        foreign = [(src[l] != 0) & (src[l] != n) for l in range(NL)]
        r = int(round((VIA_D / 2 + CLR + TW / 2) / GRID))
        self._viafree = ~dilate(np.any(foreign, axis=0), r)
        extra = max(0, int(math.ceil((w - TW) / 2 / GRID - 1e-9)))
        self._widefree = [~dilate(f, extra) for f in foreign] if extra else None
        self._neckfree = [~dilate(f, 1) for f in foreign] if extra else None
        self._padzone = None
        if extra and getattr(self, '_cur_pads', None):
            m = np.zeros((self.H, self.W), dtype=bool)
            for (px, py) in self._cur_pads:
                cx, cy = self.cell(px, py)
                if 0 <= cx < self.W and 0 <= cy < self.H:
                    m[cy, cx] = True
            self._padzone = dilate(m, 12)

    def via_ok(self, cx, cy, n):
        return bool(self._viafree[cy, cx])

    def astar(self, n, starts, targets, w, bbox, via_cost, hint=None):
        """starts: list of (layer,cx,cy); targets: list of boolean masks per layer (full size)."""
        bx0, by0, bx1, by1 = bbox
        extra = max(0, int(math.ceil((w - TW) / 2 / GRID - 1e-9)))
        occ = self.base if self.soft else self.occ
        trk = self.trk
        soft = self.soft
        zone = getattr(self, '_zone', None)
        tg = targets
        # target bbox heuristic
        ty, tx = np.nonzero(np.any(tg, axis=0))
        if len(tx) == 0:
            return None
        tx0, tx1, ty0, ty1 = tx.min(), tx.max(), ty.min(), ty.max()

        def h(cx, cy):
            if hint is not None:
                dx = abs(hint[0] - cx)
                dy = abs(hint[1] - cy)
                return (max(dx, dy) + 0.414 * min(dx, dy))
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
                    if not (self._padzone is not None and self._padzone[ny, nx] and self._neckfree[l][ny, nx]):
                        continue
                if dx and dy:
                    # avoid cutting corners
                    a = occ[l][cy, nx]
                    b = occ[l][ny, cx]
                    if (a != 0 and a != n) or (b != 0 and b != n):
                        continue
                ns = (l, nx, ny)
                ng = gs + c
                if zone is not None and zone[ny, nx]:
                    ng += ZONE_COST
                if soft:
                    for k in range(3):
                        tv = trk[l][k][ny, nx]
                        if tv != 0 and tv != n:
                            ng += SOFT_PEN
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
                    if soft:
                        for k in range(NL):
                            for j in range(3):
                                tv = trk[k][j][cy, cx]
                                if tv != 0 and tv != n:
                                    ng += SOFT_PEN
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
        if name.startswith(BUS_PREFIXES):
            self._zone = None
        else:
            if getattr(self, '_zone_mask', None) is None:
                m = np.zeros((self.H, self.W), dtype=bool)
                ax, ay = self.cell(BUS_ZONE[0], BUS_ZONE[1])
                bx, by = self.cell(BUS_ZONE[2], BUS_ZONE[3])
                m[ay:by + 1, ax:bx + 1] = True
                self._zone_mask = m
            self._zone = self._zone_mask
        self._cur_pads = [(x, y) for (x, y, _l, _r) in lst]
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
                        best = (d, j, i)
            _, j, i_near = best
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
                path = self.astar(n, starts, tree, w, (bx0, by0, bx1, by1), via_cost,
                                  self.cell(pts[i_near][0], pts[i_near][1]))
                if path:
                    break
            if not path:
                ok = False
                remaining.remove(j)
                continue
            if self.soft:
                for (l_, px_, py_) in path:
                    for k_ in range(3):
                        tv = int(self.trk[l_][k_][py_, px_])
                        if tv != 0 and tv != n and tv in self.names:
                            self._culprits.add(self.names[tv])
                rv = int(round((VIA_D / 2 + CLR + TW / 2) / GRID))
                for a_, b_ in zip(path[:-1], path[1:]):
                    if a_[1:] == b_[1:] and a_[0] != b_[0]:      # via: whole disc on every layer
                        for lo in range(NL):
                            for k_ in range(3):
                                win = self.trk[lo][k_][max(a_[2] - rv, 0):a_[2] + rv + 1, max(a_[1] - rv, 0):a_[1] + rv + 1]
                                for tv in np.unique(win):
                                    tv = int(tv)
                                    if tv != 0 and tv != n and tv in self.names:
                                        self._culprits.add(self.names[tv])
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
                vx_, vy_ = self.xy(prev[1], prev[2])
                self.vias.append((name, vx_, vy_))
                self.sm.append(("v", name, vx_, vy_))
                for k in range(NL):
                    self.stamp_disc(k, vx_, vy_, n, VIA_D / 2 + CLR + TW / 2, True)
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
                self.sm.append(("t", name, l, pts, w))
                self.stamp_path(l, pts, n, w, True)

    def freeze(self, names):
        """Make finished nets permanent obstacles (they can no longer be ripped up)."""
        for it in list(self.sm):
            if it[1] not in names:
                continue
            n = self.nid(it[1])
            if it[0] == "v":
                for k in range(NL):
                    self._stamp_base(lambda k=k, it=it, n=n: self.stamp_disc(k, it[2], it[3], n, VIA_D / 2 + CLR + TW / 2))
            else:
                self._stamp_base(lambda it=it, n=n: self.stamp_path(it[2], it[3], n, it[4]))
        self.sm = [m for m in self.sm if m[1] not in names]
        self.rebuild()

    def _stamp_base(self, fn):
        """Run a stamping function against the permanent `base` map (GND stitching is never ripped up)."""
        keep = self.occ
        self.occ = self.base
        try:
            fn()
        finally:
            self.occ = keep

    def add_escape_stubs(self, rules):
        """Pre-route a short straight stub out of every fine-pitch signal pad so that neighbours cannot bend into its corridor.
        rules: {ref_prefix: (length_mm, direction_fn(x) -> -1/+1)}"""
        count = 0
        for name, lst in list(self.pads.items()):
            n = self.nid(name)
            for i, (x, y, layers, ref) in enumerate(lst):
                for prefix, (length, dfn) in rules.items():
                    if ref.startswith(prefix):
                        d = dfn(x, y)
                        dx_, dy_ = d if isinstance(d, tuple) else (d, 0)
                        xe, ye = x + dx_ * length, y + dy_ * length
                        l = layers[0]
                        pts = [(x, y), (xe, ye)]
                        # permanent: a rip-up of the net must never delete the stub that links the pad to the route
                        self.perm.append((name, l, pts, TW))
                        self.stamp_path(l, pts, n, TW)
                        self._stamp_base(lambda l=l, pts=pts, n=n: self.stamp_path(l, pts, n, TW))
                        lst[i] = (xe, ye, layers, ref)
                        count += 1
        print("escape stubs:", count, flush=True)

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

    def stitch_gnd(self, select=None):
        n = self.nid("GND")
        if not hasattr(self, '_gnd_done'):
            self._gnd_done = set()
        self.prepare(n, TW)
        done = fail = 0
        for (x, y, layer, ref) in self.gnd_pads():
            if ref in self._gnd_done or (select is not None and not select(ref)):
                continue
            cx, cy = self.cell(x, y)
            heap = [(0.0, 0, (layer, cx, cy))]
            g = {(layer, cx, cy): 0.0}
            came = {}
            cnt = 1
            found = None
            while heap:
                c0, _, s_ = heapq.heappop(heap)
                l, px, py = s_
                if c0 > 90:
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
                self._stamp_base(lambda: self.stamp_path(layer, pts, n, TW))
            vx, vy = self.xy(found[1], found[2])
            self.vias.append(("GND", vx, vy))
            for k in range(NL):
                self.stamp_disc(k, vx, vy, n, VIA_D / 2 + CLR + TW / 2)
            self._stamp_base(lambda: [self.stamp_disc(k, vx, vy, n, VIA_D / 2 + CLR + TW / 2) for k in range(NL)])
            self.prepare(n, TW)
            self._gnd_done.add(ref)
            done += 1
        print("GND stitch: %d done, %d failed" % (done, fail), flush=True)


def taper(pts, w, neck=0.25, length=1.2):
    """Neck down the first/last `length` mm (path length) of a wide track so it can enter fine-pitch pads."""
    if w <= neck + 1e-6 or len(pts) < 2:
        return [(pts, w)]
    cum = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    if total <= 2 * length:
        return [(pts, neck)]

    def at(d):
        for i in range(len(pts) - 1):
            if cum[i] <= d <= cum[i + 1] + 1e-9:
                seg = cum[i + 1] - cum[i]
                t = 0 if seg == 0 else (d - cum[i]) / seg
                return i, (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
        return len(pts) - 2, pts[-1]

    i1, p1 = at(length)
    i2, p2 = at(total - length)
    head = [pts[0]] + [pts[k] for k in range(1, i1 + 1)] + [p1]
    mid = [p1] + [pts[k] for k in range(i1 + 1, i2 + 1)] + [p2]
    tail = [p2] + [pts[k] for k in range(i2 + 1, len(pts))]

    def clean(l):
        out = [l[0]]
        for q in l[1:]:
            if abs(q[0] - out[-1][0]) > 1e-9 or abs(q[1] - out[-1][1]) > 1e-9:
                out.append(q)
        return out
    res = []
    for seg, ww in ((head, neck), (mid, w), (tail, neck)):
        seg = clean(seg)
        if len(seg) >= 2:
            res.append((seg, ww))
    return res


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


TMDS_ORDER = ["HDMI_D0N", "HDMI_D0P", "HDMI_D1N", "HDMI_D1P", "HDMI_D2N", "HDMI_D2P", "HDMI_CKN", "HDMI_CKP"]
SIDEBAND = ["HDMI_HPD", "HDMI_5V", "HDMI_SDA", "HDMI_SCL"]   # pad order from the left end: lanes peel off without crossing
PRIORITY = ["HDMI_CKN", "HDMI_CKP", "HDMI_D0N", "HDMI_D0P", "HDMI_D1N", "HDMI_D1P", "HDMI_D2N", "HDMI_D2P", "HDMI_5V", "+3V3"]


def run(b, comps):
    t0 = time.time()
    x0, y0, x1, y1 = design.BOARD
    r = Router(b.board, x0, y0, x1, y1)
    r.load(design.BOARD)
    nets = [n for n in r.pads if n not in SKIP]
    # order: wide power first, then HDMI, then by bbox size ascending
    def key(n):
        if n in TMDS_ORDER:
            return (-0.5, TMDS_ORDER.index(n))  # TMDS pairs, in the order verified by the study
        if n in SIDEBAND:
            return (-1, SIDEBAND.index(n))      # connector sideband first: it must escape from under the TMDS lanes
        if n in ORDER_W:
            return (0, -ORDER_W[n])
        if n in PRIORITY:
            return (1, PRIORITY.index(n))
        if n.startswith("HDMI_D") or n.startswith("HDMI_CK"):
            return (2, 0)
        xs = [p[0] for p in r.pads[n]]
        ys = [p[1] for p in r.pads[n]]
        return (3, -((max(xs) - min(xs)) + (max(ys) - min(ys))))
    nets.sort(key=key)
    core_x = next(c.pos[0] for c in comps if c.ref == 'J4')
    r.add_escape_stubs({'J5.': (2.6, design.hdmi_stub_dir), 'J4.': (2.4, lambda x, y, cx=core_x: -1 if x < cx else 1)})
    r.stitch_gnd(lambda ref: ref.startswith('J5.'))      # HDMI shield pins first: they sit between TMDS stubs
    failed = []
    stitched = False
    frozen = False
    for idx, n in enumerate(nets):
        if not frozen and not (n.startswith('HDMI_D') or n.startswith('HDMI_CK') or n in SIDEBAND):
            done = [m for m in nets if (m.startswith('HDMI_D') or m.startswith('HDMI_CK') or m in SIDEBAND) and m not in failed]
            r.freeze(set(done))
            print('froze TMDS nets:', len(done), flush=True)
            frozen = True
        if (not stitched and n not in ORDER_W and n not in PRIORITY
                and not n.startswith('HDMI_D') and not n.startswith('HDMI_CK')):
            r.stitch_gnd(lambda ref: ref.startswith('J4.') or ref.startswith('J2.'))
            stitched = True
        w = ORDER_W.get(n, TW)
        r.max_exp = 2000000 if n.startswith('HDMI_') else 150000
        print("[%d/%d] %s (%d pads) t=%.0fs" % (idx + 1, len(nets), n, len(r.pads[n]), time.time() - t0), flush=True)
        vc = 40.0 if n.startswith("HDMI_D") or n.startswith("HDMI_CK") else VIA_COST
        if not r.route_net(n, w, vc):
            failed.append(n)
    if failed:
        r.max_exp = 1000000
        queue = list(failed)
        attempts = {}
        final = []
        it = 0
        while queue and it < 250:
            it += 1
            name = queue.pop(0)
            attempts[name] = attempts.get(name, 0) + 1
            if attempts[name] > 12:
                final.append(name)
                continue
            print("ripup[%d] %s (attempt %d), queue=%d" % (it, name, attempts[name], len(queue)), flush=True)
            w = ORDER_W.get(name, TW)
            r.rip_net(name)
            r.rebuild()
            r.soft = True
            r._culprits = set()
            ok = r.route_net(name, w, 8.0)
            r.soft = False
            culprits = [c for c in r._culprits if c != name and c != "GND"]
            if not ok:
                r.rip_net(name)
                r.rebuild()
                final.append(name)
                continue
            for c in culprits:
                r.rip_net(c)
            r.rebuild()
            print("   culprits:", culprits, flush=True)
            for c in culprits:
                if not r.route_net(c, ORDER_W.get(c, TW), 8.0):
                    queue.append(c)
        failed = sorted(set(final + queue))
        # drop partial routes of the final failures so that no half-routed nets remain inconsistent
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
    for (name, l, pts, w) in r.perm + r.tracks:
        b.track(name, LAYER_NAMES[l], pts, w)
    for (name, x, y) in r.vias:
        b.via(name, x, y, VIA_D, VIA_DRILL)
    return r
