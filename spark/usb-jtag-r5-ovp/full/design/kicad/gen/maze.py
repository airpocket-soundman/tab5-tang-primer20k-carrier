"""Small grid router for local edits of the r5 board (no Java / Freerouting needed).

A* on a 0.1 mm grid over (x, y, layer); 8-direction moves, via cost, same-net copper is a
target (not an obstacle). Only meant for a handful of short nets inside a window. Every
result must still pass KiCad DRC - this module never claims a clean board by itself.
Run inside KiCad's python (pcbnew).
"""
import heapq, math
import pcbnew

mm = pcbnew.ToMM
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


class Router:
    def __init__(self, board, window, layers, res=0.1, clr=0.2, via_dia=0.6, via_drill=0.3, via_cost=12.0):
        self.b, self.res, self.clr = board, res, clr
        self.x0, self.y0, self.x1, self.y1 = window
        self.nx = int(round((self.x1 - self.x0) / res)) + 1
        self.ny = int(round((self.y1 - self.y0) / res)) + 1
        self.layers = layers                    # pcbnew layer ids
        self.via_dia, self.via_drill, self.via_cost = via_dia, via_drill, via_cost
        self.prims = {l: [] for l in layers}    # layer -> [(kind, geom, net)]
        self._collect()

    # ------------------------------------------------------------------ obstacles
    def _collect(self):
        for fp in self.b.GetFootprints():
            for p in fp.Pads():
                bb = p.GetBoundingBox()
                g = (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
                for l in self.layers:
                    if p.IsOnLayer(l):
                        self.prims[l].append(('rect', g, p.GetNetname()))
        for t in self.b.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                g = (mm(t.GetX()), mm(t.GetY()), mm(t.GetWidth(t.TopLayer())) / 2)
                for l in self.layers:
                    self.prims[l].append(('circ', g, t.GetNetname()))
            elif t.GetLayer() in self.prims:
                g = (mm(t.GetStart().x), mm(t.GetStart().y), mm(t.GetEnd().x), mm(t.GetEnd().y), mm(t.GetWidth()))
                self.prims[t.GetLayer()].append(('seg', g, t.GetNetname()))

    def add_track(self, layer, pts, net, w):
        for a, c in zip(pts, pts[1:]):
            self.prims[layer].append(('seg', (a[0], a[1], c[0], c[1], w), net))

    def add_via(self, x, y, net):
        for l in self.layers:
            self.prims[l].append(('circ', (x, y, self.via_dia / 2), net))

    def _blocked(self, layer, net, grow):
        """bytearray of blocked cells on one layer for `net`, obstacles grown by `grow` mm."""
        nx, ny, res = self.nx, self.ny, self.res
        m = bytearray(nx * ny)
        def mark_rect(x0, y0, x1, y1):
            i0 = max(0, int((x0 - self.x0) / res)); i1 = min(nx - 1, int((x1 - self.x0) / res) + 1)
            j0 = max(0, int((y0 - self.y0) / res)); j1 = min(ny - 1, int((y1 - self.y0) / res) + 1)
            for j in range(j0, j1 + 1):
                row = j * nx
                for i in range(i0, i1 + 1):
                    m[row + i] = 1
        def mark_disc(cx, cy, r):
            i0 = max(0, int((cx - r - self.x0) / res)); i1 = min(nx - 1, int((cx + r - self.x0) / res) + 1)
            j0 = max(0, int((cy - r - self.y0) / res)); j1 = min(ny - 1, int((cy + r - self.y0) / res) + 1)
            r2 = r * r
            for j in range(j0, j1 + 1):
                y = self.y0 + j * res
                for i in range(i0, i1 + 1):
                    x = self.x0 + i * res
                    if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                        m[j * nx + i] = 1
        for kind, g, n in self.prims[layer]:
            if n and n == net:
                continue
            if kind == 'rect':
                mark_rect(g[0] - grow, g[1] - grow, g[2] + grow, g[3] + grow)
            elif kind == 'circ':
                mark_disc(g[0], g[1], g[2] + grow)
            else:
                x1, y1, x2, y2, w = g
                L = math.hypot(x2 - x1, y2 - y1)
                n_s = max(1, int(L / (res / 2)))
                for k in range(n_s + 1):
                    mark_disc(x1 + (x2 - x1) * k / n_s, y1 + (y2 - y1) * k / n_s, w / 2 + grow)
        return m

    # ------------------------------------------------------------------ routing
    def route(self, net, w, terminals, allowed=None):
        """terminals: [(x, y, layer or None)]. Connect all (first is the seed).
        Returns (tracks, vias): tracks=[(layer,[pts],w)], vias=[(x,y)]; None if unroutable."""
        layers = [l for l in self.layers if (allowed is None or l in allowed)]
        trk = {l: self._blocked(l, net, self.clr + w / 2) for l in layers}
        via = {l: self._blocked(l, net, self.clr + self.via_dia / 2) for l in layers}
        nx, ny, res = self.nx, self.ny, self.res
        def cell(x, y): return int(round((x - self.x0) / res)), int(round((y - self.y0) / res))
        def xy(i, j): return self.x0 + i * res, self.y0 + j * res
        tree = {}
        tracks, vias = [], []
        first = True
        for (tx, ty, tl) in terminals:
            ci, cj = cell(tx, ty)
            tls = [tl] if tl is not None else layers
            if first:
                for l in tls: tree[(ci, cj, l)] = 1
                first = False
                continue
            goals = set(tree)
            starts = [(ci, cj, l) for l in tls]
            path = self._astar(starts, goals, trk, via, layers, nx, ny)
            if path is None:
                print('  maze: no path to terminal', (tx, ty, tl), 'for net', net)
                return None
            for c in path: tree[c] = 1
            t, v = self._to_geometry(path, w, xy)
            tracks += t; vias += v
        return tracks, vias

    def _astar(self, starts, goals, trk, via, layers, nx, ny):
        gi = [g[0] for g in goals]; gj = [g[1] for g in goals]
        gcx, gcy = sum(gi) / len(gi), sum(gj) / len(gj)
        def h(i, j): return 0.0 if len(goals) > 40 else math.hypot(i - gcx, j - gcy) * 0.5
        pq = []; best = {}; prev = {}
        for s in starts:
            best[s] = 0.0; heapq.heappush(pq, (h(s[0], s[1]), 0.0, s, (0, 0)))
        while pq:
            f, g, cur, d = heapq.heappop(pq)
            if g > best.get(cur, 1e18) + 1e-9: continue
            if cur in goals:
                path = [cur]
                while path[-1] in prev: path.append(prev[path[-1]])
                return path[::-1]
            i, j, l = cur
            for di, dj in DIRS:
                ni, nj = i + di, j + dj
                if not (0 <= ni < nx and 0 <= nj < ny): continue
                nxt = (ni, nj, l)
                if trk[l][nj * nx + ni] and nxt not in goals: continue
                if di and dj and (trk[l][j * nx + ni] or trk[l][nj * nx + i]): continue   # no corner cutting
                ng = g + math.hypot(di, dj) + (0.3 if (di, dj) != d else 0.0)
                if ng < best.get(nxt, 1e18):
                    best[nxt] = ng; prev[nxt] = cur
                    heapq.heappush(pq, (ng + h(ni, nj), ng, nxt, (di, dj)))
            if all(not via[ll][j * nx + i] for ll in layers):      # through via: free on every layer
                for l2 in layers:
                    if l2 == l: continue
                    nxt = (i, j, l2); ng = g + self.via_cost
                    if ng < best.get(nxt, 1e18):
                        best[nxt] = ng; prev[nxt] = cur
                        heapq.heappush(pq, (ng + h(i, j), ng, nxt, (0, 0)))
        return None

    def _to_geometry(self, path, w, xy):
        tracks, vias = [], []
        def flush(s):
            if len(s) < 2: return
            pts = [xy(c[0], c[1]) for c in s]
            out = [pts[0]]
            for k in range(1, len(pts) - 1):
                a, c = pts[k], pts[k + 1]
                d1 = (a[0] - out[-1][0], a[1] - out[-1][1]); d2 = (c[0] - a[0], c[1] - a[1])
                if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-9: out.append(a)
            out.append(pts[-1])
            tracks.append((s[0][2], out, w))
        seg = [path[0]]
        for a, c in zip(path, path[1:]):
            if a[2] != c[2]:
                flush(seg); seg = [c]; vias.append(xy(a[0], a[1]))
            else:
                seg.append(c)
        flush(seg)
        return tracks, vias
