#include <stdio.h>
#include <stdint.h>
#include "../link_protocol.h"
int main(void) {
    unsigned q[8], r[8];
    while (scanf("%x%x%x%x%x%x%x%x %x%x%x%x%x%x%x%x", &q[0],&q[1],&q[2],&q[3],&q[4],&q[5],&q[6],&q[7], &r[0],&r[1],&r[2],&r[3],&r[4],&r[5],&r[6],&r[7]) == 16) {
        uint8_t request[8], response[8], made[8];
        for (int i=0;i<8;i++) { request[i]=(uint8_t)q[i]; response[i]=(uint8_t)r[i]; }
        link_make_request(made, request[1], request[2], request[4], request[5]);
        for (int i=0;i<8;i++) printf("%02x", made[i]);
        printf(" %d\n", link_validate_response(response, request));
    }
    return 0;
}
