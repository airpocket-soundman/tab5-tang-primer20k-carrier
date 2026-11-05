#pragma once
// Experimental GFX-only extension. Include the common LINK codec first.
// MEM/NPU images may use the same opcodes in their own device namespace.
enum { R2_NOP=0x5e,R2_UPLOAD_BATCH=0x5f,R2_CAPS=0x60,R2_X0=0x61,R2_Y0=0x62,R2_X1=0x63,R2_Y1=0x64,
       R2_COLOR=0x65,R2_ADD_RG=0x66,R2_ADD_B=0x67,R2_KIND=0x68,
       R2_RESERVED0=0x69,R2_RESERVED1=0x6a,R2_DRAW=0x6b,
       R2_UPLOAD_WORD=0x6c,R2_UPLOAD_RESET=0x6d,R2_BATCH=0x6e,R2_FADE=0x6f,
       FIRE_CAPS=0x70,FIRE_X=0x71,FIRE_Y=0x72,FIRE_WIDTH=0x73,FIRE_HEIGHT=0x74,
       FIRE_FRAME_LO=0x75,FIRE_FRAME_HI=0x76,FIRE_LOAD=0x77,FIRE_DRAW=0x78 };
static inline bool raster2d_response(const uint8_t r[8],const uint8_t q[8]) {
    uint16_t c=link_crc16(r,6),v=(uint16_t)(r[4]|((uint16_t)r[5]<<8));
    unsigned op=q[1]&127;
    if(r[0]!=0x5a || r[1]!=0 || r[2]!=q[2] || r[3]!=2 ||
       r[6]!=(uint8_t)c || r[7]!=(uint8_t)(c>>8)) return false;
    if((op>=R2_X0 && op<=R2_RESERVED1)||(op>=FIRE_X && op<=FIRE_LOAD))
        return r[4]==q[4] && r[5]==q[5];
    switch(op) {
    case R2_CAPS:return q[4]==0 && q[5]==0 && v==0x011f;
    case FIRE_CAPS:return q[4]==0 && q[5]==0 && v==0x0101;
    case R2_DRAW:return !q[4] && !q[5] && v<=1024;
    case R2_NOP:case R2_UPLOAD_RESET:return !q[4] && !q[5] && !v;
    case R2_UPLOAD_WORD:return v>=1 && v<=1024;
    case R2_FADE:case FIRE_DRAW:return !q[4] && !q[5] && v==1024;
    case R2_UPLOAD_BATCH:case R2_BATCH:return q[4]>=1 && q[4]<=64 && q[5]==1 && r[4]==q[4] && r[5]==1;
    default:return false;
    }
}
