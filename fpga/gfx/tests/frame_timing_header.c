#include "link_protocol.h"
#include "frame_timing.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void reply(uint8_t *r,const uint8_t *q,uint8_t status,uint16_t value) {
    r[0]=0x5a;r[1]=status;r[2]=q[2];r[3]=2;r[4]=(uint8_t)value;r[5]=(uint8_t)(value>>8);
    uint16_t c=link_crc16(r,6);r[6]=(uint8_t)c;r[7]=(uint8_t)(c>>8);
}
int main(void) {
    uint8_t q[8],r[8];
    for(unsigned tag=0;tag<2;tag++)for(unsigned op=FRAME_TIMING_CAPS;op<=FRAME_TIMING_HI;op++) {
        link_make_request(q,(uint8_t)(op|(tag?128:0)),73,0,0);
        uint16_t value=op==FRAME_TIMING_CAPS?FRAME_TIMING_CAP_VALUE:op==FRAME_TIMING_RESET?0:0xffff;
        reply(r,q,0,value);assert(frame_timing_response(r,q));
        r[2]^=1;assert(!frame_timing_response(r,q));r[2]^=1;
        r[7]^=1;assert(!frame_timing_response(r,q));r[7]^=1;
        reply(r,q,2,0);assert(!frame_timing_response(r,q));
        reply(r,q,5,0);assert(!frame_timing_response(r,q));
        reply(r,q,0,value);q[4]=1;assert(!frame_timing_response(r,q));q[4]=0;
        q[5]=1;assert(!frame_timing_response(r,q));q[5]=0;
    }
    link_make_request(q,FRAME_TIMING_CAPS,1,0,0);reply(r,q,0,0x011f);assert(!frame_timing_response(r,q));
    link_make_request(q,FRAME_TIMING_RESET,2,0,0);reply(r,q,0,1);assert(!frame_timing_response(r,q));
    link_make_request(q,FRAME_TIMING_LO,3,0,0);reply(r,q,0,0);assert(frame_timing_response(r,q));
    link_make_request(q,FRAME_TIMING_HI,4,0,0);reply(r,q,0,0);assert(frame_timing_response(r,q));
    link_make_request(q,0x78,5,0,0);reply(r,q,0,0);assert(!frame_timing_response(r,q));
    puts("FRAME TIMING header PASS: tagged/plain, caps/ack, zero/allones halves, status, sequence, CRC, args, unknown");
    return 0;
}
