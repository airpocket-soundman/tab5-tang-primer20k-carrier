"""Fetch and verify the pinned Sipeed DDR-test files used by the `sampleip*` variants.

Source: https://github.com/sipeed/TangPrimer-20K-example commit e469df4c0c9c41824f405a8515decf24ef1e8e6f
        DDR-test/LicheeTang20K_DDR_Test/ (BSD 3-Clause, LAKKA; the vendor IP inside is Gowin's generated,
        encrypted output). Files are NOT committed to this repository; they land in the ignored fpga/build.
Verification is by SHA-256 of the LF-normalized content (a git clone with CRLF conversion is accepted).
Default is verify-only; --download fetches missing files (needs network, user permission).
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

COMMIT = 'e469df4c0c9c41824f405a8515decf24ef1e8e6f'
BASE = f'https://raw.githubusercontent.com/sipeed/TangPrimer-20K-example/{COMMIT}/DDR-test/LicheeTang20K_DDR_Test/'
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'build/sipeed-ddr-test-e469df4c'
RECORD = ROOT / 'validation/sipeed-ddr-test-reference-2026-11-04.json'


def lf_sha(data):
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--download', action='store_true')
    p.add_argument('--dest', type=Path, default=DEST)
    args = p.parse_args()
    files = json.loads(RECORD.read_text(encoding='utf-8'))['files']
    bad = []
    for rel, info in files.items():
        path = args.dest / rel
        if not path.exists() and args.download:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(urllib.request.urlopen(BASE + rel, timeout=60).read())
        if not path.exists():
            bad.append((rel, 'missing'))
        elif lf_sha(path.read_bytes()) != info['sha256_lf_normalized']:
            bad.append((rel, 'sha256 mismatch'))
    print('OK: all', len(files), 'files match the pinned hashes' if not bad else f'FAIL: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
