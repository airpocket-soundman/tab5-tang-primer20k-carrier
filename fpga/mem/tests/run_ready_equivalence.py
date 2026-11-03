from pathlib import Path
import subprocess,hashlib,json,os
r=Path(__file__).resolve().parents[3];b=r/'fpga/build/mem-tests';b.mkdir(parents=True,exist_ok=True)
s=subprocess.check_output(['git','show','08ef3a4:fpga/mem/rtl/mem_bist.v'],cwd=r)
assert b'assign app_cmd_en=active &&' in s
p=b/'mem_bist_legacy.v';p.write_bytes(s.replace(b'module mem_bist #',b'module mem_bist_legacy #',1))
tool=Path('D:/GitHub/tab5-tang-primer20k-carrier/fpga/build/windows-tools/oss-cad-suite/bin');env=os.environ.copy();env['PATH']=str(tool)+os.pathsep+str(tool.parent/'lib')+os.pathsep+env['PATH']
i=b/'ready-equivalence.vvp';subprocess.run([str(tool/'iverilog.exe'),'-g2012','-s','tb_ready_equivalence','-o',str(i),str(p),str(r/'fpga/mem/rtl/mem_bist.v'),str(r/'fpga/mem/tests/tb_ready_equivalence.v')],check=True,env=env)
x=subprocess.run([str(tool/'vvp.exe'),str(i)],check=True,capture_output=True,text=True,env=env);print(x.stdout)
(b/'ready_equivalence.json').write_text(json.dumps({'baseline_commit':'08ef3a4','baseline_source_sha256':hashlib.sha256(s).hexdigest(),'scope':'accepted events under ready-acceptance contract; no actual controller model','output':x.stdout},indent=2)+'\n')
