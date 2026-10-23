"""Greedy overlap-free placement of the movable (non-connector) parts near their target positions."""
import math

import pcbnew

import design

FIXED_BLOCKS = {"mbus", "series", "core", "pmod", "jtag", "mech", "tmdsc"}
MARGIN = 0.25          # keep-out around other parts (mm)
EDGE = design.EDGE_MARGIN   # keep-out to board edge (mm), enclosure clearance


def box(fp):
    bb = fp.GetBoundingBox(False)
    return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()),
            pcbnew.ToMM(bb.GetBottom()))


def overlap(a, b, m=MARGIN):
    return not (a[2] + m <= b[0] or b[2] + m <= a[0] or a[3] + m <= b[1] or b[3] + m <= a[1])


def is_fixed(c):
    return c.ref[0] in ("J", "H") or c.ref.startswith("SW") or c.block in FIXED_BLOCKS     # switches sit at their given pose


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
    hr = design.HOLE_R + design.HOLE_CLEARANCE
    for c in comps:
        if c.ref[0] == "H":
            obstacles.append((c.pos[0] - hr, c.pos[1] - hr, c.pos[0] + hr, c.pos[1] + hr))
    obstacles.extend(design.FANOUT_KEEPOUTS)
    # keep the Core card area free (card lies over the carrier next to the socket)
    card_keepout = design.CARD_KEEPOUT          # tall parts only: low chips (block "tmds") may sit under the Core card

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
        keep = obstacles if c.block == "tmds" else obstacles + [card_keepout]
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
                if any(overlap(bb, o) for o in keep):
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
    for c in comps:
        if c.ref in design.EDGE_CONNECTORS or c.ref[0] == "H":
            continue
        bb = box(b.fps[c.ref])
        d = min(bb[0] - x0, bb[1] - y0, x1 - bb[2], y1 - bb[3])
        if d < design.EDGE_MARGIN - 0.05:
            print("EDGE-MARGIN: %s is %.2f mm from the outline (< %.1f)" % (c.ref, d, design.EDGE_MARGIN))
    for c in comps:
        if c.ref[0] == "H":
            continue
        bb = box(b.fps[c.ref])
        for h in comps:
            if h.ref[0] == "H":
                dx = max(bb[0] - h.pos[0], 0, h.pos[0] - bb[2])
                dy = max(bb[1] - h.pos[1], 0, h.pos[1] - bb[3])
                d = (dx * dx + dy * dy) ** 0.5 - design.HOLE_R
                if d < design.HOLE_CLEARANCE - 0.05:
                    print("HOLE-CLEARANCE: %s is %.1f mm from hole %s (< %.0f)" % (c.ref, d, h.ref, design.HOLE_CLEARANCE))
    usb = next((c for c in comps if c.ref == "J2"), None)
    if usb is not None:
        ub = box(b.fps["J2"])
        for c in comps:
            if c.ref[0] == "H":
                hx, hy = c.pos
                dx = max(ub[0] - hx, 0, hx - ub[2])
                dy = max(ub[1] - hy, 0, hy - ub[3])
                if (dx * dx + dy * dy) ** 0.5 < design.USB_SCREW_CLEARANCE:
                    print("USB-SCREW: J2 is %.1f mm from screw %s (< %.0f)" % ((dx * dx + dy * dy) ** 0.5, c.ref,
                                                                              design.USB_SCREW_CLEARANCE))
    if unplaced:
        print("UNPLACED:", unplaced)
    return unplaced
