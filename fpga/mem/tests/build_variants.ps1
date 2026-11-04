# Builds base + DDR3 isolation variants with Gowin Education 1.9.11.03. Never programs any device.
# Prereq (once): gw_sh fpga/mem/config/generate_ip.tcl ; python fpga/mem/tests/prepare_deep_taps.py ;
#   run_tests.py ; prepare_guarded.py   (MEM_VO_SHA256 must be set if MemDDR3.vo SHA differs from 4d37c875...)
param([string[]]$Ids=@('base','cs0','rst','refwait','pace','norst','readfirst'),
      [string]$GwBin='D:\Gowin\edu-x\Gowin_V1.9.11.03_Education_x64\IDE\bin')
$ErrorActionPreference='Stop'
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
