"""Prepare immutable DDR upload segments. No serial/JTAG/device access."""
from pathlib import Path
import argparse,hashlib,json,struct,zlib
MAGIC=0x31545041;CAPACITY=0x05000000
SOURCE='a4e1d5c112b1873d701b690ddf92d2e6aa822a2e759443ee7f7f27916b21b555'
def sha(b):return hashlib.sha256(b).hexdigest()
def page(a):return(a+4095)&~4095

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--firmware',type=Path,required=True);p.add_argument('--model',type=Path);p.add_argument('--rgb-ppm',type=Path);p.add_argument('--token',type=lambda s:int(s,0),required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('fresh output required')
 if not 0<a.token<=0xffffffff:p.error('nonzero uint32 token required')
 fw=a.firmware.read_bytes();assert fw and len(fw)<=0x800000
 words=[MAGIC,1,1,0,a.token,0,0,0,0,0,0,0]+[0]*16;segments=[('firmware.bin',0x05000000,fw)];info={'schema':1,'hardware_access':False,'smoke':a.smoke,'token':a.token,'entry':0x05000000,'graph_capacity':CAPACITY,'firmware_sha256':sha(fw),'numerical_qualification':False}
 if not a.smoke:
  assert a.model and a.rgb_ppm
  raw=a.model.read_bytes();assert len(raw)>=128
  h=struct.unpack('<16I',raw[:64]);assert raw[:4]==b'RQG2'and h[1]==2 and raw[64:96].hex()==SOURCE
  metadata,payload,arena=h[6],h[7],h[8];assert len(raw)==metadata+payload and 128<=metadata<=0x100000
  meta=bytearray(raw[:metadata]);meta[36:40]=b'\0'*4;assert zlib.crc32(meta)==h[9]and zlib.crc32(raw[metadata:])==h[10]
  cb=65536;ab=page(cb+payload);scratch=page(ab+arena);assert scratch+3284992<=CAPACITY
  # Provisioned input files are strict P6 RGB640; no numeric conversion here.
  ppm=a.rgb_ppm.read_bytes();prefix=b'P6\n640 640\n255\n';assert ppm.startswith(prefix)and len(ppm)==len(prefix)+640*640*3;rgb=ppm[len(prefix):]
  words[5:11]=[0x05800000,metadata,cb,ab,scratch,CAPACITY-scratch]
  segments += [('metadata.rqg',0x05800000,raw[:metadata]),('constants.bin',cb,raw[metadata:]),('input.rgb',0x05900000,rgb)]
  info.update(model_source_sha256=SOURCE,model_package_sha256=sha(raw),metadata_bytes=metadata,payload_bytes=payload,arena_bytes=arena,scratch_base=scratch,known_model_peak_end=scratch+3284992,input_rgb_sha256=sha(rgb),input_conversion='RGB8 to BGRFLOAT0..255 performed inside FPGA CPU')
 mailbox=struct.pack('<28I',*words)+bytes(96);assert len(mailbox)==208;segments += [('mailbox.bin',0x07ff0000,mailbox)]
 ranges=sorted((addr,addr+len(b),name)for name,addr,b in segments)
 assert all(e<=0x08000000 for _,e,_ in ranges)and all(ranges[i][1]<=ranges[i+1][0]for i in range(len(ranges)-1))
 a.output.mkdir(parents=True);info['segments']=[]
 for name,addr,b in segments:
  (a.output/name).write_bytes(b);info['segments'].append({'file':name,'address':addr,'bytes':len(b),'sha256':sha(b)})
 (a.output/'manifest.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8');print(json.dumps({'prepared':True,'segments':len(segments),'bytes':sum(len(b)for _,_,b in segments),'no_device_access':True}))
if __name__=='__main__':main()
