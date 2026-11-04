/* MEMV1 host codec vs the independent Python reference model (fpga/mem/tests/memv1_model.py).
 * Input: the vector file written by `memv1_model.py --vectors` (one hex byte per line; records
 * lenQ(le16) lenR(le16) Q R). For every record the codec must (a) re-encode structurally valid RD/WR/CRC32
 * requests to exactly the model's bytes, (b) accept the model's response with memv1_validate_response and a
 * status equal to byte 1, (c) agree on CRC32 and range decisions. */
#define _CRT_SECURE_NO_WARNINGS 1
#include "../mem_v1.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures, checks;
#define CHECK(c) do{ checks++; if(!(c)){ failures++; printf("FAIL line %d: %s\n",__LINE__,#c);} }while(0)

static uint8_t vec[1<<18];
static size_t vlen;

int main(int argc, char **argv) {
    CHECK(memv1_crc32(0,(const uint8_t*)"123456789",9)==0xcbf43926u);
    {   uint8_t d[200]; for(int i=0;i<200;i++) d[i]=(uint8_t)(i*7+3);
        CHECK(memv1_crc32(memv1_crc32(0,d,100),d+100,100)==memv1_crc32(0,d,200)); }
    CHECK(memv1_range_valid(0,1) && memv1_range_valid(0x7fff000,256) && memv1_range_valid(0x7fffff0,1));
    CHECK(!memv1_range_valid(0x7fffff0,2) && !memv1_range_valid(0x8000000,1) && !memv1_range_valid(1,1) &&
          !memv1_range_valid(0,0) && !memv1_range_valid(0,257) && !memv1_range_valid(0xfffffff0u,2));
    CHECK(link_crc16((const uint8_t*)"123456789",9)==0x29b1);
    if(argc<2) { printf("usage: test_mem_v1 vectors.hex\n"); return 2; }
    FILE *f=fopen(argv[1],"r");
    if(!f) { printf("cannot open %s\n",argv[1]); return 2; }
    unsigned v;
    while(vlen<sizeof vec && fscanf(f,"%x",&v)==1) vec[vlen++]=(uint8_t)v;
    fclose(f);
    size_t p=0; int records=0, encoded=0, validated=0;
    static uint8_t buf[5000];
    while(p+4<=vlen) {
        size_t lq=vec[p]|((size_t)vec[p+1]<<8), lr=vec[p+2]|((size_t)vec[p+3]<<8);
        if(!lq) break;
        const uint8_t *q=vec+p+4, *r=q+lq;
        p+=4+lq+lr; records++;
        unsigned op=q[1]&0x7f; bool tagged=(q[1]&0x80)!=0;
        size_t pre=0;
        if(lr>=8 && r[0]==0xc3) { /* tagged reply prefix */ pre=8; CHECK(tagged); }
        else CHECK(!tagged || r[0]==0xc3 || r[1]==MEMV1_ST_FORMAT);
        if(pre) for(int i=0;i<8;i++) CHECK(r[i]==0xc3);
        const uint8_t *rr=r+pre; size_t rl=lr-pre;
        bool q_header_ok=lq>=8 && q[0]==0xa5 && q[3]==2 && link_crc16(q,6)==(uint16_t)(q[6]|(q[7]<<8));
        if(q_header_ok && (op==MEMV1_RD||op==MEMV1_WR||op==MEMV1_CRC32) && lq>=18) {
            uint32_t beats=q[4]|((uint32_t)q[5]<<8), addr=memv1_get32(q+8), arg=memv1_get32(q+12);
            size_t n=0;
            /* only re-encode requests whose trailer is intact (corrupted ones exercise the device, not the encoder) */
            uint16_t tc=link_crc16_extend(link_crc16(q,6),q+8,(unsigned)(lq-10));
            if(tc==(uint16_t)(q[lq-2]|(q[lq-1]<<8)) && beats>=1 && beats<=256) {
                if(op==MEMV1_RD && arg==0) n=memv1_encode_rd(buf,sizeof buf,q[2],addr,beats,tagged);
                else if(op==MEMV1_CRC32) n=memv1_encode_crc32(buf,sizeof buf,q[2],addr,beats,arg,tagged);
                else if(op==MEMV1_WR && lq==18+beats*16 && memv1_crc32(0,q+16,beats*16)==arg)
                    n=memv1_encode_wr(buf,sizeof buf,q[2],addr,beats,q+16,tagged);
                if(n) { CHECK(n==lq && memcmp(buf,q,lq)==0); encoded++; }
            }
        }
        if(q_header_ok && op>=0x50 && op<=0x5c) { CHECK(rr[1]==0); /* legacy MEM diagnostic ABI: mem_protocol.h */ }
        else if(q_header_ok) {
            int st=memv1_validate_response(rr,rl,q);
            /* a request with a bad extended trailer still gets a well-formed 8-byte error reply */
            if(st!=rr[1]) printf("record %d op %02x q4 %u status %d reply status %u r45 %02x%02x%c",records-1,q[1],q[4],st,rr[1],rr[4],rr[5],10);
            CHECK(st==rr[1]);
            if(st==rr[1]) validated++;
            if(rr[1]==0 && op==MEMV1_RD) { uint32_t beats=q[4]|((uint32_t)q[5]<<8);
                CHECK(rl==10+beats*16); }
            if(rr[1]==0 && op==MEMV1_CRC32 && lq>=18) {
                uint32_t beats=q[4]|((uint32_t)q[5]<<8); (void)beats;
                CHECK(rl==14); }
            if(rr[1]==0 && (op==MEMV1_RD||op==MEMV1_WR||op==MEMV1_CRC32)) CHECK(memv1_range_valid(memv1_get32(q+8),q[4]|((uint32_t)q[5]<<8)));
        } else {
            /* header CRC corrupted: device answers status FORMAT; the codec rejects it as a response to q */
            CHECK(rr[1]==MEMV1_ST_FORMAT);
        }
    }
    printf("%s mem_v1 %d checks, %d records, %d re-encoded, %d validated\n",failures?"FAIL":"PASS",checks,records,encoded,validated);
    return failures?1:0;
}
