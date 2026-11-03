"""C row-response validation against independent tile/CRC reference data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from reference.link_protocol import crc16, crc_valid, request, seal
from reference.triangle_tile import TriangleTile, ROW


class TriangleRowsCodec(unittest.TestCase):
    def test_c_rows_and_corruption(self):
        configured = os.environ.get('CARRIER_CC_JSON')
        compiler = json.loads(configured) if configured else [shutil.which('cc') or shutil.which('gcc')]
        if not compiler[0]:
            self.skipTest('Existing C compiler unavailable')
        tile = TriangleTile()
        cases = []

        def expected_header(q, r):
            return (len(r) >= 8 and q[1] == ROW and q[4] < 32 and q[5] < 2
                    and r[:4] == bytes([0x5a, 0, q[2], 2]) and r[4:6] == q[4:6]
                    and crc_valid(r[:8]))

        def add(q, r):
            header = expected_header(q, r)
            full = (len(r) == 74 and header
                    and int.from_bytes(r[72:74], 'little') == crc16(r[:6]+r[8:72]))
            cases.append((q, r, header, full))

        # Ordinary error responses remain eight bytes and never enter the
        # fixed-size full-response validator in the caller below.
        for row, plane in [(0,0),(31,1),(32,0),(0,2),(255,255)]:
            q = request(ROW, len(cases), row, plane)
            r = tile.exchange(q)
            self.assertEqual(len(r), 8)
            self.assertNotEqual(r[1], 0)
            add(q,r)
        tile.exchange(request(0x2b,0,0x34,0x12))
        # Nonuniform color and depth make ordering/endian mistakes observable.
        for i, value in enumerate([-8,8, 504,24, 16,496, 1,32768,65535,0x9a35]):
            word = value & 65535
            tile.exchange(request(0x21+i,i,word&255,word>>8))
        tile.exchange(request(0x2c,0))
        for plane in range(2):
            pixels = tile.frame.color if plane == 0 else tile.frame.depth
            for row in range(32):
                q = request(ROW, (plane*32+row)&255, row, plane)
                r = tile.exchange(q)
                self.assertEqual(len(r),74)
                self.assertEqual([int.from_bytes(r[i:i+2],'little') for i in range(8,72,2)],
                                 pixels[row*32:row*32+32])
                add(q,r)
                # Every byte, including both independent CRC fields, is covered.
                for offset in range(74):
                    damaged = bytearray(r); damaged[offset] ^= 1
                    add(q,bytes(damaged))

        q = request(ROW,0x83,7,1)
        r = tile.exchange(q)
        for offset in (2,4,5):
            # Bind the trailer to sequence/row/plane, even if an intermediary
            # changes and reseals the ordinary eight-byte response header.
            prefix = bytearray(r[:6]); prefix[offset] ^= 1
            rebound_q = bytearray(q[:6]); rebound_q[offset] = prefix[offset]
            rebound_q = seal(rebound_q)
            stale_body = seal(prefix)+r[8:]
            self.assertTrue(expected_header(rebound_q, stale_body))
            add(rebound_q,stale_body)
            rebound = seal(prefix)+r[8:72]+crc16(prefix+r[8:72]).to_bytes(2,'little')
            add(rebound_q,rebound)
        # Unknown opcodes must fail even with internally consistent row data.
        add(request(0xff,q[2],q[4],q[5]),r)
        for row, plane in [(32,0),(0,2)]:
            invalid_q = request(ROW,0x84,row,plane)
            add(invalid_q,tile.exchange(invalid_q))
        bad_q = bytearray(q); bad_q[6] ^= 1
        add(q,tile.exchange(bad_q))
        # Caller discards truncated success frames instead of passing a shorter
        # array to the 74-byte function (whose API has no length parameter).
        for length in (8,30,72,73):
            add(q,r[:length])

        header = Path(__file__).resolve().parents[1]/'link_protocol.h'
        source = '''#include <stdio.h>
#include "HEADER"
int main(void) {
    unsigned n, v;
    while(scanf("%u", &n)==1) {
        uint8_t q[8],r[74]={0};
        if(n<8 || n>74) return 2;
        for(unsigned i=0;i<8;i++) { if(scanf("%x",&v)!=1) return 3; q[i]=(uint8_t)v; }
        for(unsigned i=0;i<n;i++) { if(scanf("%x",&v)!=1) return 4; r[i]=(uint8_t)v; }
        const bool called=n==TRI_ROW_RESPONSE_BYTES;
        const bool full=called ? link_validate_row_response(r,q) : false;
        printf("%d %d %d\\n",link_validate_response(r,q),called,full);
    }
    return 0;
}
'''.replace('HEADER',header.as_posix())
        with tempfile.TemporaryDirectory(prefix='triangle-row-codec-') as tmp:
            path = Path(tmp)/'rows.c'; path.write_text(source,encoding='utf-8')
            binary = Path(tmp)/('rows.exe' if os.name=='nt' else 'rows')
            subprocess.run([*compiler,'-std=c99','-Wall','-Wextra','-Werror',str(path),'-o',str(binary)],check=True)
            data = ''.join(str(len(r))+' '+' '.join(f'{b:02x}' for b in q+r)+'\n'
                           for q,r,_,_ in cases)
            run = subprocess.run([str(binary)],input=data,text=True,capture_output=True,check=True)
        lines = run.stdout.splitlines()
        self.assertEqual(len(lines),len(cases))
        for (q,r,header_valid,full_valid),line in zip(cases,lines):
            with self.subTest(op=q[1],seq=q[2],length=len(r),row=q[4],plane=q[5],response=r.hex()):
                self.assertEqual(tuple(map(int,line.split())),
                                 (int(header_valid),int(len(r)==74),int(full_valid)))


if __name__ == '__main__':
    unittest.main()
