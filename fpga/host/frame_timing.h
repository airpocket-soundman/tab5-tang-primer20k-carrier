#pragma once
// GFX-only frame-timing extension. Include the common LINK codec first.
// Explicit capability negotiation is required; FRACTAL_INFO stays unchanged.
enum { FRAME_TIMING_CAPS=0x79,FRAME_TIMING_RESET=0x7a,
       FRAME_TIMING_LO=0x7b,FRAME_TIMING_HI=0x7c,
       FRAME_TIMING_CAP_VALUE=0x0120 };
static inline bool frame_timing_response(const uint8_t r[8],const uint8_t q[8]) {
    uint16_t c=link_crc16(r,6),v=(uint16_t)(r[4]|((uint16_t)r[5]<<8));
    unsigned op=q[1]&127;
    if(r[0]!=0x5a || r[1]!=0 || r[2]!=q[2] || r[3]!=2 ||
       r[6]!=(uint8_t)c || r[7]!=(uint8_t)(c>>8) || q[4]!=0 || q[5]!=0) return false;
    switch(op) {
    case FRAME_TIMING_CAPS:return v==FRAME_TIMING_CAP_VALUE;
    case FRAME_TIMING_RESET:return v==0;
    case FRAME_TIMING_LO:case FRAME_TIMING_HI:return true;
    default:return false;
    }
}
