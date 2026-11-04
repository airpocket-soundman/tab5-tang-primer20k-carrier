"""Minimal KiCad .kicad_pcb reader: pad number -> net name of the Core SODIMM socket footprint.

Offline, no KiCad needed. The Core socket is the only footprint with more than 100 pads that
carries the F_D0 net.
"""
import re
from pathlib import Path


def _blocks(text, start_re):
    for m in re.finditer(start_re, text):
        depth = 0
        for j in range(m.start(), len(text)):
            c = text[j]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    yield text[m.start():j + 1]
                    break


def core_socket_nets(pcb_path):
    """Return {sodimm_pad: net_name_or_None} for the Core socket footprint."""
    text = Path(pcb_path).read_text(encoding='utf-8')
    sockets = [fp for fp in _blocks(text, r'\(footprint ')
               if '"F_D0"' in fp and fp.count('(pad ') > 100]
    if len(sockets) != 1:
        raise ValueError(f'expected exactly one Core socket footprint, found {len(sockets)}')
    nets = {}
    for pad in _blocks(sockets[0], r'\(pad '):
        name = re.match(r'\(pad "([^"]*)"', pad)
        if not name or not name.group(1):
            continue
        net = re.search(r'\(net (?:\d+\s+)?"([^"]*)"\)', pad)
        nets[name.group(1)] = net.group(1) if net else None
    return nets
