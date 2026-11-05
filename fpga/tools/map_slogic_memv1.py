"""Conservative offline channel mapping for a bounded MEMV1 CAPS capture.

No device/USB/serial access. Requires numpy. Accepts sigrok .sr/.srzip ZIPs
with device1, unitsize=2 and little-endian 16-bit logic chunks. Samples must
cover the explicit 0.5MHz tagged CAPS index0..8 sequence, not arbitrary traffic.
Unknown, missing and duplicate probes remain unresolved; nothing is repaired.
"""
import argparse
import configparser
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np


def crc16(data):
    value = 0xffff
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xffff
    return value


def request(index, first_seq=0x41):
    head = bytes((0xa5, 0xe0, (first_seq + index) & 255, 2, index, 0))
    return head + crc16(head).to_bytes(2, "little")


def response(index, first_seq=0x41):
    values = (0x4d31, 0x0100, 128, 16, 256, 0x0073, 1, 12)
    status, value = (0, values[index]) if index < len(values) else (3, 0)
    head = bytes((0x5a, status, (first_seq + index) & 255, 2, value & 255, value >> 8))
    return bytes([0xc3]) * 8 + head + crc16(head).to_bytes(2, "little")


def rate_number(text):
    match = re.fullmatch(r"\s*([0-9.]+)\s*([kKmMgG]?)\s*(?:Hz|hz)?\s*", text)
    if not match:
        raise ValueError("unsupported samplerate: " + text)
    return float(match[1]) * {"": 1, "k": 1e3, "m": 1e6, "g": 1e9}[match[2].lower()]


def load_capture(path, override_rate=None):
    with zipfile.ZipFile(path) as archive:
        parser = configparser.ConfigParser()
        parser.read_string(archive.read("metadata").decode("utf-8-sig"))
        devices = [s for s in parser.sections() if s.startswith("device ") or s.startswith("device")]
        if len(devices) != 1:
            raise ValueError("require exactly one logic device in archive")
        cfg = parser[devices[0]]
        if int(cfg.get("unitsize", "2")) != 2:
            raise ValueError("require unitsize=2; other layouts are not silently reinterpreted")
        base = cfg.get("capturefile", "logic-1")
        chunks = [n for n in archive.namelist() if n == base or re.fullmatch(re.escape(base) + r"-\d+", n)]
        chunks.sort(key=lambda n: int(n.rsplit("-", 1)[1]) if n != base else 0)
        if not chunks:
            raise ValueError("no logic chunks for " + base)
        raw = b"".join(archive.read(n) for n in chunks)
        if len(raw) % 2:
            raise ValueError("truncated 16-bit sample")
        samples = np.frombuffer(raw, dtype="<u2")
        hz = override_rate or rate_number(cfg["samplerate"])
        probes = int(cfg.get("total probes", "16"))
        if not 1 <= probes <= 16:
            raise ValueError("require 1..16 packed probes")
        names = {str(i): cfg.get("probe" + str(i + 1), "CH" + str(i)) for i in range(probes)}
        return samples, hz, {"chunks": chunks, "probe_names": names, "probes": probes}


def bursts(samples, channel, period):
    high = (samples & (1 << channel)) != 0
    rises = np.flatnonzero(high[1:] & ~high[:-1]) + 1
    if len(rises) < 8:
        return []
    intervals = np.diff(rises)
    # Split on any nonperiodic edge: never skip or fix an edge to make a frame.
    cuts = np.flatnonzero(np.abs(intervals - period) > max(1.1, period * .15)) + 1
    return [g for g in np.split(rises, cuts) if len(g) >= 8]


def paired_bursts(groups, max_rx_clocks=256):
    pairs = []
    for index in range(len(groups) - 1):
        tx, rx = groups[index:index + 2]
        if len(tx) == 8 and 24 <= len(rx) <= max_rx_clocks:
            pairs.append((tx, rx))
    return pairs


def level(samples, edge, channel):
    return ((samples[edge] >> channel) & 1).astype(np.uint8)


def choose(candidates):
    return {"channel": candidates[0] if len(candidates) == 1 else None,
            "candidates": candidates,
            "status": "identified" if len(candidates) == 1 else "ambiguous" if candidates else "unknown"}


