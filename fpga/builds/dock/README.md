# Dock OSS build (experimental)

For the local Windows setup, build and USB SRAM programming entry point, see
[Dock USB development environment](../../../docs/Dock_USB開発環境.md).

`build_oss.py` runs already installed Yosys, nextpnr-himbaechel Gowin, and
Apicula `gowin_pack`. It does not install tools, access hardware, or program a
board. Obtain and review the toolchain separately. The package versions used for
this experiment are `yowasp-yosys==0.70.0.0.post1259`,
`yowasp-nextpnr-himbaechel-gowin==0.11.1.0.post826`, and its required dependency
`apycula==0.32`. Installation and successful builds are not assumed.

For example, pass the actual executable paths for the current system:

```powershell
python fpga/builds/dock/build_oss.py link --yosys <yosys-exe> --nextpnr <nextpnr-exe> --pack <gowin-pack-exe>
python fpga/builds/dock/build_oss.py gfx --yosys <yosys-exe> --nextpnr <nextpnr-exe> --pack <gowin-pack-exe>
python -m unittest discover -s fpga/builds/dock/tests -v
```

`--output <directory>` overrides the default `fpga/build/dock-oss-<variant>`.
Each run gets a fresh `runs/<id>` directory with stage logs and outputs. The
output directory's `manifest.json` records source and tool hashes, version
queries, exact commands, stage results, and hashes of outputs produced by that
run. A failed stage prevents later stages; prior run files are never presented
as outputs of the new run. Review the manifest and logs for the particular
run, including tool diagnostics and resource use.

The target is `GW2A-LV18PG256C8/I7` with Apicula family `GW2A-18`, using the
canonical Dock CST and a 27 MHz nextpnr clock target. This Apicula family name
is distinct from the name used by the vendor build script. This flow does not
consume the vendor SDC, constrain external interface delays, or waive timing
failures. A successful build does not verify pin electrical compatibility,
clock-domain assumptions, interface timing, or operation on hardware.

References: [Apicula nextpnr-himbaechel Gowin options](https://github.com/YosysHQ/apicula/wiki/Nextpnr%E2%80%90Himbaechel-Gowin)
and [Apicula example Makefile](https://raw.githubusercontent.com/YosysHQ/apicula/master/examples/Makefile).

## Verified build scope (2026-10-28)

LINK and GFX synthesis, placement/routing and pack completed with the versions
above. Both passed the internal 27 MHz constraint. GFX inferred one BSRAM.
The pack command uses `--sspi_as_gpio` for T10/SI/D2 (Dock Key_0).
It does not request GPIO reuse of JTAG, MSPI or RECONFIG.
See [validation](../../validation/README.md) for artifact hashes and warnings.

On Windows, paths passed to YoWASP use forward slashes because WASI does not
accept native backslashes as path separators. The runner normalizes these paths.

The vendor `build.tcl` remains available for `gw_sh build.tcl link|gfx`, including
SSPI GPIO reuse, but has not been executed in Gowin EDA.
# 三角形タイル診断の追加

`build_oss.py triangle`は32×32の色・深度を内部RAMに持つ独立GFX診断を生成する。
命令は[三角形タイル試験](../../../docs/Dock三角形タイル試験.md)を参照。
既存の`link`、`gfx`とは別イメージで、全画面GPUや性能向上を示すものではない。
