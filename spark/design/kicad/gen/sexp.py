"""Minimal S-expression reader/writer for KiCad files."""
import re

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')
BS = chr(92)


class Str(str):
    """A quoted string."""


def parse(text):
    pos, stack, cur = 0, [], []
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            stack.append(cur)
            cur = []
        elif m.group(2):
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif m.group(3) is not None:
            cur.append(Str(m.group(3)))
        elif m.group(4) is not None:
            cur.append(m.group(4))
    return cur[0] if len(cur) == 1 else cur


def find(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def first(node, name):
    r = find(node, name)
    return r[0] if r else None


def quote(s):
    return '"' + s.replace(BS, BS + BS).replace('"', BS + '"') + '"'


def dump(node, indent=0):
    """Serialize back to KiCad style text."""
    if isinstance(node, Str):
        return quote(node)
    if isinstance(node, str):
        return node
    pad = '\t' * indent
    if all(not isinstance(c, list) for c in node):
        return '(' + ' '.join(dump(c) for c in node) + ')'
    head = []
    i = 0
    while i < len(node) and not isinstance(node[i], list):
        head.append(dump(node[i]))
        i += 1
    out = '(' + ' '.join(head)
    for c in node[i:]:
        if isinstance(c, list):
            out += '\n' + pad + '\t' + dump(c, indent + 1)
        else:
            out += ' ' + dump(c)
    out += '\n' + pad + ')'
    return out
