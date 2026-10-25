from pathlib import Path
import hashlib,json,urllib.request,zipfile,io
H=Path(__file__).resolve().parent
sources={
 'TPS5430_unencrypted.zip':'https://www.ti.com/lit/zip/SLVMCU8',
 'TPS5430_TINA.TSM':'https://www.ti.com/lit/tsm/SLVM095',
 'TPS5430_EVM_SLVU157A.pdf':'https://www.ti.com/lit/pdf/SLVU157',
 'XC6206.pdf':'https://product.torexsemi.com/system/files/series/xc6206.pdf',
}
report=[]
for filename,url in sources.items():
 p=H/'reference'/filename
 try:
  data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=45).read()
  if filename.endswith('.pdf'):assert data.startswith(b'%PDF')
  p.write_bytes(data)
  if filename.endswith('.zip'):
   z=zipfile.ZipFile(io.BytesIO(data))
   for name in z.namelist():
    if name.endswith('/'):continue
    out=H/'models'/Path(name).name;out.write_bytes(z.read(name))
  report.append(dict(filename=filename,url=url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),status='downloaded'))
 except Exception as e:report.append(dict(filename=filename,url=url,status='failed',reason=str(e)))
(H/'reference/sources.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=1))
