"""Build FPGA-local RV32IMC firmware with the installed ESP baremetal toolchain."""
from pathlib import Path
import argparse,subprocess,json,hashlib
from validate_elf import validate
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--toolchain',type=Path,default=Path('C:/Users/yamas/.espressif/tools/riscv32-esp-elf/esp-14.2.0_20251107/riscv32-esp-elf/bin'));p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--chain-smoke',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);out=a.output.resolve();cc=a.toolchain/'riscv32-esp-elf-g++.exe';v=ROOT/'vendor/host/main/inference';elf=out/'autonomous.elf'
src=([ROOT/'start.S',ROOT/('smoke_chain.cpp' if a.chain_smoke else 'smoke.cpp'),ROOT/'transport_mmio.cpp',ROOT/'syscalls.cpp'] if (a.smoke or a.chain_smoke) else [ROOT/'start.S',ROOT/'firmware.cpp',ROOT/'transport_mmio.cpp',ROOT/'syscalls.cpp',v/'rtdetr_graph.cpp',v/'rtdetr_fpga_backend.cpp']);flags=['-march=rv32imc_zicsr_zifencei','-mabi=ilp32','-std=c++17','-O2','-g','-ffp-contract=off','-fno-exceptions','-fno-rtti','-fno-threadsafe-statics','-fno-use-cxa-atexit','-ffunction-sections','-fdata-sections','-msmall-data-limit=0','-Wall','-Wextra','-Werror','-I'+str(ROOT),'-I'+str(v),'-I'+str(v.parent),'-nostartfiles','-Wl,--gc-sections','-Wl,-Map='+str(out/'autonomous.map'),'-T'+str(ROOT/'link.ld')]
commands=[[str(cc),*flags,*map(str,src),'-o',str(elf),'-lm','-lc','-lgcc'],[str(a.toolchain/'riscv32-esp-elf-objcopy.exe'),'-O','binary',str(elf),str(out/'autonomous.bin')],[str(a.toolchain/'riscv32-esp-elf-size.exe'),str(elf)],[str(a.toolchain/'riscv32-esp-elf-objdump.exe'),'-d',str(elf)]];logs=[]
for i,cmd in enumerate(commands):
 r=subprocess.run(cmd,capture_output=True,text=True);logs.append({'command':cmd,'returncode':r.returncode,'output':r.stdout+r.stderr});(out/'commands.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8')
 if r.returncode:print(r.stdout+r.stderr);raise SystemExit(r.returncode)
 if i==2:print(r.stdout)
 if i==3:(out/'autonomous.dis').write_text(r.stdout,encoding='utf-8')
bss_proof=validate(elf)
(out/'bss-proof.json').write_text(json.dumps(bss_proof,indent=2)+'\n',encoding='utf-8')
files=[*src,ROOT/'validate_elf.py',ROOT/'abi.h',ROOT/'platform.hpp',ROOT/'link.ld',ROOT/'build.py',*v.glob('*.hpp')]
(out/'result.json').write_text(json.dumps({'built':True,'ELF_BSS_startup_guard_passed':True,'smoke':a.smoke,'chain_smoke':a.chain_smoke,'hardware_access':False,'fpga_execution_claim':False,'entry':0x05000000,'isa':'RV32IMC soft-float (compiler zicsr/zifencei multilib; instruction audit required)','elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256((out/'autonomous.bin').read_bytes()).hexdigest(),'binary_bytes':(out/'autonomous.bin').stat().st_size,'sources_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}},indent=2)+'\n',encoding='utf-8')
