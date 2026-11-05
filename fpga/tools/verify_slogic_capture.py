"""Validate a completed 16-bit sigrok acquisition; never accesses hardware.

A zero sigrok-cli exit code does not prove a full acquisition: the SLogic
driver can report end=error:usb-error and save fewer samples with exit 0.
"""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import re
import zipfile


def verify(path, samples, rate, channels=16, log=None):
    errors, total, digest = [], 0, hashlib.sha256()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP members')
        config = configparser.ConfigParser()
        config.read_string(archive.read('metadata').decode('utf-8-sig'))
        devices = [s for s in config.sections() if s.startswith('device ')]
        if len(devices) != 1:
            raise ValueError('Expected one logic device')
        device = config[devices[0]]
        if int(device['unitsize']) != 2 or int(device['total probes']) != channels:
            raise ValueError('Unexpected packing/channel count')
        match = re.fullmatch(r'\s*([0-9.]+)\s*([kKmMgG]?)\s*Hz\s*', device['samplerate'])
        if not match:
            raise ValueError('Invalid sample rate metadata')
        actual_rate = float(match[1]) * {'': 1, 'k': 1e3, 'm': 1e6, 'g': 1e9}[match[2].lower()]
        if actual_rate != rate:
            errors.append(f'Sample rate {actual_rate} != {rate}')
        base = device['capturefile']
        chunks = []
        for name in names:
            m = re.fullmatch(re.escape(base)+r'-(\d+)', name)
            if m:
                chunks.append((int(m[1]), name))
        chunks.sort()
        if not chunks or [i for i, _ in chunks] != list(range(1, len(chunks)+1)):
            raise ValueError('Missing or noncontiguous logic chunks')
        for _, name in chunks:
            with archive.open(name) as stream:
                while block := stream.read(512*1024):
                    digest.update(block)
                    total += len(block)
    if total != samples*2:
        errors.append(f'Packed bytes {total} != {samples*2}; acquisition incomplete')
    if log is not None:
        text = Path(log).read_text(encoding='utf-8', errors='replace')
        if re.search(r'end=error|Device only sent|LIBUSB_ERROR|usb-error', text, re.I):
            errors.append('Driver log reports acquisition/USB error')
    return dict(passed=not errors, errors=errors, expected_samples=samples,
                actual_samples=total//2, actual_bytes=total, rate=actual_rate,
                channels=channels, raw_sha256=digest.hexdigest(), hardware_access=False,
                scope='Acquisition completeness only; not probe mapping or signal timing qualification')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('--samples', type=int, required=True)
    p.add_argument('--rate', type=int, required=True)
    p.add_argument('--log', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args(argv)
    if a.samples <= 0 or a.rate <= 0:
        p.error('Positive sample count/rate required')
    try:
        result = verify(a.capture, a.samples, a.rate, log=a.log)
    except (OSError, ValueError, KeyError, configparser.Error, zipfile.BadZipFile) as exc:
        result = dict(passed=False, errors=[str(exc)], hardware_access=False)
    text = json.dumps(result, indent=2)+'\n'
    if a.output:
        a.output.write_text(text, encoding='utf-8', newline='\n')
    print(text, end='')
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
