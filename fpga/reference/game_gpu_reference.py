"""Executable G0 clear/line/triangle contract. Golden model, not RTL speed model."""
from dataclasses import dataclass

SUBPIXEL = 16
COORD_MIN, COORD_MAX = -32768, 32767  # signed 12.4 raw units


def require_int(value):
    # bool subclasses int, but is not a wire integer value.
    if type(value) is not int:
        raise ValueError("expected built-in integer (not bool/float)")


@dataclass(frozen=True)
class Vertex:
    x: int  # raw signed 12.4
    y: int
    z: int  # unsigned reciprocal depth, larger is nearer


def edge(a, b, x, y):
    return (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x)


def inclusive(a, b):
    dy, dx = b.y - a.y, b.x - a.x
    return dy < 0 or (dy == 0 and dx > 0)


class Frame:
    def __init__(self, width, height):
        require_int(width)
        require_int(height)
        if not (1 <= width <= 640 and 1 <= height <= 360):
            raise ValueError("unsupported dimensions")
        self.width, self.height = width, height
        self.color = [0] * (width * height)
        self.depth = [0] * (width * height)

    def _validate_draw(self, vertices, color, scissor):
        for v in vertices:
            if not isinstance(v, Vertex):
                raise ValueError("expected Vertex")
            for value in (v.x, v.y, v.z):
                require_int(value)
            if not (COORD_MIN <= v.x <= COORD_MAX and COORD_MIN <= v.y <= COORD_MAX
                    and 0 <= v.z <= 65535):
                raise ValueError("vertex out of range")
        require_int(color)
        if not 0 <= color <= 65535:
            raise ValueError("RGB565 out of range")
        s = (0, 0, self.width, self.height) if scissor is None else scissor
        if type(s) not in (tuple, list) or len(s) != 4:
            raise ValueError("expected four-integer scissor")
        for value in s:
            require_int(value)
        if not (0 <= s[0] <= s[2] <= self.width and 0 <= s[1] <= s[3] <= self.height):
            raise ValueError("scissor out of range")
        return s

    def clear(self, color=0, depth=0):
        """Clear the complete target, independently of draw scissor."""
        for value in (color, depth):
            require_int(value)
            if not 0 <= value <= 65535:
                raise ValueError("clear value out of range")
        self.color[:] = [color] * len(self.color)
        self.depth[:] = [depth] * len(self.depth)

    def line(self, a, b, color, scissor=None):
        """Endpoint-ordered Bresenham; clip stores, never clamp endpoints."""
        s = self._validate_draw((a, b), color, scissor)
        x, y, x1, y1 = a.x // 16, a.y // 16, b.x // 16, b.y // 16
        dx, dy = abs(x1 - x), -abs(y1 - y)
        sx, sy = (1 if x < x1 else -1), (1 if y < y1 else -1)
        err = dx + dy
        covered = set()
        while True:
            if s[0] <= x < s[2] and s[1] <= y < s[3]:
                self.color[y * self.width + x] = color
                covered.add((x, y))
            if x == x1 and y == y1:
                return covered
            twice = 2 * err
            if twice >= dy:
                err += dy
                x += sx
            if twice <= dx:
                err += dx
                y += sy

    def triangle(self, a, b, c, color, scissor=None):
        # Validate the complete command before any framebuffer mutation.
        s = self._validate_draw((a, b, c), color, scissor)
        area = edge(a, b, c.x, c.y)
        if area == 0:
            return set()
        if area < 0:
            b, c = c, b
            area = -area
        covered = set()
        # Bounding box clips traversal; original edges and interpolation are preserved.
        for y in range(max(s[1], min(a.y, b.y, c.y) // 16),
                       min(s[3], max(a.y, b.y, c.y) // 16 + 1)):
            for x in range(max(s[0], min(a.x, b.x, c.x) // 16),
                           min(s[2], max(a.x, b.x, c.x) // 16 + 1)):
                px, py = x * 16 + 8, y * 16 + 8
                weights = (edge(b, c, px, py), edge(c, a, px, py), edge(a, b, px, py))
                if not all(w > 0 or (w == 0 and inclusive(u, v))
                           for w, (u, v) in zip(weights, ((b, c), (c, a), (a, b)))):
                    continue
                covered.add((x, y))
                z = sum(w * v.z for w, v in zip(weights, (a, b, c))) // area
                i = y * self.width + x
                if z > self.depth[i]:
                    self.depth[i], self.color[i] = z, color
        return covered