def analyze(samples, samplerate, bus_hz=500000, first_seq=0x41, count=9,
            min_frames=3, probes=16, max_rx_clocks=256):
    period = samplerate / bus_hz
    if period < 6:
        raise ValueError("need >=6 samples per bus period; use a slower diagnostic transfer")
    clock_candidates = []
    for channel in range(probes):
        pairs = paired_bursts(bursts(samples, channel, period), max_rx_clocks)
        if len(pairs) < min_frames:
            continue
        # A capture may start or end partway through the known CAPS sequence.
        # Multiple equally good offsets remain ambiguous.
        alternatives = []
        span = min(len(pairs), count)
        for start_pair in range(len(pairs) - span + 1):
            selected = pairs[start_pair:start_pair + span]
            observed_edges = np.concatenate([tx - 1 for tx, _ in selected])
            observed_rx = np.concatenate([rx[:16] - 1 for _, rx in selected])
            for first_index in range(count - span + 1):
                expected = np.frombuffer(b"".join(request(first_index + k, first_seq) for k in range(span)), dtype=np.uint8)
                expected_rx = np.frombuffer(b"".join(response(first_index + k, first_seq) for k in range(span)), dtype=np.uint8)
                mappings = {}
                matched_signatures = set()
                for bit in range(8):
                    want = (expected >> bit) & 1
                    mappings["D" + str(bit)] = [ch for ch in range(probes) if ch != channel
                                               and np.array_equal(level(samples, observed_edges, ch), want)
                                               and np.array_equal(level(samples, observed_rx, ch), (expected_rx >> bit) & 1)]
                    if mappings["D" + str(bit)]:
                        matched_signatures.add(want.tobytes())
                if len(matched_signatures) < 2:
                    continue  # two duplicate wires do not prove two independent data bits
                supported = sum(bool(v) for v in mappings.values())
                alternatives.append((supported, first_index, start_pair, selected, mappings))
        if not alternatives:
            continue
        best_score = max(x[0] for x in alternatives)
        if best_score < 2:
            continue
        best = [x for x in alternatives if x[0] == best_score]
        clock_candidates.append({"channel": channel, "score": best_score, "alternatives": best, "pairs": len(pairs)})
    if not clock_candidates:
        return {"result": "insufficient_evidence", "reason": "no unique model with minimum TX8/RX24-or-longer pairs and >=2 independent matching TX/RX data bits",
                "mapping": {s: choose([]) for s in ["CLK", "DIR", "READY"] + ["D" + str(i) for i in range(8)]}}
    score = max(c["score"] for c in clock_candidates)
    best_clocks = [c for c in clock_candidates if c["score"] == score]
    if len(best_clocks) != 1 or len(best_clocks[0]["alternatives"]) != 1:
        return {"result": "ambiguous", "reason": "clock or known-frame alignment is not unique",
                "clock_candidates": [{"channel": c["channel"], "matching_data_bits": c["score"], "alignments": len(c["alternatives"])} for c in best_clocks],
                "mapping": {s: choose([c["channel"] for c in best_clocks]) if s == "CLK" else choose([])
                            for s in ["CLK", "DIR", "READY"] + ["D" + str(i) for i in range(8)]}}
    chosen = best_clocks[0]
    _, first_index, _, pairs, data = chosen["alternatives"][0]
    mapping = {"CLK": choose([chosen["channel"]])}
    for signal, candidates in data.items():
        mapping[signal] = choose(candidates)
    # Do not assign a probe to two roles even if the sampled signatures collide.
    used_data = {c for candidates in data.values() for c in candidates}
    tx_times = np.concatenate([tx - 1 for tx, _ in pairs])
    rx_times = np.concatenate([rx - 1 for _, rx in pairs])
    early = np.concatenate([rx[:2] - 1 for _, rx in pairs])
    late = np.concatenate([rx[21:] - 1 for _, rx in pairs])
    eligible = [ch for ch in range(probes) if ch != chosen["channel"] and ch not in used_data]
    direction = [ch for ch in eligible if not np.any(level(samples, tx_times, ch)) and np.all(level(samples, rx_times, ch))]
    ready = [ch for ch in eligible if not np.any(level(samples, tx_times, ch)) and np.all(level(samples, early, ch)) and not np.any(level(samples, late, ch))]
    mapping["DIR"] = choose(direction)
    mapping["READY"] = choose(ready)
    # If two different data bits have the same singleton probe, neither is proven.
    assigned = [entry["channel"] for entry in mapping.values() if entry["channel"] is not None]
    collisions = {channel for channel in assigned if assigned.count(channel) > 1}
    for entry in mapping.values():
        if entry["channel"] in collisions:
            entry["channel"] = None
            entry["status"] = "ambiguous"
    complete = all(v["status"] == "identified" for v in mapping.values())
    return {"result": "complete" if complete else "partial", "mapping": mapping,
            "evidence": {"frames": len(pairs), "caps_first_index": first_index,
                         "sequence_first": (first_seq + first_index) & 255, "clock_period_samples": period,
                         "tx_physical_clocks": [len(tx) for tx, _ in pairs],
                         "rx_physical_clocks": [len(rx) for _, rx in pairs],
                         "max_rx_clocks": max_rx_clocks, "rx_protocol_bytes": 16,
                         "rx_requested_capture_bytes": 24,
                         "rx_post_protocol_physical_clocks": [len(rx) - 16 for _, rx in pairs],
                         "clock_rule": "8 periodic TX rising edges followed by 24..max_rx_clocks physical RX rising edges; tail retained",
                         "data_rule": "all TX bytes and RX first16 prefix/header bytes match independent tagged CAPS and CRC16",
                         "control_rule": "DIR low for all TX/high for all RX; READY TX-low, RX first2-high/last3-low",
                         "tx_first_sample": int(pairs[0][0][0]), "rx_last_sample": int(pairs[-1][1][-1])},
            "limits": ["Digital sampled levels only; not analog signal-integrity proof", "Unconnected/duplicate/unsampled signals remain unknown or ambiguous", "A matching probe signature is valid only for this known traffic capture"]}


