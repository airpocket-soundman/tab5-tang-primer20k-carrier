from pathlib import Path
import subprocess,json,hashlib,binascii,struct,os
r=Path.cwd();o=r/'build/npu-v3-crc-fixture';s=(r/'main/dock_gpu.cpp').read_text();start=s.index('    uint8_t wire[2061],header[8];',s.index('bool conv_exchange_bounded('));end=s.index('    auto wait_long=',start);body=s[start:end].replace('wire[2061],header[8]','wire[2061]')
code=r'''
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cassert>
#include "link_protocol.h"
#include "dma_tx_pack.hpp"
static uint8_t sequence=0;
static unsigned build(uint8_t op,const uint8_t*request,unsigned request_bytes,uint8_t*out){
BODY
 std::memcpy(out,wire,wire_bytes);return wire_bytes;
}
int main(int argc,char**argv){assert(argc==2);FILE*f=std::fopen(argv[1],"wb");assert(f);
 const unsigned sizes[]={2032,2032,32,16,16,16,16,256,128,256,32};
 alignas(128)uint8_t payload[2040],frame[2061],raw[8704];uint32_t rng=0x4e24c0de;unsigned count=0,dma=0,gpio=0;uint64_t bytes=0;
 for(unsigned cycle=0;cycle<24000;cycle++)for(unsigned size:sizes){
  const uint32_t addr=0x04000000+((count*16)&0xffff0);for(unsigned j=0;j<4;j++)payload[j]=uint8_t(addr>>(j*8));payload[4]=uint8_t(size);payload[5]=uint8_t(size>>8);payload[6]=payload[7]=0;
  for(unsigned j=0;j<size;j++){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;payload[8+j]=cycle%5==0?0:cycle%5==1?0xff:cycle%5==2?0xa5:uint8_t(rng);}
  unsigned n=build(0x71,payload,size+8,frame);assert(n==size+18);std::memset(raw,0xcd,sizeof raw);auto*packed=raw+128;
  assert(dma_tx_pack::pack(frame,n,packed,dma_tx_pack::mem_capacity,dma_tx_pack::mem_max_bytes));
  for(unsigned j=0;j<128;j++)assert(raw[j]==0xcd);
  for(unsigned j=0;j<n;j++)assert(packed[j*2]==frame[j]&&packed[j*2+1]==0);
  for(unsigned j=n*2;j<dma_tx_pack::mem_capacity;j++)assert(packed[j]==0xcd);
  const bool isdma=size+8>=256;if(isdma)++dma;else++gpio;
  uint16_t header[2]={uint16_t(isdma),uint16_t(n)};assert(std::fwrite(header,4,1,f)==1&&std::fwrite(frame,n,1,f)==1);count++;bytes+=n;
 }
 std::fclose(f);std::printf("PASS actualframer+bytepack frames=%u DMAselected=%u GPIOselected=%u wirebytes=%llu seqwraps=%u guards/trailer/allbytes nohardware\n",count,dma,gpio,(unsigned long long)bytes,count/256);
}
'''.replace('BODY',body);(o/'test.cpp').write_text(code)
cc='D:/GitHub/airpocket-soundman/tab5-fpga-gpu-demo/build/test-tools/ziglang/zig.exe';cmd=[cc,'c++','-std=c++17','-O2','-UNDEBUG','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(r/'main'),'-I'+str(r/'bringup/tab5/main'),str(o/'test.cpp'),'-o',str(o/'test.exe')];logs=[]
for c in [cmd,[str(o/'test.exe'),str(o/'frames.bin')]]:
 p=subprocess.run(c,capture_output=True,text=True);logs.append({'command':c,'returncode':p.returncode,'output':p.stdout+p.stderr});print(p.stdout+p.stderr);assert p.returncode==0
frames=dmas=wire=0
with (o/'frames.bin').open('rb')as f:
 while True:
  tag=f.read(4)
  if not tag:break
  dma,n=struct.unpack('<HH',tag);data=f.read(n);assert len(data)==n
  assert data[:2]==b'\xa5\x71' and data[2]==frames%256 and data[3]==2
  length=int.from_bytes(data[4:6],'little');assert length+10==n
  assert binascii.crc_hqx(data[:6],0xffff)==int.from_bytes(data[6:8],'little')
  assert binascii.crc_hqx(data[8:-2],binascii.crc_hqx(data[:6],0xffff))==int.from_bytes(data[-2:],'little')
  count=int.from_bytes(data[12:14],'little');assert count+8==length and count%16==0 and data[14:16]==b'\0\0' and bool(dma)==(length>=256)
  frames+=1;dmas+=dma;wire+=n
assert frames==264000 and dmas==96000 and wire>113000000
result={'passed':True,'hardware_access':False,'frames':frames,'DMA_selected_frames':dmas,'GPIO_selected_frames':frames-dmas,'wirebytes':wire,'oracle':'Independent Python binascii.crc_hqx; actual C++ frame-builder extracted from conv_exchange_bounded and actual bytepacker; fake selection only','scope_limits':['No actual PARLIO/GDMA/FIFO/GPIO matrix timing or electrical validation','No reproduction of physical CRCfailure; only software frame/packing contamination ruled out for fixture'], 'source_sha256':{n:hashlib.sha256((r/n).read_bytes()).hexdigest()for n in ['main/dock_gpu.cpp','main/dock_dma_tx.cpp','main/dma_tx_pack.hpp','bringup/tab5/main/link_protocol.h']},'commands':logs};(o/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS independentCRC',frames,wire)
