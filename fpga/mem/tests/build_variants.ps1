# Builds base + DDR3 isolation variants with Gowin Education 1.9.11.03. Never programs any device.
# Prereq (once): gw_sh fpga/mem/config/generate_ip.tcl ; python fpga/mem/tests/prepare_deep_taps.py ;
#   run_tests.py ; prepare_guarded.py   (MEM_VO_SHA256 must be set if MemDDR3.vo SHA differs from 4d37c875...)
param([string[]]$Ids=@('base','cs0','rst','refwait','pace','norst','readfirst','sampleip'),
      [string]$GwBin='D:\Gowin\edu-x\Gowin_V1.9.11.03_Education_x64\IDE\bin')
$ErrorActionPreference='Continue'  # gw_sh writes to stderr; do not abort the loop on that
$repo=Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
Set-Location $repo
$env:PATH="$GwBin;$env:PATH"
python fpga/mem/tests/prepare_variant.py all
foreach($id in $Ids){
  $env:MEM_BIST_GUARDED='1'; $env:MEM_VARIANT=$id
  $log="fpga/build/mem-variant-$id-console.log"
  gw_sh fpga/mem/config/build.tcl *>&1 | Tee-Object $log | Select-Object -Last 3
  Write-Host "== $id done: $log"
}
Remove-Item Env:MEM_VARIANT

# ---- (a) clk400: gw_sh call order (run by the main session; nothing here programs a device) ----
# Prepare IP (gw_sh), taps, RTL tests, guarded SDC, then build. Net names in prepare_deep_taps.py /
# project_vendor_clock_cone.py (n219_4, n1426_3 ...) are auto-generated; if the new MemDDR3.vo differs,
# those scripts fail loudly -> record "taps not following", do not edit names blindly.
#   $env:MEM_IP_TAG='clk400'; $env:MEM_CLK='400'
#   gw_sh fpga/mem/config/generate_ip.tcl                       # -> fpga/build/mem-bist-ip-clk400/generated/MemDDR3/MemDDR3.vo
#   (Get-FileHash fpga/build/mem-bist-ip-clk400/generated/MemDDR3/MemDDR3.vo).Hash.ToLower()   # -> $env:MEM_VO_SHA256
#   python fpga/mem/tests/prepare_deep_taps.py                  # needs MEM_VO_SHA256 = that hash
#   python fpga/mem/tests/run_tests.py --iverilog <..> --vvp <..> --primitive-lib <IDE/simlib/gw2a/prim_sim.v>
#   python fpga/mem/tests/prepare_guarded.py                    # base SDC: fpga/mem/config/mem_bist_clk400.sdc
#   python fpga/mem/tests/prepare_variant.py clk400
#   $env:MEM_BIST_GUARDED='1'; $env:MEM_VARIANT='clk400'; gw_sh fpga/mem/config/build.tcl
#   python fpga/mem/tests/record_variant.py clk400              # STA at USER 99.5625MHz is NOT assumed to pass
