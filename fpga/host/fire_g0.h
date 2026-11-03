/* Integer CPU reference for the GPU LAB "Procedural fire" scene (fire_g0).
 * Bit-identical to fpga/reference/fire_g0.py and to the RTL fpga/gfx/rtl/fire_pixel.v.
 * Q16 fixed point; 640x360 visual profile. Header-only, no dynamic memory.
 */
#ifndef FIRE_G0_H
#define FIRE_G0_H
#include <stdint.h>

#define FIRE_G0_W 640
#define FIRE_G0_H 360
#define FIRE_G0_SX 205
#define FIRE_G0_SY 182
#define FIRE_G0_TIME_STEP 2949

static inline uint16_t fire_g0_hash16(int32_t ix,int32_t iy,unsigned octave){
    uint32_t hv=(uint32_t)ix*0x9E37u+(uint32_t)iy*0x85EBu+(uint32_t)(17u+octave)*0xC2B3u;
    uint32_t x1=hv^(hv>>15);
    uint32_t m=(x1&0xFFFFu)*0x2C1Bu;
    return (uint16_t)(((m^(m>>11))^(hv>>16))&0xFFFFu);
}
static inline int32_t fire_g0_smooth(int32_t f){
    int32_t s=(int32_t)(((uint32_t)f*(uint32_t)f)>>16);
    return (int32_t)(((int64_t)s*(196608-2*f))>>16);
}
static inline int32_t fire_g0_noise(int32_t u,int32_t v,unsigned octave){
    int32_t ix=u>>16,fx=u&0xFFFF,iy=v>>16,fy=v&0xFFFF;
    int32_t n00=fire_g0_hash16(ix,iy,octave),n10=fire_g0_hash16(ix+1,iy,octave);
    int32_t n01=fire_g0_hash16(ix,iy+1,octave),n11=fire_g0_hash16(ix+1,iy+1,octave);
    int32_t sx=fire_g0_smooth(fx),sy=fire_g0_smooth(fy);
    int32_t a=n00+(int32_t)(((int64_t)(n10-n00)*sx)>>16);
    int32_t b=n01+(int32_t)(((int64_t)(n11-n01)*sx)>>16);
    return a+(int32_t)(((int64_t)(b-a)*sy)>>16);
}
static inline int32_t fire_g0_clamp(int64_t v,int32_t lo,int32_t hi){return v<lo?lo:v>hi?hi:(int32_t)v;}
/* Heat in Q16 (0..65536). */
static inline int32_t fire_g0_heat(int x,int y,uint32_t frame,unsigned octaves){
    int32_t nx=(x-320)*FIRE_G0_SX,h=(359-y)*FIRE_G0_SY;
    int32_t t=(int32_t)(frame*FIRE_G0_TIME_STEP);
    int32_t turb=0;
    for(unsigned o=0;o<octaves;o++){
        int32_t freq=3<<o;
        int32_t u=nx*freq+(12<<16);
        int32_t tm=t+(t>>2)*(int32_t)o;
        int32_t v=h*freq-tm;
        turb+=fire_g0_noise(u,v,o)>>(o+1);
    }
    int32_t a=((65536-h)*3)>>1;
    int32_t b=(int32_t)(((int64_t)(nx<0?-nx:nx)*(32768+h))>>16);
    int32_t c=(int32_t)(((int64_t)turb*55706)>>16);
    return fire_g0_clamp((int64_t)a-b+c-45875,0,65536);
}
static inline uint16_t fire_g0_color(int x,int y,uint32_t frame,unsigned octaves){
    int32_t hq=fire_g0_heat(x,y,frame,octaves);
    int32_t r=(int32_t)(((int64_t)(hq*3>65536?65536:hq*3)*255)>>16);
    int32_t g=(int32_t)(((int64_t)fire_g0_clamp((int64_t)hq*3-52429,0,65536)*240)>>16);
    int32_t b=(int32_t)(((int64_t)fire_g0_clamp((int64_t)hq*4-163840,0,65536)*160)>>16);
    return (uint16_t)(((r&248)<<8)|((g&252)<<3)|(b>>3));
}
#endif
