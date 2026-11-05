"""Prepare hash-checked local FPGA/Tab5 bundles and command plans. Never accesses devices.

Old-IP bitstreams stay under ignored fpga/build; do not commit the generated kit.
Commands are argument arrays, not shell fragments. PORT/CABLE/LOCATION must be
resolved from the newly connected devices; previous COM/cable numbers are not used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
IMAGES = {
    "gpu-baseline": ("baseline_85bac224/baseline_85bac224.fs", "85bac22420a81bbaaef26a2edff81a3deb0e2bb114a97f106c1deede8062d717", "0000E368", "gpu"),
    "gpu-phase4": ("n_phase_t4/n_phase_t4.fs", "05c51ab257d4af24e50b52a47dc110b995ae87b6552bfcbdee9cba1059317bb8", "00003194", "gpu-highrate"),
    "memv1": ("memv1/memv1_mem_v1_top_v2.fs", "8dd9890743db8c3993b19bf169f42a9c882ec76fd8f07ff08ec3491aa6f26203", "0000A692", "mem"),
    "mem-bandwidth": ("membw/t4_bw2.fs", "4eb0f8868054fd90d992f6702c3f95ec2b9d1a152482a04065f0365fa4082823", "000000AF", "mem"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revision(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def copy_checked(source, destination):
    # Archived .fs files can be read-only on Windows. Reuse an exact copy;
    # refuse to replace a different kit instead of changing its attributes.
    if destination.exists():
        if sha(source) != sha(destination):
            raise ValueError(f"Existing kit differs; select a new --output: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def firmware(build, output, required):
    config = (build / "sdkconfig").read_text(encoding="utf-8")
    missing = [setting for setting in required if setting not in config.splitlines()]
    if missing:
        raise ValueError(f"Wrong firmware config in {build}: {missing}")
    description = json.loads((build / "flasher_args.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    artifacts, flash_files = [], {}
    for address, name in description["flash_files"].items():
        source = build / name
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy_checked(source, destination)
        if sha(source) != sha(destination):
            raise ValueError("Firmware copy changed")
        artifacts.append(dict(path=str(destination), sha256=sha(destination), bytes=destination.stat().st_size))
        flash_files[address] = str(destination)
    for name in ("sdkconfig", "project_description.json"):
        copy_checked(build / name, output / name)
        artifacts.append(dict(path=str(output / name), sha256=sha(output / name)))
    elf = build / "tab5_gpu_lab.elf"
    settings = description["flash_settings"]
    args = ["-m", "esptool", "--chip", "esp32p4", "-p", "{PORT}", "-b", "460800", "--before", "default_reset", "--after", "hard_reset", "write_flash",
            "--flash_mode", settings["flash_mode"], "--flash_freq", settings["flash_freq"], "--flash_size", settings["flash_size"]]
    for address, path in flash_files.items():
        args += [address, path]
    return dict(build=str(build), bin_files=artifacts, elf_sha256=sha(elf), flash_python_args=args,
                project=json.loads((build / "project_description.json").read_text())["project_version"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host-repo", type=Path, required=True)
    p.add_argument("--images", type=Path, default=Path("D:/esp/images"))
    p.add_argument("--gpu-build", type=Path, required=True)
    p.add_argument("--mem-build", type=Path, required=True)
    p.add_argument("--highrate-build", type=Path)
    p.add_argument("--output", type=Path, default=ROOT / "fpga/build/offline-ready/kit")
    a = p.parse_args()
    # Refuse a tracked destination: redistributability of old IP is unresolved.
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", str(a.output.resolve() / "probe.fs")], capture_output=True)
    if ignored.returncode:
        p.error("--output must be in a Git-ignored directory (old-IP bitstreams)")
    a.output.mkdir(parents=True, exist_ok=True)
    manifest = dict(schema=1, hardware_access=False, carrier_commit=revision(ROOT), host_commit=revision(a.host_repo),
                    firmware={}, profiles={}, placeholders=["PORT", "CABLE", "LOCATION"],
                    limits=["No current device/ARM/USB identity is assumed.", "BW and MEMV1 opcode spaces overlap; never interchange test tools.",
                            "MEMV1 cancel remains a known DMA sequence-classification issue; excluded from initial test stages.",
                            "New firmware builds are offline candidates, not physical passes."])
    manifest["firmware"]["gpu"] = firmware(a.gpu_build.resolve(), a.output / "gpu", ["CONFIG_DOCK_JUMPER_REVIEWED=y", "CONFIG_DOCK_STREAM_SCALED=y", "CONFIG_DOCK_EXPERIMENTAL_DMA_RX=y", "CONFIG_GPU_LAB_DEMO_WIDTH=640", "CONFIG_GPU_LAB_DEMO_HEIGHT=360", "CONFIG_GPU_LAB_FRACTAL_VIVID=y"])
    manifest["firmware"]["mem"] = firmware(a.mem_build.resolve(), a.output / "mem", ["CONFIG_DOCK_JUMPER_REVIEWED=y", "CONFIG_DOCK_MEM_PROBE=y", "CONFIG_DOCK_MEM_PROBE_DMA=y"])
    if a.highrate_build:
        manifest["firmware"]["gpu-highrate"] = firmware(a.highrate_build.resolve(), a.output / "gpu-highrate", ["CONFIG_DOCK_STREAM_HIGH_RATES=y", "CONFIG_DOCK_STREAM_SCALED=y", "CONFIG_DOCK_EXPERIMENTAL_DMA_RX=y"])
    for name, (relative, expected, usercode, host) in IMAGES.items():
        source = a.images / relative
        if sha(source) != expected:
            raise ValueError(f"FPGA image hash mismatch: {source}")
        destination = a.output / (name + ".fs")
        copy_checked(source, destination)
        if sha(destination) != expected:
            raise ValueError("FPGA copy changed")
        common = ["--device", "GW2A-18C", "--cable-index", "{CABLE}", "--location", "{LOCATION}", "--frequency", "2.5MHz"]
        manifest["profiles"][name] = dict(path=str(destination), sha256=expected, usercode=usercode, host=host,
            firmware_ready=host in manifest["firmware"], sram_programmer_args=common+["--operation_index", "2", "--fsFile", str(destination)],
            read_usercode_args=common+["--operation_index", "73"], read_status_args=common+["--operation_index", "74"], expected_status="00006020")
    manifest["test_commands"] = {
        "gpu-baseline": ["tools/compare_dock_demo.py", "--port", "{PORT}", "--dma-rx-hz", "5000000", "--rx-mode", "continuous", "--stream-profile", "scaled_1024x4", "--dma-scope", "bulk", "--readout", "tile", "--triangle-batch", "on", "--empty-tiles", "on", "--tile-bins", "on", "--tx-mode", "persistent_dma", "--tx-hz", "5000000", "--tx-phase", "positive", "--tx-scope", "batch", "--rx-sample-edge", "negative", "--scenes", "1", "2", "3", "--loads", "0", "2", "--frames", "17", "--repeats", "2", "--output", "{RESULT}.json"],
        "memv1-readonly": ["tools/memv1_xfer.py", "--port", "{PORT}", "--mode", "dma", "--hz", "500000", "--tx-phase", "positive", "--edge", "positive", "--stages", "caps,status,rd1,rd256", "--expected-elf-sha", manifest["firmware"]["mem"]["elf_sha256"], "--record", "{RESULT}.json"],
        "memv1-2mhz": ["tools/memv1_xfer.py", "--port", "{PORT}", "--mode", "dma", "--hz", "2000000", "--tx-phase", "positive", "--edge", "positive", "--execute", "--stages", "caps,status,rd1,rd256,wr1,wr256,crc32,invalid,crc_error,tail", "--expected-elf-sha", manifest["firmware"]["mem"]["elf_sha256"], "--record", "{RESULT}.json"],
        "mem-bandwidth": ["tools/probe_mem_bw.py", "--execute", "--port", "{PORT}", "--mib", "1", "--bist-after", "--expected-elf-sha", manifest["firmware"]["mem"]["elf_sha256"], "--output", "{RESULT}.json"],
    }
    for name, hz in (("gpu-baseline-20mhz", "20000000"), ("gpu-phase4-25mhz", "25000000")):
        command = list(manifest["test_commands"]["gpu-baseline"])
        command[command.index("--dma-rx-hz")+1] = hz
        manifest["test_commands"][name] = command
    for name, command in manifest["test_commands"].items():
        if name.startswith("gpu-"):
            command.extend(["--half-ns", "25", "--setup-ns", "25", "--guard-ns", "2000"])
    (a.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(result="OFFLINE_KIT_READY", hardware_access=False, manifest=str(a.output / "manifest.json"), profiles=len(manifest["profiles"]), firmware=len(manifest["firmware"]))))


if __name__ == "__main__":
    main()
