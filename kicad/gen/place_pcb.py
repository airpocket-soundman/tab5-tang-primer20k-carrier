"""Greedy overlap-free placement of the movable (non-connector) parts near their target positions."""
import math

import pcbnew

import design

FIXED_BLOCKS = {"mbus", "series", "core", "pmod", "jtag", "mech"}
MARGIN = 0.25          # keep-out around other parts (mm)
EDGE = 0.9             # keep-out to board edge (mm)


def box(fp):
    bb = fp.GetBoundingBox(False)
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()),
            pcbnew.ToMM(bb.GetBottom()))


def overlap(a, b, m=MARGIN):
    return not (a[2] + m <= b[0] or b[2] + m <= a[0] or a[3] + m <= b[1] or b[3] + m <= a[1])


def is_fixed(c):
    return c.ref[0] in ("J", "H") or c.block in FIXED_BLOCKS


def run(b, comps):
    x0, y0, x1, y1 = design.BOARD
    obstacles = []
    core_box = None
    for c in comps:
        if is_fixed(c):
            bb = box(b.fps[c.ref])
            obstacles.append(bb)
            if c.block == "core":
                core_box = bb
    # fan-out area in front of the HDMI connector pads must stay free of parts
    obstacles.extend(design.FANOUT_KEEPOUTS)
    # keep the Core card area free (card lies over the carrier next to the socket)
    obstacles.append(design.CARD_KEEPOUT)

    def area(c):
        bb = box(b.fps[c.ref])
        return (bb[2] - bb[0]) * (bb[3] - bb[1])

    movable = [c for c in comps if not is_fixed(c)]
    movable.sort(key=lambda c: (-(c.ref[0] == "U"), -area(c)))
    cand = []
    R = 45
    step = 0.5
    for i in range(-int(R / step), int(R / step) + 1):
        for j in range(-int(R / step), int(R / step) + 1):
            d = math.hypot(i, j) * step
            if d <= R:
                cand.append((d, i * step, j * step))
    cand.sort()
    unplaced = []
    for c in movable:
        fp = b.fps[c.ref]
        done = False
        for rot in (c.rot, (c.rot + 90) % 360):
            b.pose(fp, c, c.pos[0], c.pos[1], rot)
            base = box(fp)
            cx0, cy0 = (base[0] + base[2]) / 2, (base[1] + base[3]) / 2
            w, h = base[2] - base[0], base[3] - base[1]
            for d, dx, dy in cand:
                nx0 = base[0] + dx
                ny0 = base[1] + dy
                bb = (nx0, ny0, nx0 + w, ny0 + h)
                if bb[0] < x0 + EDGE or bb[1] < y0 + EDGE or bb[2] > x1 - EDGE or bb[3] > y1 - EDGE:
                    continue
                if any(overlap(bb, o) for o in obstacles):
                    continue
                b.pose(fp, c, c.pos[0] + dx, c.pos[1] + dy, rot)
                c.pos = (c.pos[0] + dx, c.pos[1] + dy)
                c.rot = rot
                obstacles.append(bb)
                done = True
                break
            if done:
                break
        if not done:
            unplaced.append(c.ref)
    if unplaced:
        print("UNPLACED:", unplaced)
    return unplaced
