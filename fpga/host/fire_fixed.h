#pragma once
#include <stdbool.h>
#include <stdint.h>

/* Fire integer_g0 v1: Q8 smooth value noise, 2/4/6 octaves. This is a
 * separate numerical contract from the preserved legacy floating-point fire.
 * Coordinates normalize with floor(Q20 reciprocals); animation repeats at
 * frame65536. All hash operations explicitly wrap at16 bits. */
static inline bool fire_fixed_valid(unsigned width,unsigned height,unsigned load) {
    return load<3 && ((width==640 && height==360) ||
           (width==320 && height==180) || (width==160 && height==96));
}
static inline unsigned fire_fixed_smooth(unsigned f) {
    return (f*f*(768u-2u*f))>>16;
}
static inline unsigned fire_fixed_hash(int32_t x,int32_t y,unsigned octave) {
    uint16_t v=(uint16_t)((uint32_t)(uint16_t)x*1973u+
        (uint32_t)(uint16_t)y*9277u+(17u+octave)*26699u);
    v=(uint16_t)((uint32_t)(v^(v>>7))*25173u);
    return (v^(v>>8))&255u;
}
static inline int32_t fire_fixed_floor8(int32_t x) {
    return x>=0?x/256:-((-x+255)/256);
}
static inline unsigned fire_fixed_clamp(int value) {
    return value<0?0u:value>256?256u:(unsigned)value;
}
static inline uint16_t fire_fixed_pixel(unsigned x,unsigned y,unsigned width,
                                      unsigned height,uint32_t frame,unsigned load) {
    if(!fire_fixed_valid(width,height,load) || x>=width || y>=height) return 0;
    const unsigned iw=width==640?1638u:width==320?3276u:6553u;
    const unsigned ih=height==360?2912u:height==180?5825u:10922u;
    const int nx=(int)((x*iw)>>11)-256;
    const unsigned h=((height-1-y)*ih)>>12;
    unsigned turbulence=0;
    for(unsigned o=0;o<2u+load*2u;++o) {
        const unsigned frequency=3u<<o;
        const int32_t u=(nx+256)*(int)frequency/2+3072;
        const int32_t v=(int32_t)(h*frequency)-(int32_t)((frame&65535u)*(12u+2u*o));
        const int32_t ix=fire_fixed_floor8(u),iy=fire_fixed_floor8(v);
        const unsigned fx=fire_fixed_smooth((unsigned)(u-ix*256));
        const unsigned fy=fire_fixed_smooth((unsigned)(v-iy*256));
        const unsigned a=fire_fixed_hash(ix,iy,o),b=fire_fixed_hash(ix+1,iy,o);
        const unsigned c=fire_fixed_hash(ix,iy+1,o),d=fire_fixed_hash(ix+1,iy+1,o);
        const unsigned top=(a*(256u-fx)+b*fx)>>8;
        const unsigned bottom=(c*(256u-fx)+d*fx)>>8;
        const unsigned sample=(top*(256u-fy)+bottom*fy)>>8;
        turbulence+=(sample*(128u>>o))>>8;
    }
    const unsigned ax=(unsigned)(nx<0?-nx:nx);
    const int heat=(int)((256u-h)*3u/2u)-(int)((ax*(128u+h))>>8)+
                   (int)((turbulence*218u)>>8)-179;
    const unsigned r=(fire_fixed_clamp(heat*3)*255u)>>8;
    const unsigned g=(fire_fixed_clamp(heat*3-205)*240u)>>8;
    const unsigned b=(fire_fixed_clamp(heat*4-640)*160u)>>8;
    return (uint16_t)(((r&248u)<<8)|((g&252u)<<3)|(b>>3));
}
