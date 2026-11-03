#pragma once
#include <stddef.h>
#include "link_protocol.h"
// Resident triangle model v1 (MODEL_CAPS/LOAD/POSE/DRAW). Separate header so
// link_protocol.h and its synchronised hash stay unchanged. Bit-exact with
// fpga/reference/triangle_model.py and fpga/link/rtl/triangle_model.v.
// Caller owns all buffers; encoders return 0 on invalid arguments or capacity.
enum { MODEL_CAPS=0x48, MODEL_LOAD=0x49, MODEL_POSE=0x4a, MODEL_DRAW=0x4b,
       MODEL_MAX_VERTICES=64, MODEL_MAX_TRIANGLES=96, MODEL_POSE_BYTES=32,
       MODEL_TILE_Q4=512, MODEL_FORMAT=1,
       MODEL_OK=0, MODEL_BAD_CRC=1, MODEL_UNSUPPORTED=2, MODEL_BAD_ARGUMENT=3, MODEL_NOT_READY=5 };

typedef struct { int16_t x,y,z; } model_vertex_t;
typedef struct { uint8_t i0,i1,i2; uint16_t color; } model_triangle_t;
typedef struct {
    int16_t rotation[9];      // row major, Q2.14
    int16_t translation[3];   // camera-space offset, model units
    int16_t focal;            // Q12.4 pixels per (unit/depth)
    int16_t center_x,center_y;// Q12.4 screen centre
    uint8_t depth_shift;      // 0..15
} model_pose_t;
typedef struct { bool valid; int16_t x,y; uint16_t depth; } model_screen_t;

static inline unsigned model_load_size(unsigned nv,unsigned nt) { return 10+6*(nv+nt); }
static inline unsigned model_pose_size(void) { return 10+MODEL_POSE_BYTES; }

static inline void model_put16(uint8_t *out,uint16_t v) { out[0]=(uint8_t)v; out[1]=(uint8_t)(v>>8); }

static inline bool model_caps_encode(uint8_t q[8],uint8_t seq,bool tagged,uint8_t which) {
    if(!q || which>1) return false;
    link_make_request(q,(uint8_t)(MODEL_CAPS|(tagged?128:0)),seq,which,0);
    return true;
}
static inline bool model_draw_encode(uint8_t q[8],uint8_t seq,bool tagged,uint8_t tile_x,uint8_t tile_y) {
    if(!q) return false;
    link_make_request(q,(uint8_t)(MODEL_DRAW|(tagged?128:0)),seq,tile_x,tile_y);
    return true;
}
static inline unsigned model_load_encode(uint8_t *out,unsigned capacity,uint8_t seq,bool tagged,
    const model_vertex_t *v,unsigned nv,const model_triangle_t *t,unsigned nt) {
    if(!out || !v || !t || nv<1 || nv>MODEL_MAX_VERTICES || nt<1 || nt>MODEL_MAX_TRIANGLES ||
       capacity<model_load_size(nv,nt)) return 0;
    for(unsigned i=0;i<nt;i++) if(t[i].i0>=nv || t[i].i1>=nv || t[i].i2>=nv) return 0;
    link_make_request(out,(uint8_t)(MODEL_LOAD|(tagged?128:0)),seq,(uint8_t)nv,(uint8_t)nt);
    uint8_t *p=out+8;
    for(unsigned i=0;i<nv;i++) {model_put16(p,(uint16_t)v[i].x);model_put16(p+2,(uint16_t)v[i].y);model_put16(p+4,(uint16_t)v[i].z);p+=6;}
    for(unsigned i=0;i<nt;i++) {p[0]=t[i].i0;p[1]=t[i].i1;p[2]=t[i].i2;p[3]=0;model_put16(p+4,t[i].color);p+=6;}
    uint16_t c=link_crc16_extend(link_crc16(out,6),out+8,(size_t)(p-(out+8)));
    model_put16(p,c);
    return (unsigned)(p+2-out);
}
static inline unsigned model_pose_encode(uint8_t *out,unsigned capacity,uint8_t seq,bool tagged,const model_pose_t *pose) {
    if(!out || !pose || pose->depth_shift>15 || capacity<model_pose_size()) return 0;
    link_make_request(out,(uint8_t)(MODEL_POSE|(tagged?128:0)),seq,0,MODEL_FORMAT);
    uint8_t *p=out+8;
    for(unsigned i=0;i<9;i++) {model_put16(p,(uint16_t)pose->rotation[i]);p+=2;}
    for(unsigned i=0;i<3;i++) {model_put16(p,(uint16_t)pose->translation[i]);p+=2;}
    model_put16(p,(uint16_t)pose->focal);model_put16(p+2,(uint16_t)pose->center_x);
    model_put16(p+4,(uint16_t)pose->center_y);model_put16(p+6,pose->depth_shift);p+=8;
    uint16_t c=link_crc16_extend(link_crc16(out,6),out+8,MODEL_POSE_BYTES);
    model_put16(p,c);
    return model_pose_size();
}

