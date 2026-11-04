"""Generate/check the slice-by-8 CRC-16/CCITT-FALSE tables embedded in fpga/host/link_protocol.h.

T0 is the classic byte table; Tk[i] is the CRC register after byte i followed by k zero bytes.
The header region between the BEGIN/END markers is machine generated.
"""
import argparse
from pathlib import Path
import sys

HEADER = Path(__file__).resolve().parents[1] / 'host/link_protocol.h'
BEGIN = '    // BEGIN GENERATED CRC16 TABLES (fpga/tools/gen_crc16_tables.py)\n'
END = '    // END GENERATED CRC16 TABLES\n'


def tables():
    t0 = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xffff if c & 0x8000 else (c << 1) & 0xffff
        t0.append(c)
    out = [t0]
    for _ in range(7):
        prev = out[-1]
        out.append([((v << 8) & 0xffff) ^ t0[v >> 8] for v in prev])
    return out


def render():
    lines = [BEGIN, '    static const uint16_t table[8][256]={\n']
    for k, t in enumerate(tables()):
        lines.append(f'        {{ // T{k}\n')
        for i in range(0, 256, 8):
            lines.append('        ' + ','.join(f'0x{v:04x}' for v in t[i:i + 8]) + ',\n')
        lines.append('        },\n')
    lines += ['    };\n', END]
    return ''.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    a = p.parse_args()
    text = HEADER.read_text(encoding='utf-8')
    b, e = text.find(BEGIN), text.find(END)
    if b < 0 or e < 0:
        sys.exit('markers missing in ' + str(HEADER))
    new = text[:b] + render() + text[e + len(END):]
    if a.check:
        if new != text:
            sys.exit('generated CRC tables are stale')
        print('PASS CRC tables are current')
    else:
        HEADER.write_text(new, encoding='utf-8', newline='\n')
        print('wrote', HEADER)


if __name__ == '__main__':
    main()
