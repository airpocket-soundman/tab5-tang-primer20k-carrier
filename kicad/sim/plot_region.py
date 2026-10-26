"""python plot_region.py x0 y0 x1 y1 out.png [layer]  -- draw pads/tracks/vias of board_dump.json."""
import json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "board_dump.json")))
x0, y0, x1, y1 = map(float, sys.argv[1:5]); out = sys.argv[5]
layer = sys.argv[6] if len(sys.argv) > 6 else "F.Cu"
fig, ax = plt.subplots(figsize=(14, 14 * (y1 - y0) / (x1 - x0)))
import hashlib
def col(n):
    if n == "GND": return "#888888"
    h = int(hashlib.md5(n.encode()).hexdigest()[:6], 16)
    return "#%06x" % ((h & 0x7f7f7f) | 0x303030)
for ref, num, net, l, t, r, b in d["pads"]:
    if r < x0 or l > x1 or b < y0 or t > y1: continue
    ax.add_patch(Rectangle((l, t), r - l, b - t, fc=col(net), ec="k", lw=.3, alpha=.6))
    if (r - l) > .6: ax.text((l + r) / 2, (t + b) / 2, "%s.%s\n%s" % (ref, num, net), fontsize=5, ha="center", va="center")
for net, ly, xa, ya, xb, yb, w in d["tracks"]:
    if ly != layer: continue
    if max(xa, xb) < x0 or min(xa, xb) > x1 or max(ya, yb) < y0 or min(ya, yb) > y1: continue
    ax.plot([xa, xb], [ya, yb], color=col(net), lw=w * 14 * 1.0 / ((x1 - x0) / 14) * 5.0 / 5.0 * 5, solid_capstyle="round", alpha=.85)
for net, x, y, dia in d["vias"]:
    if x0 <= x <= x1 and y0 <= y <= y1:
        ax.add_patch(Circle((x, y), dia / 2, fc="none", ec="r", lw=.8))
ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect("equal"); ax.grid(alpha=.25)
plt.savefig(out, dpi=90, bbox_inches="tight")
