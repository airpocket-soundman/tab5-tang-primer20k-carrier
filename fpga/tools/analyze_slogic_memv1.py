"""Offline fixed-probe MEMV1 RD256 waveform/receiver comparison; never opens a device.

Streams packed 16-bit sigrok ZIP chunks twice. Only DIR-high regions are retained.
Mapping: physical CLK=CH7, DIR=CH5, READY=CH6; data bit0..7=CH15..CH8.
Offsets are relative to observed probe threshold crossings, NOT ESP32 internal
sampling phase. Raw edges are neither skipped nor reconstructed. Canonical byte
extraction is explicit (default physical falling+0ns), never an automatic retry.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile
import numpy as np
from map_slogic_memv1 import crc16, rate_number
import configparser

MAPPING = {"CLK": 7, "DIR": 5, "READY": 6, "D0..D7": list(range(15, 7, -1))}
BLOCK_BYTES = 2 * 1024 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blocks(archive, names):
    offset = 0
    for name in names:
        with archive.open(name) as source:
            while raw := source.read(BLOCK_BYTES):
                if len(raw) % 2:
                    raise ValueError("odd-sized packed logic block")
                values = np.frombuffer(raw, dtype="<u2")
                yield offset, values
                offset += len(values)


def regions(path):
    with zipfile.ZipFile(path) as archive:
        metadata = configparser.ConfigParser()
        metadata.read_string(archive.read("metadata").decode("utf-8-sig"))
        devices = [s for s in metadata.sections() if s.startswith("device")]
        if len(devices) != 1:
            raise ValueError("exactly one device required")
        cfg = metadata[devices[0]]
        if int(cfg.get("unitsize", "2")) != 2 or int(cfg.get("total probes", "16")) != 16:
            raise ValueError("explicit fixed mapping requires packed 16-channel, 2-byte samples")
        rate = rate_number(cfg["samplerate"])
        base = cfg.get("capturefile", "logic-1")
        names = sorted((n for n in archive.namelist() if re.fullmatch(re.escape(base) + r"-\d+", n)), key=lambda n: int(n.rsplit("-", 1)[1]))
        if not names:
            raise ValueError("no logic chunks")
        spans, start, previous, total = [], None, False, 0
        for offset, values in blocks(archive, names):
            high = (values & 32) != 0
            changes = np.flatnonzero(high[1:] != high[:-1]) + 1
            if bool(high[0]) != previous:
                changes = np.r_[0, changes]
            for index in changes:
                if high[index]:
                    start = offset + int(index)
                elif start is not None:
                    spans.append((start, offset + int(index)))
                    start = None
            previous, total = bool(high[-1]), offset + len(values)
        if start is not None:
            raise ValueError("capture ends with incomplete DIR-high interval")
        roi = [(max(0, low - 64), min(total, high + 64)) for low, high in spans]
        pieces = [[] for _ in roi]
        for offset, values in blocks(archive, names):
            end = offset + len(values)
            for index, (low, high) in enumerate(roi):
                if low < end and high > offset:
                    pieces[index].append(values[max(0, low - offset):min(len(values), high - offset)].copy())
        return rate, total, [(spans[i], roi[i][0], np.concatenate(part)) for i, part in enumerate(pieces)]


def extract_edges(values, span, base):
    clock = (values & 128) != 0
    rising = np.flatnonzero(clock[1:] & ~clock[:-1]) + 1
    falling = np.flatnonzero(~clock[1:] & clock[:-1]) + 1
    return {name: edges[(edges >= span[0] - base) & (edges < span[1] - base)]
            for name, edges in (("rising", rising), ("falling", falling))}


def data_bytes(values):
    data = np.zeros(len(values), dtype=np.uint8)
    for bit, channel in enumerate(MAPPING["D0..D7"]):
        data |= ((values >> channel) & 1).astype(np.uint8) << bit
    return data


def candidates(stream, seq, length):
    found = []
    for offset in range(min(64, max(0, len(stream) - length + 1))):
        header = stream[offset:offset + 8]
        if header[:4] != bytes((0x5a, 0, seq, 2)):
            continue
        body = stream[offset:offset + length]
        prefix = offset >= 8 and stream[offset - 8:offset] == bytes([0xc3]) * 8
        hc = crc16(header[:6]) == int.from_bytes(header[6:8], "little")
        bound = crc16(body[:6] + body[8:-2])
        found.append((offset, body, {"header_offset": offset, "header_hex": header.hex(), "prefix8_valid": prefix,
                                   "header_crc_valid": hc, "bound_crc_calculated": f"{bound:04x}",
                                   "bound_crc_received": f"{int.from_bytes(body[-2:], 'little'):04x}",
                                   "bound_crc_valid": bound == int.from_bytes(body[-2:], "little")}))
    return found


def compare(wire, receiver):
    differences = [{"response_offset": index, "payload_offset": index - 8 if 8 <= index < len(wire) - 2 else None,
                    "wire": f"{left:02x}", "p4": f"{right:02x}", "xor": f"{left ^ right:02x}"}
                   for index, (left, right) in enumerate(zip(wire, receiver)) if left != right]
    return {"wire_length": len(wire), "p4_length": len(receiver), "differing_bytes": len(differences), "differences": differences,
            "one_to_zero_bits": dict(Counter(str(bit) for left, right in zip(wire, receiver) for bit in range(8) if left & (1 << bit) and not right & (1 << bit))),
            "zero_to_one_bits": dict(Counter(str(bit) for left, right in zip(wire, receiver) for bit in range(8) if right & (1 << bit) and not left & (1 << bit))),
            "p4_header_crc_valid": crc16(receiver[:6]) == int.from_bytes(receiver[6:8], "little"),
            "p4_bound_crc_calculated": f"{crc16(receiver[:6] + receiver[8:-2]):04x}",
            "p4_bound_crc_received": f"{int.from_bytes(receiver[-2:], 'little'):04x}"}


def histogram(values):
    return {str(int(key)): int(value) for key, value in zip(*np.unique(values, return_counts=True))}


def stability(values, times, reference, sample_ns):
    result = {}
    for bit in (1, 6, 7, 4):
        signal = ((values >> (15 - bit)) & 1).astype(np.uint8)
        changes = np.flatnonzero(signal[1:] != signal[:-1]) + 1
        wanted = (np.frombuffer(reference, dtype=np.uint8) >> bit) & 1
        previous_changes, next_changes = [], []
        for index in np.flatnonzero(wanted[1:] != wanted[:-1]) + 1:
            location = np.searchsorted(changes, times[index], side="right")
            if location:
                previous_changes.append((times[index] - changes[location - 1]) * sample_ns)
        for index in np.flatnonzero(wanted[:-1] != wanted[1:]):
            location = np.searchsorted(changes, times[index], side="right")
            if location < len(changes):
                next_changes.append((changes[location] - times[index]) * sample_ns)
        def stats(samples):
            return {"count": len(samples), "min_ns": float(min(samples)), "median_ns": float(np.median(samples)), "max_ns": float(max(samples))} if samples else None
        result["D" + str(bit)] = {"stable_before_canonical_sample": stats(previous_changes), "stable_after_canonical_sample": stats(next_changes)}
    return result


def analyze(args):
    rate, count, rois = regions(args.capture)
    sample_ns = 1e9 / rate
    phase_offsets = (-30, -20, -10, 0, 10, 20, 30, 40)
    p4 = args.p4.read_bytes() if args.p4 else None
    if p4 is not None and len(p4) != args.body_bytes:
        raise ValueError("P4 length differs from explicit response length")
    reports, canonical = [], []
    for number, (span, base, values) in enumerate(rois):
        edges = extract_edges(values, span, base)
        if len(edges["rising"]) < args.body_bytes:
            continue
        data = data_bytes(values)
        phases = []
        for name, locations in edges.items():
            for shift_ns in sorted(set(phase_offsets + (args.canonical_offset_ns,))):
                shift = shift_ns / sample_ns
                if abs(shift - round(shift)) > 1e-7:
                    raise ValueError("offset is not an integral number of acquired samples")
                samples = locations + int(round(shift))
                if np.any(samples < 0) or np.any(samples >= len(data)):
                    raise ValueError("phase offset exceeds retained ROI")
                stream = bytes(data[samples])
                possible = candidates(stream, args.seq, args.body_bytes)
                phase = {"physical_edge": name, "offset_ns": shift_ns, "header_candidates": [entry for _, _, entry in possible],
                         "first_24_observed_bytes_hex": stream[:24].hex()}
                valid = [(offset, body, info) for offset, body, info in possible if info["prefix8_valid"] and info["header_crc_valid"] and info["bound_crc_valid"]]
                phase["valid_candidate_count"] = len(valid)
                fixed_header = 8 if name == "rising" else 9
                phase["valid_at_fixed_byte_clock_alignment"] = len(valid) == 1 and valid[0][0] == fixed_header
                if len(valid) == 1:
                    offset, body, info = valid[0]
                    phase["frame_sha256"] = hashlib.sha256(body).hexdigest()
                    if p4 is not None:
                        phase["p4_differing_bytes"] = sum(a != b for a, b in zip(body, p4))
                    if name == args.canonical_edge and shift_ns == args.canonical_offset_ns:
                        canonical.append((number, body, values, locations[offset:offset + args.body_bytes], edges, base, span))
                phases.append(phase)
        rising = edges["rising"]
        high_width = [int(edges["falling"][np.searchsorted(edges["falling"], edge, side="right")] - edge)
                      for edge in rising if np.searchsorted(edges["falling"], edge, side="right") < len(edges["falling"])]
        periods = np.diff(rising)
        expected_period = rate / args.bus_hz
        ready = ((values >> 6) & 1).astype(np.uint8)
        ready_transitions = np.flatnonzero(ready[1:] != ready[:-1]) + 1
        reports.append({"dir_interval_index": number, "dir_start_sample": span[0], "dir_end_sample": span[1],
                        "raw_rising_edges": len(rising), "raw_falling_edges": len(edges["falling"]),
                        "rising_period_samples": histogram(periods), "high_width_samples": histogram(high_width),
                        "mean_period_ns": float(np.mean(periods) * sample_ns),
                        "short_interval_indices": np.flatnonzero(periods < .75 * expected_period).tolist(),
                        "long_interval_indices": np.flatnonzero(periods > 1.5 * expected_period).tolist(),
                        "ready_transitions": [{"sample": base + int(t), "level": int(ready[t]),
                                               "rising_edges_before_transition": int(np.searchsorted(rising, t))}
                                              for t in ready_transitions if span[0] - base <= t < span[1] - base], "phases": phases})
    if len(canonical) != 1:
        raise ValueError(f"canonical extraction must have one unique CRC-valid candidate across all DIR intervals, found {len(canonical)}")
    number, wire, values, times, edges, base, span = canonical[0]
    valid_hashes = {p["frame_sha256"] for group in reports for p in group["phases"] if p.get("valid_candidate_count") == 1}
    if len(valid_hashes) != 1:
        raise ValueError("CRC-valid phase samples disagree in frame contents; refuse to select")
    reference = np.frombuffer(wire, dtype=np.uint8)
    for group in reports:
        if group["dir_interval_index"] != number:
            continue
        for phase in group["phases"]:
            locations = edges[phase["physical_edge"]]
            shift = int(round(phase["offset_ns"] / sample_ns))
            # A fixed observed header position per edge, not CRC-guided byte edits.
            offset = 8 if phase["physical_edge"] == "rising" else 9
            other = data_bytes(values)[locations[offset:offset + len(wire)] + shift]
            xor = other ^ reference
            phase["fixed_alignment_to_canonical"] = {"header_offset": offset, "different_bytes": int(np.count_nonzero(xor)),
                                                       "D1_different_bits": int(np.count_nonzero(xor & 2)), "D6_different_bits": int(np.count_nonzero(xor & 64))}
    caps = json.loads((args.capture.parent / "caps.json").read_text()) if (args.capture.parent / "caps.json").exists() else None
    output = {"scope": "offline digital probe waveform; no repair, device operation, or inference of P4 internal phase",
              "script_sha256": sha(__file__), "mapping_module_sha256": sha(Path(__file__).with_name("map_slogic_memv1.py")),
              "capture_path": str(args.capture.resolve()), "capture_sha256": sha(args.capture), "sample_rate": rate, "total_samples": count,
              "retained_roi_samples": sum(len(values) for _, _, values in rois), "all_dir_intervals": len(rois), "mapping": MAPPING,
              "canonical": {"physical_edge": args.canonical_edge, "offset_ns": args.canonical_offset_ns, "dir_interval_index": number,
                            "header_hex": wire[:8].hex(), "length": len(wire), "frame_sha256": hashlib.sha256(wire).hexdigest(),
                            "bound_crc": f"{crc16(wire[:6] + wire[8:-2]):04x}", "header_crc_valid": True, "bound_crc_valid": True},
              "groups": reports, "stability": stability(values, times, wire, sample_ns),
              "limitations": ["10ns digital threshold sampling; sub-sample glitches and analog setup/hold are unresolved", "Physical probe CLK edges are not direct observations of the P4 internal sampling phase", "Probe loading, threshold, READY reconnection and PLL/reprogramming can change conditions", "Clock tails after READY are retained and not repaired or discarded"]}
    run_path = args.capture.parent / "run.json"
    if run_path.exists():
        run = json.loads(run_path.read_text())
        host = run.get("host_command", [])
        edge_index = host.index("--edge") if "--edge" in host else None
        output["capture_conditions"] = {"run_source_sha256": sha(run_path), "threshold_v": run.get("threshold_v"),
                                        "prearm": run.get("prearm"), "trigger": run.get("trigger"),
                                        "host_command": host, "host_requested_edge_label": host[edge_index + 1] if edge_index is not None else None}
    if caps:
        rd = next((frame for frame in caps.get("frames", []) if frame.get("label") == "RD 256 beats"), None)
        output["firmware_claim"] = {"result": caps.get("result"), "dma_options": caps.get("dma_options"),
                                    "rx_hz": caps.get("rx_hz"), "tx_hz": caps.get("tx_hz"),
                                    "rd256": rd, "rd256_stage": caps.get("stages", {}).get("rd256"),
                                    "source_sha256": sha(args.capture.parent / "caps.json")}
    output["phase_alignment_note"] = "Window mismatch counts keep rising header clock8/falling9 fixed. A CRC-valid candidate at another header clock is a whole-byte phase wrap, not evidence that the same byte is valid at that clock."
    output["p4_response_available"] = p4 is not None
    if p4 is not None:
        output["p4_response_path"] = str(args.p4.resolve())
        output["p4_response_sha256"] = sha(args.p4)
        output["comparison"] = compare(wire, p4)
    return output, wire


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--wire-output", required=True, type=Path)
    parser.add_argument("--p4", type=Path)
    parser.add_argument("--seq", type=lambda text: int(text, 0), default=0x53)
    parser.add_argument("--body-bytes", type=int, default=4106)
    parser.add_argument("--bus-hz", type=float, default=16000000)
    parser.add_argument("--canonical-edge", choices=("rising", "falling"), default="falling")
    parser.add_argument("--canonical-offset-ns", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.seq <= 255 or args.body_bytes < 10 or args.bus_hz <= 0:
        parser.error("valid sequence, response length >=10 and positive bus rate required")
    output, wire = analyze(args)
    args.wire_output.write_bytes(wire)
    output["wire_frame_path"] = str(args.wire_output.resolve())
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "canonical": output["canonical"],
                      "p4_differing_bytes": output.get("comparison", {}).get("differing_bytes")}, ensure_ascii=True))


if __name__ == "__main__":
    main()
