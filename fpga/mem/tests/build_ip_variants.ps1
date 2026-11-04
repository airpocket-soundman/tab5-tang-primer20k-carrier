# Offline build of untapped clk400 IP-option variants (generator options only). Never programs a device.
# For each entry: tag = IP output suffix (fpga/build/mem-bist-ip-<tag>), variant id = clk400x_<name>.
# Steps: (generate IP if missing; no scheduler taps) -> run_tests (tagged) -> prepare_guarded (tagged) -> prepare_variant -> gw_sh build.
param([string[]]$Names=@('dp000','dp1116','drvhigh'),
      [string]$GwBin='D:\Gowin\edu-x\Gowin_V1.9.11.03_Education_x64\IDE\bin',
      [string]$OssBin='D:\tools\oss-cad-suite\bin',
      [string]$PrimLib='D:\Gowin\edu-x\Gowin_V1.9.11.03_Education_x64\IDE\simlib\gw2a\prim_sim.v')
$ErrorActionPreference='Continue'
$repo=Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
Set-Location $repo
$env:PATH="$GwBin;$OssBin;$OssBin\..\lib;$env:PATH"
$cfg=@{
 'dp000'='CONFIG.Debug_Parameter_Enable true CONFIG.Debug_Parameter1_Value 101 CONFIG.Debug_Parameter2_Value 0 CONFIG.Debug_Parameter3_Value 0 CONFIG.Debug_Parameter4_Value 0';
 'dp1116'='CONFIG.Debug_Parameter_Enable true CONFIG.Debug_Parameter1_Value 111 CONFIG.Debug_Parameter2_Value 6 CONFIG.Debug_Parameter3_Value 40 CONFIG.Debug_Parameter4_Value 40';
 'drvhigh'='CONFIG.OUTPUT_DRV HIGH'}
foreach($n in $Names){
  $tag="x$n"
  $env:MEM_IP_TAG=$tag; $env:MEM_CLK='400'; $env:MEM_EXTRA_CFG=$cfg[$n]
  $vo="fpga/build/mem-bist-ip-$tag/generated/MemDDR3/MemDDR3.vo"
  if(-not (Test-Path $vo)){ gw_sh fpga/mem/config/generate_ip.tcl 2>&1 | Out-File -Encoding utf8 "fpga/build/ip-$tag-console.log" }
  Remove-Item Env:MEM_EXTRA_CFG,Env:MEM_CLK -ErrorAction SilentlyContinue
  $env:MEM_VO_SHA256=(Get-FileHash $vo -Algorithm SHA256).Hash.ToLower()
  Copy-Item fpga/mem/config/mem_bist_clk400.sdc "fpga/mem/config/mem_bist_$tag.sdc" -Force
  python fpga/mem/tests/run_tests.py --iverilog "$OssBin\iverilog.exe" --vvp "$OssBin\vvp.exe" --primitive-lib $PrimLib 2>&1 | Select-String '^PASS|Traceback|FATAL' | ForEach-Object { $_.Line.Substring(0,[Math]::Min(70,$_.Line.Length)) }
  python fpga/mem/tests/prepare_guarded.py 2>&1 | Select-Object -Last 1
  $env:MEM_BIST_GUARDED='1'; $env:MEM_VARIANT="clk400x_$n"
  python fpga/mem/tests/prepare_variant.py $env:MEM_VARIANT
  gw_sh fpga/mem/config/build.tcl 2>&1 | Out-File -Encoding utf8 "fpga/build/mem-variant-clk400x_$n-console.log"
  Get-Content "fpga/build/mem-variant-clk400x_$n-console.log" | Select-Object -Last 1
  Remove-Item Env:MEM_VARIANT,Env:MEM_IP_TAG,Env:MEM_VO_SHA256 -ErrorAction SilentlyContinue
}
