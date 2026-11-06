"""Offline exact old49/new16 depth miter; requires existing Icarus only."""
import argparse,hashlib,json,random,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE='75c641571f8e04fdaf42cacce7b4d2a2ef765b36'
p=argparse.ArgumentParser();p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');a=p.parse_args()
out=ROOT/'fpga/build/depth16-review';out.mkdir(parents=True,exist_ok=True)
# Frozen original from BASE:fpga/gfx/rtl/triangle_depth.v. Only the module
# identifier is changed in the fixture; no Git history is needed at runtime.
reference=ROOT/'fpga/gfx/tests/fixtures/triangle_depth49_reference.v'
fixture=reference.read_bytes()
REFERENCE_ORIGINAL_SHA256='de970c1412f827a1bac67d840b7f0345128ad669a67cd3d3e66029c2b5ffe06f'
REFERENCE_FIXTURE_SHA256='2d78fc0675264a754b2d2a3310f21984dea916607310d9c9d235b1d4087fd93c'
old=fixture.replace(b'module triangle_depth49_reference (',b'module triangle_depth (')
if hashlib.sha256(fixture).hexdigest()!=REFERENCE_FIXTURE_SHA256 or hashlib.sha256(old).hexdigest()!=REFERENCE_ORIGINAL_SHA256:
 raise RuntimeError('Frozen old49 reference fixture SHA256 mismatch')
r=random.Random(20261106);rows=[];maximum=8589672450
for n in range(6000):
 area=r.choice([1,2,3,65535,65536,2**32-1,2**32,maximum,r.randrange(1,maximum+1)])
 wa=r.randrange(area+1);wb=r.randrange(area-wa+1);wc=area-wa-wb
 za,zb,zc=[r.choice([0,1,32767,32768,65534,65535,r.randrange(65536)])for _ in range(3)]
 oldz=r.choice([0,65535,r.randrange(65536)])
 covered=n%11!=0
 if n in (1,2,3):
  area=maximum if n!=2 else 1;wa=area;wb=wc=0;za=65535 if n!=3 else 0;zb=zc=0;oldz=65534 if n!=3 else 0;covered=True
 if n%19==0:area=r.choice([0,-1,maximum+1,2**63-1,-2**63])
 if n%23==0:wa=-1
 if n%29==0:wc+=1
 valid=0<area<=maximum and min(wa,wb,wc)>=0 and wa+wb+wc==area
 expected=(int(not valid)<<16)
 if valid and covered:
  numerator=wa*za+wb*zb+wc*zc
  assert numerator<area*65536 and numerator<2**49 and (numerator>>16)<area
  z=numerator//area
  if n%7==0:oldz=z  # strict-depth equality must fail, never >=.
  expected=z | (int(z>oldz)<<17)
 fields=[(area,64),(wa,64),(wb,64),(wc,64),(za,16),(zb,16),(zc,16),(oldz,16),(int(covered),64)]
 packed=0
 for v,bits in fields:packed=(packed<<bits)|(v&((1<<bits)-1))
 rows.append((packed,expected))
(out/'miter-inputs.mem').write_text(''.join(f'{x:096x}\n'for x,_ in rows))
(out/'miter-expected.mem').write_text(''.join(f'{x:016x}\n'for _,x in rows))
rtl=ROOT/'fpga/gfx/rtl/triangle_depth.v';tb=ROOT/'fpga/gfx/tests/tb_triangle_depth16_miter.v'
cmd=[a.iverilog,'-g2012','-Wall','-s','tb_triangle_depth16_miter','-o',str(out/'miter.vvp'),str(rtl),str(reference),str(tb)]
c=subprocess.run(cmd,capture_output=True,text=True);(out/'compile.log').write_text(c.stdout+c.stderr);c.check_returncode()
v=subprocess.run([a.vvp,str(out/'miter.vvp')],cwd=out,capture_output=True,text=True);(out/'simulation.log').write_text(v.stdout+v.stderr)
manifest=dict(passed=v.returncode==0,reference_commit=BASE,seed=20261106,cases=len(rows),source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in [rtl,tb,Path(__file__)]},reference_original_sha256=REFERENCE_ORIGINAL_SHA256,reference_fixture_sha256=hashlib.sha256(fixture).hexdigest(),reference_fixture=str(reference.relative_to(ROOT)),stdout=v.stdout,returncode=v.returncode)
(out/'result.json').write_text(json.dumps(manifest,indent=2));print(v.stdout);v.check_returncode()
