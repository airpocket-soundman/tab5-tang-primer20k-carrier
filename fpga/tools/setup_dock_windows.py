"""Set up workspace-local Dock tools on Windows; never accesses devices."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import venv

ROOT = Path(__file__).resolve().parents[1]
RELEASE = '2026-10-26'
ARCHIVE_NAME = 'oss-cad-suite-windows-x64-20261026.tgz'
URL = f'https://github.com/YosysHQ/oss-cad-suite-build/releases/download/{RELEASE}/{ARCHIVE_NAME}'
SHA256 = '8d0467cbd6d2c8fb41e99d3cd8a727109b8a3f08a9161c33a11ae6e731b998e3'
SIZE = 604483111
PACKAGES = ('yowasp-yosys==0.70.0.0.post1259', 'yowasp-nextpnr-himbaechel-gowin==0.11.1.0.post826', 'apycula==0.32')


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def verify_archive(path, size=None, expected=None):
    path=Path(path)
    size=SIZE if size is None else size
    expected=SHA256 if expected is None else expected
    if path.stat().st_size != size or sha256(path) != expected:
        raise ValueError(f'Archive size or SHA-256 mismatch: {path}')


def selected(name):
    p=PurePosixPath(name)
    if len(p.parts)<2 or p.parts[0]!='oss-cad-suite':
        return False
    rest=p.parts[1:]
    low=[s.lower() for s in rest]
    return (low[0]=='bin' and (low[-1] in ('openfpgaloader.exe','iverilog.exe','vvp.exe') or low[-1].endswith('.dll')) or
            low[0]=='lib' and low[-1].endswith('.dll') or
            len(low)>=2 and low[:2]==['lib','ivl'] or
            len(low)>=2 and low[:2]==['share','openfpgaloader'] or
            len(low)>=2 and low[:2]==['license','license.iverilog'] or
            len(low)==1 and ('license' in low[0] or 'copying' in low[0]))


def extract_loader(archive, destination):
    """Extract regular files only and reject traversal or duplicate paths."""
    destination=Path(destination).resolve()
    found=[]
    seen=set()
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            # Check the original name before normalizing or matching it.
            parts=PurePosixPath(member.name).parts
            if member.name.startswith('/') or '\\' in member.name or '..' in parts:
                raise ValueError(f'Unsafe archive path: {member.name}')
            if not selected(member.name) or member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f'Unsupported archive member: {member.name}')
            rel=PurePosixPath(*parts[1:])
            key=str(rel).casefold()
            if key in seen:
                raise ValueError(f'Duplicate archive member: {member.name}')
            seen.add(key)
            target=destination.joinpath(*rel.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.resolve().is_relative_to(destination):
                raise ValueError(f'Unsafe extraction target: {target}')
            src=tar.extractfile(member)
            if src is None:
                raise ValueError(f'Unable to read: {member.name}')
            # A temporary file in the same directory avoids leaving partial executables.
            temp=target.with_name(target.name+'.extracting')
            with src, temp.open('wb') as dst:
                while data:=src.read(1024*1024):
                    dst.write(data)
            os.replace(temp,target)
            if target.name.lower()=='openfpgaloader.exe':
                found.append(target)
    if len(found)!=1:
        raise ValueError(f'Expected exactly one openFPGALoader.exe; found {len(found)}')
    # OSS CAD Suite stores Windows runtime DLLs in lib/, outside the normal
    # search path of bin/openFPGALoader.exe. Copy the top-level DLLs beside
    # the executable so callers need no global or process PATH modifications.
    for dll in (destination/'lib').glob('*.dll'):
        target=found[0].parent/dll.name
        if target.exists() and sha256(target)!=sha256(dll):
            raise ValueError(f'Different DLL already exists in loader directory: {target}')
        if not target.exists():
            shutil.copyfile(dll,target)
    return found[0]


def acquire(archive):
    archive=Path(archive)
    if archive.exists():
        verify_archive(archive)
        return
    archive.parent.mkdir(parents=True,exist_ok=True)
    partial=archive.with_name(archive.name+'.download')
    print(f'Downloading {URL}',flush=True)
    with urllib.request.urlopen(URL,timeout=60) as src, partial.open('wb') as dst:
        while data:=src.read(1024*1024):
            dst.write(data)
    verify_archive(partial)
    os.replace(partial,archive)


def run(command, env=None):
    result=subprocess.run([str(c) for c in command],capture_output=True,text=True,errors='replace',env=env)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {command}\n{result.stdout}{result.stderr}')
    return (result.stdout+result.stderr).strip()


def setup_build_env(env):
    env=Path(env)
    python=env/'Scripts'/'python.exe'
    if not python.exists():
        if env.exists() and any(env.iterdir()):
            raise RuntimeError(f'Nonempty path is not a Windows Python venv: {env}')
        venv.EnvBuilder(with_pip=True).create(env)
    wanted=dict(item.split('==') for item in PACKAGES)
    code='import json,importlib.metadata as m; print(json.dumps({n:m.version(n) for n in '+repr(list(wanted))+'}))'
    try:
        current=json.loads(run([python,'-c',code]))
    except (RuntimeError,ValueError):
        current={}
    if current != wanted:
        run([python,'-m','pip','install',*PACKAGES])
        current=json.loads(run([python,'-c',code]))
    if current != wanted:
        raise RuntimeError(f'Installed package versions differ: {current}')
    executables={name:env/'Scripts'/exe for name,exe in {
        'yosys':'yowasp-yosys.exe','nextpnr':'yowasp-nextpnr-himbaechel-gowin.exe',
        'pack':'gowin_pack.exe'}.items()}
    for path in executables.values():
        if not path.is_file():
            raise RuntimeError(f'Missing build executable: {path}')
    entries={k:{'path':str(v.resolve()),'sha256':sha256(v)} for k,v in executables.items()}
    for name in ('yosys','nextpnr'):
        entries[name]['version']=run([executables[name],'--version'])
    # apycula 0.32's gowin_pack has no --version option.
    entries['pack']['version']='apycula '+current['apycula']+' (Python package metadata)'
    return {'python':str(python.resolve()),'packages':current,'executables':entries}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'build/toolchain'/ARCHIVE_NAME)
    parser.add_argument('--skip-build-env',action='store_true',help='Set up the loader only')
    args=parser.parse_args()
    manifest_path=ROOT/'build/windows-tools/manifest.json'
    manifest_path.parent.mkdir(parents=True,exist_ok=True)
    manifest={'status':'running','hardware_access':'none','system_changes':'none',
              'archive':{'path':str(args.archive.resolve()),'url':URL,'sha256':SHA256,'size':SIZE},
              'loader':{'status':'not_run'},'simulation':{'status':'not_run'},'build_env':{'status':'not_run'}}
    def save(): manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        if sys.platform!='win32':
            raise RuntimeError('Run this installer using native Windows Python')
        acquire(args.archive)
        loader=extract_loader(args.archive,ROOT/'build/windows-tools/oss-cad-suite')
        manifest['loader']={'status':'passed','path':str(loader), 'sha256':sha256(loader),
                            'version':run([loader,'--version'])}
        save()
        manifest['simulation']={'status':'running'}; save()
        child_env=os.environ.copy()
        child_env['PATH']=str(loader.parent)+os.pathsep+child_env.get('PATH','')
        simulator={}
        for name, version_flag in (('iverilog','-V'),('vvp','-V')):
            executable=loader.parent/(name+'.exe')
            if not executable.is_file():
                raise RuntimeError(f'Missing simulation executable: {executable}')
            simulator[name]={'path':str(executable), 'sha256':sha256(executable),
                             'version':run([executable,version_flag],env=child_env)}
        manifest['simulation']={'status':'passed',**simulator}; save()
        if not args.skip_build_env:
            manifest['build_env']={'status':'running'}; save()
            manifest['build_env']={'status':'passed',**setup_build_env(ROOT/'build/oss-env')}
        manifest['status']='passed'
        save()
        print(f"Loader: {loader}\nManifest: {manifest_path}")
        return 0
    except (OSError,ValueError,RuntimeError,tarfile.TarError,subprocess.SubprocessError) as exc:
        if manifest['build_env']['status']=='running': manifest['build_env']['status']='failed'
        elif manifest['simulation']['status']=='running': manifest['simulation']['status']='failed'
        elif manifest['loader']['status']=='not_run': manifest['loader']={'status':'failed'}
        manifest.update(status='failed',error=str(exc)); save()
        print(str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
