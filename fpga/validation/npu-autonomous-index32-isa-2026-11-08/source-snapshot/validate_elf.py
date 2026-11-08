"""Check actual ELF section ownership of startup BSS symbols, not linker dot guesses."""
from pathlib import Path
import struct,sys,json

def validate(path):
 b=Path(path).read_bytes();h=struct.unpack_from('<16sHHIIIIIHHHHHH',b);assert h[0][:5]==b'\x7fELF\x01'and h[0][5]==1
 sections=[struct.unpack_from('<10I',b,h[6]+i*h[11])for i in range(h[12])];symbols={}
 for s in sections:
  if s[1]!=2:continue
  names=sections[s[6]];text=b[names[4]:names[4]+names[5]]
  for off in range(s[4],s[4]+s[5],s[9]):
   name,value,size,info,other,sec=struct.unpack_from('<IIIBBH',b,off);end=text.find(b'\0',name);symbols[text[name:end].decode()]=(value,size,sec)
 start=symbols['__bss_start'][0];end=symbols['__bss_end'][0];assert start%16==0 and start<end
 allocated_bss=[]
 for i,s in enumerate(sections):
  if s[1]==8 and s[2]&2 and s[5]:
   assert start<=s[3]and s[3]+s[5]<=end,(hex(start),hex(end),hex(s[3]),s[5]);allocated_bss.append({'section':i,'address':s[3],'bytes':s[5]})
 assert allocated_bss and symbols['__firmware_end'][0]==end and end<=0x05800000
 assert h[4]==0x05000000 and symbols['_start'][0]==h[4]
 for name,(address,size,sec)in symbols.items():
  if sec<len(sections)and sections[sec][1]==8 and size:assert start<=address and address+size<=end,name
 return {'passed':True,'entry':h[4],'bss_start':start,'bss_end':end,'bss_bytes':end-start,'allocated_nobits':allocated_bss,'firmware_end':end,'hardware_access':False}
if __name__=='__main__':print(json.dumps(validate(sys.argv[1]),indent=2))
