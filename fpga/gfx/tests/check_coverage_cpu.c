#include "triangle_reference.h"
#include <stdio.h>
#include <inttypes.h>
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    FILE *in=fopen(argv[1],"r"),*expected=fopen(argv[2],"r");
    if(!in||!expected)return 2;
    char input[200],want[200];unsigned count=0;
    while(fgets(input,sizeof(input),in)) {
        if(!fgets(want,sizeof(want),expected))return 2;
        unsigned v[8];uint64_t e[5];
        if(sscanf(input,"%4x%4x%4x%4x%4x%4x%4x%4x",v,v+1,v+2,v+3,v+4,v+5,v+6,v+7)!=8)return 2;
        if(sscanf(want,"%16"SCNx64"%16"SCNx64"%16"SCNx64"%16"SCNx64"%16"SCNx64,e,e+1,e+2,e+3,e+4)!=5)return 2;
        triangle_vertex a={(int16_t)v[0],(int16_t)v[1],0},b={(int16_t)v[2],(int16_t)v[3],0},c={(int16_t)v[4],(int16_t)v[5],0};
        int64_t signed_area=triangle_edge(a,b,c.x,c.y),area=signed_area<0?-signed_area:signed_area;
        int swapped=signed_area<0,covered=0;int64_t wa=0,wb=0,wc=0;
        if(area) {
            if(swapped){triangle_vertex t=b;b=c;c=t;}
            const int64_t px=v[6]*16+8,py=v[7]*16+8;
            wa=triangle_edge(b,c,px,py);wb=triangle_edge(c,a,px,py);wc=triangle_edge(a,b,px,py);
            covered=(wa>0||(wa==0&&triangle_inclusive(b,c)))&&(wb>0||(wb==0&&triangle_inclusive(c,a)))&&(wc>0||(wc==0&&triangle_inclusive(a,b)));
            if(swapped){int64_t t=wb;wb=wc;wc=t;}
        }
        uint64_t got[5]={(uint64_t)(covered|(!area<<1)|(swapped<<2)),(uint64_t)area,(uint64_t)wa,(uint64_t)wb,(uint64_t)wc};
        for(unsigned i=0;i<5;i++)if(got[i]!=e[i]){printf("FAIL CPU vector%u field%u\n",count,i);return 1;}
        count++;
    }
    fclose(in);fclose(expected);printf("PASS native CPU G0 coverage %u vectors\n",count);return 0;
}
