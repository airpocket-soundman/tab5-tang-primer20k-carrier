#pragma once
#include <cstdint>
#include <cstddef>
#include <cmath>
#include <algorithm>
namespace inference { namespace rtdetr {
struct Storage {void* context=nullptr;bool(*read)(void*,std::uint64_t,void*,std::size_t)=nullptr;bool(*write)(void*,std::uint64_t,const void*,std::size_t)=nullptr;bool(*cancelled)(void*)=nullptr;};
struct GridSample {std::uint64_t input=0,grid=0,output=0;unsigned n=0,c=0,h=0,w=0,oh=0,ow=0;bool align_corners=false;};
struct GridStats {std::uint64_t samples=0,read_bytes=0,write_bytes=0;};
// ONNX GridSample: rank4 FLOAT, bilinear, zeros only. Other attributes must be
// rejected by exporter. Input NCHW, grid N/OH/OW/xy, output N/C/OH/OW.
inline bool grid_sample(const GridSample&r,const Storage&s,GridStats&stats){
 stats={};if(!s.read||!s.write||!r.n||!r.c||!r.h||!r.w||!r.oh||!r.ow||r.h>1048576||r.w>1048576)return false;
 const std::uint64_t pixels=std::uint64_t(r.oh)*r.ow,input_count=std::uint64_t(r.n)*r.c*r.h*r.w,output_count=std::uint64_t(r.n)*r.c*pixels,grid_count=std::uint64_t(r.n)*pixels*2;
 if(input_count>UINT32_MAX||output_count>UINT32_MAX||grid_count>UINT32_MAX||r.input>UINT64_MAX-input_count*4||r.grid>UINT64_MAX-grid_count*4||r.output>UINT64_MAX-output_count*4)return false;
 auto read=[&](std::uint64_t a,void*p,std::size_t n){if(s.cancelled&&s.cancelled(s.context))return false;if(!s.read(s.context,a,p,n))return false;stats.read_bytes+=n;return true;};
 float grids[128*2],out[128];
 for(unsigned batch=0;batch<r.n;++batch)for(std::uint64_t base=0;base<pixels;base+=128){const unsigned count=unsigned(std::min<std::uint64_t>(128,pixels-base));if(!read(r.grid+(batch*pixels+base)*8,grids,count*8))return false;
  for(unsigned channel=0;channel<r.c;++channel){for(unsigned j=0;j<count;++j){float gx=grids[j*2],gy=grids[j*2+1];if(std::isnan(gx))gx=-1;if(std::isnan(gy))gy=-1;
   const float x=r.align_corners?((gx+1)*.5f)*(r.w-1):((gx+1)*r.w-1)*.5f;
   const float y=r.align_corners?((gy+1)*.5f)*(r.h-1):((gy+1)*r.h-1)*.5f;
   if(!std::isfinite(x)||!std::isfinite(y))return false;
   if(x<=-1||y<=-1||x>=r.w||y>=r.h){out[j]=0;continue;}
   const int x0=int(std::floor(x)),y0=int(std::floor(y));const float dx=x-x0,dy=y-y0;float v[4]={};
   for(unsigned yy=0;yy<2;++yy)for(unsigned xx=0;xx<2;++xx){const int ix=x0+int(xx),iy=y0+int(yy);if(ix>=0&&iy>=0&&unsigned(ix)<r.w&&unsigned(iy)<r.h){const std::uint64_t at=((std::uint64_t(batch)*r.c+channel)*r.h+unsigned(iy))*r.w+unsigned(ix);if(!read(r.input+at*4,&v[yy*2+xx],4))return false;}}
   out[j]=(1-dy)*((1-dx)*v[0]+dx*v[1])+dy*((1-dx)*v[2]+dx*v[3]);
  }if(s.cancelled&&s.cancelled(s.context))return false;const auto at=((std::uint64_t(batch)*r.c+channel)*pixels+base)*4;if(!s.write(s.context,r.output+at,out,count*4))return false;stats.write_bytes+=count*4;stats.samples+=count;}
 }
 return true;
}
}}
