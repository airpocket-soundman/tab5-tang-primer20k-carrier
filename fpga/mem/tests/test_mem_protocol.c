#include "../../host/mem_protocol.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define CHECK(x) do{++checks;if(!(x)){fprintf(stderr,"failed line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static void response(uint8_t r[8],const uint8_t q[8],unsigned status,unsigned value){
 r[0]=0x5a;r[1]=(uint8_t)status;r[2]=q[2];r[3]=2;r[4]=(uint8_t)value;r[5]=(uint8_t)(value>>8);
 uint16_t c=link_crc16(r,6);r[6]=(uint8_t)c;r[7]=(uint8_t)(c>>8);
}
int main(void){
 uint8_t q[8],r[8],copy[8];unsigned i,status;
 link_make_request(q,MEM_CAPS,255,0,0);response(r,q,0,MEM_FORMAT);CHECK(mem_validate_response(r,q));
 response(r,q,0,0x0140);CHECK(!mem_validate_response(r,q));
 for(i=MEM_BASE_LO;i<=MEM_SEED_HI;++i){
  link_make_request(q,(uint8_t)(i|0x80),0,0xcd,0xab);response(r,q,0,0xabcd);CHECK(mem_validate_response(r,q));
  response(r,q,0,0xabce);CHECK(!mem_validate_response(r,q));
 }
 for(i=0;i<256;++i){
  link_make_request(q,MEM_WORD,(uint8_t)i,31,0);response(r,q,0,0xcafe);CHECK(mem_validate_response(r,q));
  memcpy(copy,q,8);copy[2]^=1;uint16_t c=link_crc16(copy,6);copy[6]=(uint8_t)c;copy[7]=(uint8_t)(c>>8);
  CHECK(!mem_validate_response(r,copy));
 }
 for(i=0;i<8;++i){memcpy(copy,r,8);copy[i]^=1;CHECK(!mem_validate_response(copy,q));}
 for(status=1;status<=5;++status){response(r,q,status,0);CHECK(mem_validate_response(r,q));response(r,q,status,1);CHECK(!mem_validate_response(r,q));}
 response(r,q,6,0);CHECK(!mem_validate_response(r,q));
 link_make_request(q,MEM_WORD,0,32,0);response(r,q,0,0);CHECK(!mem_validate_response(r,q));
 link_make_request(q,MEM_WORD,0,0,1);response(r,q,0,0);CHECK(!mem_validate_response(r,q));
 const unsigned values[8]={0x014d,2048,0x0d0a,0x0310,324,81,0x0389,65535};
 for(i=0;i<8;++i){link_make_request(q,MEM_SYSQUERY,0,(uint8_t)i,0);response(r,q,0,values[i]);CHECK(mem_validate_response(r,q));}
 link_make_request(q,MEM_SYSQUERY,0,6,0);response(r,q,0,0x8000);CHECK(!mem_validate_response(r,q));
 link_make_request(q,MEM_SYSQUERY,0,8,0);response(r,q,0,0);CHECK(!mem_validate_response(r,q));response(r,q,3,0);CHECK(mem_validate_response(r,q));
 response(r,q,0,MEM_DIAG_FORMAT);CHECK(mem_validate_response(r,q));
 for(i=9;i<=19;++i){link_make_request(q,MEM_SYSQUERY,0,(uint8_t)i,0);response(r,q,0,0xcafe);CHECK(mem_validate_response(r,q));}
 link_make_request(q,MEM_SYSQUERY,0,20,0);response(r,q,0,0);CHECK(!mem_validate_response(r,q));
 link_make_request(q,MEM_CAPS,0,0,0);response(r,q,0,MEM_FORMAT);q[1]^=0x80;CHECK(!mem_validate_response(r,q));
 CHECK(mem_range_valid(0,8388608));CHECK(mem_range_valid(0x7fffff0,1));CHECK(!mem_range_valid(0x7fffff0,2));
 CHECK(!mem_range_valid(1,1));CHECK(!mem_range_valid(0,0));CHECK(!mem_range_valid(0,0xffffffffu));CHECK(!mem_range_valid(0xfffffff0u,1));
 uint16_t w[32]={0};w[0]=5;w[1]=0x0500;w[2]=0xffff;w[3]=0xffff;w[4]=34;w[26]=123;w[28]=0x100;w[30]=81;w[31]=MEM_FORMAT;
 CHECK(mem_words64(w+26)==((UINT64_C(1)<<40)+123));
 CHECK(mem_snapshot_done_pass(w,0xffffffffu,17,65535,65535,0x389));
 CHECK(mem_snapshot_done_pass(w,0xffffffffu,17,0,0,0x389));
 CHECK(!mem_snapshot_done_pass(w,0xffffffffu,17,65535,0,0x389));
 CHECK(!mem_snapshot_done_pass(w,0,17,1,1,0x389));
 CHECK(!mem_snapshot_done_pass(w,0xffffffffu,18,1,1,0x389));
 for(i=0;i<16;++i){
  unsigned bit=1u<<i;
  if(0x389&bit)CHECK(!mem_snapshot_done_pass(w,0xffffffffu,17,1,1,(uint16_t)(0x389^bit)));
  else CHECK(!mem_snapshot_done_pass(w,0xffffffffu,17,1,1,(uint16_t)(0x389|bit)));
 }
 w[6]=1;CHECK(!mem_snapshot_done_pass(w,0xffffffffu,17,1,1,0x389));w[6]=0;
 w[1]=0x0506;CHECK(!mem_snapshot_done_pass(w,0xffffffffu,17,1,1,0x389));w[1]=0x0500;
 w[0]|=0x20;CHECK(!mem_snapshot_done_pass(w,0xffffffffu,17,1,1,0x389));
 printf("PASS mem_protocol %u checks: CRC/seq/caps/args, range overflow, stale/reset flags, generation,64bitcycles\n",checks);
 return 0;
}
