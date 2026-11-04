# Offline build of the second regenerated-IP variant batch (2026-11-05, Education 1.9.11.03). Never programs a device.
# Each variant keeps the scheduler taps: IP(tag) -> prepare_deep_taps -> run_tests(tagged) -> prepare_guarded -> prepare_variant -> gw_sh build -> record_variant.
# Addr_Cmd_Mode 2T is rejected by this generator version (ERROR: Value '2T' is no found), so the 2T variants are not produced.
param([string[]]$Names=@('nip_b_324_drvhigh','nip_d_297','nip_e_360'),
      [string]$GwBin='D:\Gowin\Gowin_V1.9.11.03_Education_x64\IDE\bin',
      [string]$OssBin='D:\GitHub\airpocket-soundman\tab5-tang-primer20k-carrier-main\fpga\build\windows-tools\oss-cad-suite\bin',
      [string]$PrimLib='D:\Gowin\Gowin_V1.9.11.03_Education_x64\IDE\simlib\gw2a\prim_sim.v')
$ErrorActionPreference='Continue'
$repo=Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
Set-Location $repo
$env:PATH="$GwBin;$OssBin;$OssBin\..\lib;$env:PATH"
$cfg=@{
 'nip_b_324_drvhigh'=@('n2b','324','1T','CONFIG.OUTPUT_DRV HIGH');
 'nip_d_297'=@('n2d','297','1T','');
 'nip_e_360'=@('n2e','360','1T','')}
foreach($n in $Names){
  $c=$cfg[$n];$tag=$c[0]
  $env:MEM_IP_TAG=$tag;$env:MEM_CLK=$c[1];$env:MEM_ADDR_CMD=$c[2];$env:MEM_EXTRA_CFG=$c[3]
  $vo="fpga/build/mem-bist-ip-$tag/generated/MemDDR3/MemDDR3.vo"
  if(-not (Test-Path $vo)){ gw_sh fpga/mem/config/generate_ip.tcl 2>&1 | Out-File -Encoding utf8 "fpga/build/ip-$tag-console.log" }
  Remove-Item Env:MEM_CLK,Env:MEM_ADDR_CMD,Env:MEM_EXTRA_CFG -ErrorAction SilentlyContinue
  $env:MEM_VO_SHA256=(Get-FileHash $vo -Algorithm SHA256).Hash.ToLower()
  python fpga/mem/tests/prepare_deep_taps.py 2>&1 | Select-Object -Last 1
  python fpga/mem/tests/run_tests.py --iverilog "$OssBin\iverilog.exe" --vvp "$OssBin\vvp.exe" --primitive-lib $PrimLib 2>&1 | Select-String '^PASS|Traceback|FATAL|Error' | ForEach-Object { $_.Line.Substring(0,[Math]::Min(70,$_.Line.Length)) }
  python fpga/mem/tests/prepare_guarded.py 2>&1 | Select-Object -Last 1
  $env:MEM_BIST_GUARDED='1'; $env:MEM_VARIANT=$n
  python fpga/mem/tests/prepare_variant.py $n
  gw_sh fpga/mem/config/build.tcl 2>&1 | Out-File -Encoding utf8 "fpga/build/mem-variant-$n-console.log"
  Get-Content "fpga/build/mem-variant-$n-console.log" | Select-Object -Last 1
  Remove-Item Env:MEM_VARIANT,Env:MEM_IP_TAG,Env:MEM_VO_SHA256,Env:MEM_BIST_GUARDED -ErrorAction SilentlyContinue
}
# After the builds: $env:MEM_REC_DATE='2026-11-05'; $env:MEM_REC_SUMMARY='mem-variants-newip2-2026-11-05.json'; python fpga/mem/tests/record_variant.py nip_b_324_drvhigh nip_d_297 nip_e_360