def synthetic(mapping, frames=9, omit=(), duplicate=None, extra_rx_clocks=0):
    period = 10
    tails = [extra_rx_clocks] * frames if isinstance(extra_rx_clocks, int) else list(extra_rx_clocks)
    assert len(tails) == frames and min(tails) >= 0
    stride = 400 + (24 + max(tails)) * period
    samples = np.zeros(200 + frames * stride, dtype="<u2")
    def set_signal(signal, lo, hi, state):
        if signal in omit or signal not in mapping:
            return
        channels = [mapping[signal]] + ([duplicate[1]] if duplicate and duplicate[0] == signal else [])
        for ch in channels:
            if state:
                samples[lo:hi] |= np.uint16(1 << ch)
    for index in range(frames):
        start = 100 + index * stride
        for j, byte in enumerate(request(index)):
            edge = start + j * period + period // 2
            set_signal("CLK", edge, edge + period // 2, 1)
            for bit in range(8):
                set_signal("D" + str(bit), edge - period // 2, edge + period // 2, (byte >> bit) & 1)
        rx_start = start + 180
        rx_clocks = 24 + tails[index]
        set_signal("DIR", rx_start - 15, rx_start + rx_clocks * period + 5, 1)
        set_signal("READY", start + 100, rx_start + 160, 1)
        reply = response(index)
        for j in range(rx_clocks):
            edge = rx_start + j * period + period // 2
            set_signal("CLK", edge, edge + period // 2, 1)
            if j < len(reply):
                for bit in range(8):
                    set_signal("D" + str(bit), edge - period // 2, edge + period // 2, (reply[j] >> bit) & 1)
    return samples


def self_test():
    import random
    signals = ["CLK", "DIR", "READY"] + ["D" + str(i) for i in range(8)]
    checks = 0
    for seed in range(20):
        channels = list(range(16)); random.Random(seed).shuffle(channels)
        mapping = dict(zip(signals, channels))
        result = analyze(synthetic(mapping), 5000000)
        assert result["result"] == "complete", result
        assert {s: e["channel"] for s, e in result["mapping"].items()} == mapping
        checks += 1
    # The initial probe plan has only CLK, READY, D1 and D6. Two independent
    # exact data signatures suffice when periodic TX8/RX24 and alignment have
    # one unique interpretation. Other signals must remain unresolved.
    for seed in range(20):
        channels = list(range(16)); random.Random(100 + seed).shuffle(channels)
        four = dict(zip(("CLK", "READY", "D1", "D6"), channels))
        result = analyze(synthetic(four), 5000000)
        assert result["result"] == "partial", result
        assert all(result["mapping"][signal]["channel"] == channel for signal, channel in four.items()), result
        assert all(result["mapping"][signal]["channel"] is None for signal in signals if signal not in four), result
        checks += 1
    four = {"CLK": 0, "READY": 1, "D1": 2, "D6": 3}
    result = analyze(synthetic(four, duplicate=("CLK", 15)), 5000000)
    assert result["result"] == "ambiguous" and result["mapping"]["CLK"]["channel"] is None
    checks += 1
    assert analyze(synthetic(four, frames=2), 5000000)["result"] == "insufficient_evidence"
    checks += 1
    # Finite DMA capture can leave free-running clocks after the requested
    # capture bytes. Preserve all physical RX clocks, including a varying tail.
    full = dict(zip(signals, range(len(signals))))
    for tails in (20, [0, 20, 7, 32, 1, 40, 0, 20, 4]):
        result = analyze(synthetic(full, extra_rx_clocks=tails), 5000000)
        assert result["result"] == "complete", result
        wanted = [44] * 9 if isinstance(tails, int) else [24 + n for n in tails]
        assert result["evidence"]["rx_physical_clocks"] == wanted
        checks += 1
        result = analyze(synthetic(four, extra_rx_clocks=tails), 5000000)
        assert result["result"] == "partial" and all(result["mapping"][key]["channel"] == ch for key, ch in four.items()), result
        checks += 1
    # A mismatching observed reply is not repaired by the known expectation.
    damaged = synthetic(full, extra_rx_clocks=20)
    rx_edge = 100 + 180 + 8 * 10 + 5
    damaged[rx_edge - 1] ^= np.uint16(1 << full["D3"])
    assert analyze(damaged, 5000000)["mapping"]["D3"]["channel"] is None
    checks += 1
    one_bit = {"CLK": 0, "READY": 1, "D1": 2}
    assert analyze(synthetic(one_bit, duplicate=("D1", 15)), 5000000)["result"] == "insufficient_evidence"
    checks += 1
    mapping = dict(zip(signals, range(len(signals))))
    partial = analyze(synthetic(mapping, omit=("D3", "READY")), 5000000)
    assert partial["result"] == "partial" and partial["mapping"]["D3"]["channel"] is None and partial["mapping"]["READY"]["channel"] is None
    checks += 1
    ambiguous = analyze(synthetic(mapping, duplicate=("D4", 15)), 5000000)
    assert ambiguous["mapping"]["D4"]["status"] == "ambiguous" and ambiguous["mapping"]["D4"]["channel"] is None
    checks += 1
    assert analyze(synthetic(mapping, frames=2), 5000000)["result"] == "insufficient_evidence"
    checks += 1
    assert analyze(synthetic(mapping, omit=tuple("D" + str(i) for i in range(8))), 5000000)["result"] == "insufficient_evidence"
    checks += 1
    # Exercise actual sigrok ZIP layout, chunk ordering, and metadata parsing.
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic.sr"
        raw = synthetic(mapping).tobytes()
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("metadata", "[global]\nsigrok version=0.5.2\n[device 1]\nsamplerate=5 MHz\ntotal probes=16\nunitsize=2\ncapturefile=logic-1\n")
            archive.writestr("logic-1-2", raw[400:])
            archive.writestr("logic-1-1", raw[:400])
        samples, hz, info = load_capture(path)
        assert info["chunks"] == ["logic-1-1", "logic-1-2"] and analyze(samples, hz)["result"] == "complete"
        checks += 1
    print(json.dumps({"self_test": "PASS", "checks": checks}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-rate", type=float, help="override samples per second, e.g. 5000000")
    parser.add_argument("--bus-hz", type=float, default=500000)
    parser.add_argument("--first-seq", type=lambda s: int(s, 0), default=0x41)
    parser.add_argument("--count", type=int, default=9)
    parser.add_argument("--min-frames", type=int, default=3)
    parser.add_argument("--max-rx-clocks", type=int, default=256,
                        help="maximum physical RX burst edges, including free-running tail (default 256)")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test(); return 0
    if not args.input:
        parser.error("input capture or --self-test required")
    if args.bus_hz <= 0 or not 3 <= args.min_frames <= args.count <= 9 or not 0 <= args.first_seq <= 255 or not 24 <= args.max_rx_clocks <= 4096:
        parser.error("positive bus rate, 3<=min-frames<=count<=9, first-seq 0..255, max-rx-clocks 24..4096 required")
    samples, rate, info = load_capture(args.input, args.sample_rate)
    result = analyze(samples, rate, args.bus_hz, args.first_seq, args.count, args.min_frames, info["probes"], args.max_rx_clocks)
    result.update({"input": str(args.input.resolve()), "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
                   "samplerate": rate, "samples": len(samples), "archive": info,
                   "scope": "offline inference only; no device operations"})
    text = json.dumps(result, indent=2, ensure_ascii=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["result"] in ("complete", "partial") else 2


if __name__ == "__main__":
    raise SystemExit(main())
