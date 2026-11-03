#pragma once
#include <stdbool.h>
#include <stdint.h>

// dock-gfx-v0: experimental extension, independent of the future DDR3 v1 ABI.
enum { LINK_ID=1, LINK_ECHO=2, LINK_INVERT=3,
       GFX_INFO=0x10, GFX_COLOR=0x11, GFX_CLEAR=0x12, GFX_PIXEL=0x13,
       GFX_READ=0x14, GFX_ORIGIN=0x15, GFX_RECT=0x16,
       TRI_INFO=0x20, TRI_AX=0x21, TRI_AY=0x22, TRI_BX=0x23, TRI_BY=0x24,
       TRI_CX=0x25, TRI_CY=0x26, TRI_ZA=0x27, TRI_ZB=0x28, TRI_ZC=0x29,
       TRI_COLOR=0x2a, TRI_CLEAR=0x2b, TRI_DRAW=0x2c, TRI_READ=0x2d, TRI_DEPTH=0x2e,
       TRI_ROW=0x2f };
enum { TRI_ROW_WORDS=32, TRI_ROW_RESPONSE_BYTES=74 };
static inline uint16_t link_crc16_extend(uint16_t c, const uint8_t *p, unsigned n) {
    while(n--) { c^=(uint16_t)*p++ << 8; for(int i=0;i<8;i++) c=(c&0x8000)?(c<<1)^0x1021:c<<1; }
    return c;
}
static inline uint16_t link_crc16(const uint8_t *p, unsigned n) {
    return link_crc16_extend(0xffff,p,n);
}
static inline void link_make_request(uint8_t q[8], uint8_t op, uint8_t seq, uint8_t a, uint8_t b) {
    q[0]=0xa5; q[1]=op; q[2]=seq; q[3]=2; q[4]=a; q[5]=b;
    uint16_t c=link_crc16(q,6); q[6]=(uint8_t)c; q[7]=(uint8_t)(c>>8);
}
static inline bool link_validate_response(const uint8_t r[8], const uint8_t q[8]) {
    uint16_t c=link_crc16(r,6);
    if(r[0]!=0x5a || r[1]!=0 || r[2]!=q[2] || r[3]!=2 || r[6]!=(uint8_t)c || r[7]!=(uint8_t)(c>>8)) return false;
    switch(q[1]) {
        case LINK_ID: return r[4]=='T' && r[5]=='P';
        case LINK_ECHO: return r[4]==q[4] && r[5]==q[5];
        case LINK_INVERT: return r[4]==(uint8_t)(q[4]^255) && r[5]==(uint8_t)(q[5]^255);
        case GFX_INFO: case TRI_INFO: return r[4]==32 && r[5]==32;
        case TRI_AX: case TRI_AY: case TRI_BX: case TRI_BY: case TRI_CX: case TRI_CY:
        case TRI_ZA: case TRI_ZB: case TRI_ZC: case TRI_COLOR:
            return r[4]==q[4] && r[5]==q[5];
        case TRI_CLEAR: return r[4]==0 && r[5]==0;
        case TRI_DRAW: return ((uint16_t)r[4] | (uint16_t)r[5]<<8)<=1024;
        case TRI_READ: case TRI_DEPTH: return true; // Compare complete color/depth on host.
        case TRI_ROW: return q[4]<32 && q[5]<2 && r[4]==q[4] && r[5]==q[5];
        case GFX_COLOR: case GFX_PIXEL: case GFX_ORIGIN: case GFX_RECT:
            return r[4]==q[4] && r[5]==q[5];
        case GFX_CLEAR: return r[4]==0 && r[5]==0;
        case GFX_READ: return true; // Caller must compare against expected image.
        default: return false;
    }
}
// TRI_ROW success only: 8-byte header + 64-byte row + 2-byte bound CRC.
// A nonzero status is a normal eight-byte error, never a 74-byte success.
static inline bool link_validate_row_response(const uint8_t r[74], const uint8_t q[8]) {
    if(q[1]!=TRI_ROW || !link_validate_response(r,q)) return false;
    uint16_t c=link_crc16_extend(link_crc16(r,6),r+8,64);
    return r[72]==(uint8_t)c && r[73]==(uint8_t)(c>>8);
}
