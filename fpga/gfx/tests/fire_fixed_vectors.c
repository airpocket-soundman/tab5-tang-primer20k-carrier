#include "fire_fixed.h"
#include <stdio.h>
int main(void) {
    unsigned x,y,w,h,frame,load;
    while(scanf("%u %u %u %u %u %u",&x,&y,&w,&h,&frame,&load)==6) {
        printf("%u\n",fire_fixed_valid(w,h,load)?1024u:0u);
        if(fire_fixed_valid(w,h,load))
            for(unsigned yy=0;yy<32;++yy) for(unsigned xx=0;xx<32;++xx)
                printf("%04x\n",fire_fixed_pixel(x+xx,y+yy,w,h,frame,load));
    }
    return 0;
}
