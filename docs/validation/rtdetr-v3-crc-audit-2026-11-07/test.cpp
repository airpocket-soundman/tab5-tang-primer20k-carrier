
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cassert>
#include "link_protocol.h"
#include "dma_tx_pack.hpp"
static uint8_t sequence=0;
static unsigned build(uint8_t op,const uint8_t*request,unsigned request_bytes,uint8_t*out){
    uint8_t wire[2061];link_make_request(wire,op,sequence++,uint8_t(request_bytes),uint8_t(request_bytes>>8));
    unsigned wire_bytes=8;
    if(request_bytes){std::memcpy(wire+8,request,request_bytes);const auto c=link_crc16_extend(link_crc16(wire,6),request,request_bytes);wire[8+request_bytes]=uint8_t(c);wire[9+request_bytes]=uint8_t(c>>8);wire_bytes+=request_bytes+2;}

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