// Response of a model command: normal eight-byte frame (plus the optional
// eight 0xc3 prefix bytes are handled by the transport, as for other commands).
static inline bool model_validate_response(const uint8_t r[8],const uint8_t q[8]) {
    uint16_t c=link_crc16(r,6);
    if(r[0]!=0x5a || r[2]!=q[2] || r[3]!=2 || r[6]!=(uint8_t)c || r[7]!=(uint8_t)(c>>8)) return false;
    if(r[1]!=MODEL_OK) return false;
    switch(q[1]&0x7f) {
        case MODEL_CAPS: return q[5]==0 && ((q[4]==0 && r[4]==MODEL_MAX_VERTICES && r[5]==MODEL_FORMAT) ||
                                            (q[4]==1 && r[4]==MODEL_MAX_TRIANGLES && r[5]==0));
        case MODEL_LOAD: return r[4]==q[4] && r[5]==q[5];
        case MODEL_POSE: return q[4]==0 && q[5]==MODEL_FORMAT && r[4]<=MODEL_MAX_VERTICES && r[5]>=1 && r[5]<=MODEL_MAX_VERTICES;
        case MODEL_DRAW: return r[4]<=MODEL_MAX_TRIANGLES && r[5]<=MODEL_MAX_TRIANGLES;
        default: return false;
    }
}

// Exact projection. int64 arithmetic; division truncates toward zero as in C.
static inline void model_project_vertex(const model_pose_t *pose,const model_vertex_t *v,model_screen_t *out) {
    int64_t cam[3];
    for(int row=0;row<3;row++) {
        int64_t acc=(int64_t)pose->rotation[3*row]*v->x+(int64_t)pose->rotation[3*row+1]*v->y+
                    (int64_t)pose->rotation[3*row+2]*v->z;
        // Arithmetic shift of a negative value is implementation-defined in C;
        // use floor division by 2^14 explicitly.
        int64_t floored=acc>=0 ? acc/16384 : -((-acc+16383)/16384);
        cam[row]=floored+pose->translation[row];
    }
    out->valid=false;out->x=0;out->y=0;out->depth=0;
    if(cam[2]<1) return;
    int64_t sx=pose->center_x+((int64_t)pose->focal*cam[0])/cam[2];
    int64_t sy=pose->center_y+((int64_t)pose->focal*cam[1])/cam[2];
    if(sx<-32768 || sx>32767 || sy<-32768 || sy>32767) return;
    int64_t depth=cam[2]>>pose->depth_shift;
    out->valid=true;out->x=(int16_t)sx;out->y=(int16_t)sy;out->depth=(uint16_t)(depth>65535?65535:depth);
}
static inline void model_project(const model_pose_t *pose,const model_vertex_t *v,unsigned nv,model_screen_t *out) {
    for(unsigned i=0;i<nv;i++) model_project_vertex(pose,&v[i],&out[i]);
}

// Replays one 32x32 tile: writes ten setter words per submitted triangle
// (AX,AY,BX,BY,CX,CY,ZA,ZB,ZC,COLOR) into records, in model order. Returns the
// number of submitted triangles (0..nt); skipped counts invalid/overflowing
// triangles, matching the device's MODEL_DRAW reply. records needs 10*nt words.
static inline unsigned model_tile_records(uint16_t *records,const model_triangle_t *t,unsigned nt,
    const model_screen_t *s,uint8_t tile_x,uint8_t tile_y,unsigned *skipped) {
    int32_t ox=(int32_t)tile_x*MODEL_TILE_Q4,oy=(int32_t)tile_y*MODEL_TILE_Q4;
    unsigned drawn=0,skip=0;
    for(unsigned k=0;k<nt;k++) {
        const model_screen_t *p[3]={&s[t[k].i0],&s[t[k].i1],&s[t[k].i2]};
        if(!(p[0]->valid && p[1]->valid && p[2]->valid)) {skip++;continue;}
        int32_t lx[3],ly[3];bool fit=true;
        for(int i=0;i<3;i++) {
            lx[i]=(int32_t)p[i]->x-ox;ly[i]=(int32_t)p[i]->y-oy;
            if(lx[i]<-32768||lx[i]>32767||ly[i]<-32768||ly[i]>32767) fit=false;
        }
        if(!fit) {skip++;continue;}
        if((lx[0]<0&&lx[1]<0&&lx[2]<0)||(lx[0]>MODEL_TILE_Q4-1&&lx[1]>MODEL_TILE_Q4-1&&lx[2]>MODEL_TILE_Q4-1)||
           (ly[0]<0&&ly[1]<0&&ly[2]<0)||(ly[0]>MODEL_TILE_Q4-1&&ly[1]>MODEL_TILE_Q4-1&&ly[2]>MODEL_TILE_Q4-1)) continue;
        uint16_t *r=records+10*drawn;
        for(int i=0;i<3;i++) {r[2*i]=(uint16_t)lx[i];r[2*i+1]=(uint16_t)ly[i];r[6+i]=p[i]->depth;}
        r[9]=t[k].color;
        drawn++;
    }
    if(skipped) *skipped=skip;
    return drawn;
}
