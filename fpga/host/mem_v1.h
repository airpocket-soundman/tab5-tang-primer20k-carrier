#pragma once
/* MEMV1: explicit DDR3 READ / WRITE / CRC32 over the carrier LINK (docs/MEMV1_*.md, protocol spec v1 draft).
 * Host codec only: no GPIO, PARLIO, DMA, timer or OS code. Not a transparent RAM; DDR3 is reached only by
 * explicit chunked commands (<= 4 KiB, 16-byte aligned). Opcodes 0x60..0x67 are a PROPOSAL until every host
 * adopts them (hardware: not yet verified).
 *
 * Request  : a5 op seq 02 a b crcLo crcHi  (op bit7 = tagged reply with 8x c3 prefix).
 *            RD / WR / CRC32 : a,b = beats (le16, 1..256), then descriptor {addr le32, arg le32},
 *            WR payload (beats*16), CRC16 trailer over header[0..5]+descriptor+payload.
 *            arg: WR = zlib CRC32 of the payload, CRC32 = previous finalized CRC32 (0 for a new message),
 *            RD = must be 0.
 * Response : 5a status seq 02 r0 r1 crcLo crcHi (r0,r1 = generation for success of RD/WR/CRC32).
 *            RD success : + payload(beats*16) + CRC16 over reply[0..5]+payload.
 *            CRC32 success : + crc32 le32 + CRC16 over reply[0..5]+crc32.
 *            Any nonzero status is a plain 8-byte frame.
 */
#include "link_protocol.h"
#include <stddef.h>

enum { MEMV1_CAPS=0x60, MEMV1_STATUS=0x61, MEMV1_RD=0x62, MEMV1_WR=0x63, MEMV1_FILL=0x64,
       MEMV1_COPY=0x65, MEMV1_CRC32=0x66, MEMV1_CANCEL=0x67 };
enum { MEMV1_ST_OK=0, MEMV1_ST_FORMAT=1, MEMV1_ST_UNKNOWN=2, MEMV1_ST_INVALID=3, MEMV1_ST_TIMEOUT=4,
       MEMV1_ST_NOT_READY=5, MEMV1_ST_BUSY=6, MEMV1_ST_CRC_ERROR=7, MEMV1_ST_CANCELLED=8,
       MEMV1_ST_DDR_FAULT=9, MEMV1_ST_STALE=10 };
enum { MEMV1_FORMAT=0x4d31, MEMV1_ALIGN=16, MEMV1_MAX_BEATS=256, MEMV1_CHUNK_BYTES=4096,
       MEMV1_CAPACITY_BYTES=134217728 };
/* CAPS word indices (a) and STATUS word indices (a). */
enum { MEMV1_CAPS_FORMAT=0, MEMV1_CAPS_VERSION=1, MEMV1_CAPS_CAPACITY_MIB=2, MEMV1_CAPS_ALIGN=3,
       MEMV1_CAPS_MAX_BEATS=4, MEMV1_CAPS_FEATURES=5, MEMV1_CAPS_REGIONS=6, MEMV1_CAPS_RESERVED=7 };
enum { MEMV1_FEAT_RD=1, MEMV1_FEAT_WR=2, MEMV1_FEAT_FILL=4, MEMV1_FEAT_COPY=8, MEMV1_FEAT_CRC32=16,
       MEMV1_FEAT_BIST=32, MEMV1_FEAT_CANCEL=64 };
enum { MEMV1_STAT_FLAGS=0, MEMV1_STAT_GENERATION=1, MEMV1_STAT_LAST_STATUS=2, MEMV1_STAT_OP_COUNT=3,
       MEMV1_STAT_UNDEF_ADDR_LO=4, MEMV1_STAT_UNDEF_ADDR_HI=5, MEMV1_STAT_UNDEF_BEATS=6, MEMV1_STAT_RAW=7 };
enum { MEMV1_FLAG_CALIBRATED=1, MEMV1_FLAG_USER_ALIVE=2, MEMV1_FLAG_INFLIGHT=4, MEMV1_FLAG_BIST=8,
       MEMV1_FLAG_UNDEFINED_RANGE=16 };

static inline uint32_t memv1_crc32(uint32_t prev, const uint8_t *p, size_t n) {
    /* zlib crc32(): nibble table, chainable via the previous finalized value. */
    static const uint32_t t[16]={0x00000000,0x1db71064,0x3b6e20c8,0x26d930ac,0x76dc4190,0x6b6b51f4,
        0x4db26158,0x5005713c,0xedb88320,0xf00f9344,0xd6d6a3e8,0xcb61b38c,0x9b64c2b0,0x86d3d2d4,
        0xa00ae278,0xbdbdf21c};
    uint32_t c=prev^0xffffffffu;
    while(n--) { c^=*p++; c=(c>>4)^t[c&15]; c=(c>>4)^t[c&15]; }
    return c^0xffffffffu;
}
/* addr 16B aligned, 1..256 beats, inside capacity, no 32-bit wrap. */
static inline bool memv1_range_valid(uint32_t addr, uint32_t beats) {
    return !(addr&15) && beats>=1 && beats<=MEMV1_MAX_BEATS &&
           (uint64_t)addr+(uint64_t)beats*16<=MEMV1_CAPACITY_BYTES;
}
static inline size_t memv1_prefix_len(const uint8_t q[8]) { return (q[1]&0x80)?8:0; }
/* 8-byte setters for CAPS / STATUS / CANCEL (a = word index). */
static inline void memv1_make_simple(uint8_t q[8], uint8_t op, uint8_t seq, uint8_t a, uint8_t b, bool tagged) {
    link_make_request(q,(uint8_t)(op|(tagged?0x80:0)),seq,a,b);
}
static inline void memv1_put32(uint8_t *p, uint32_t v) { p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24); }
static inline uint32_t memv1_get32(const uint8_t *p) { return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24); }
/* Returns the request length, 0 on invalid arguments (no range check beyond beats 1..256: the device decides). */
static inline size_t memv1_encode(uint8_t *out, size_t cap, uint8_t op, uint8_t seq, uint32_t addr,
        uint32_t beats, uint32_t arg, const uint8_t *payload, bool tagged) {
    size_t pay=(op==MEMV1_WR)?(size_t)beats*16:0;
    if(!out || beats<1 || beats>MEMV1_MAX_BEATS || cap<18+pay) return 0;
    if(op!=MEMV1_RD && op!=MEMV1_WR && op!=MEMV1_CRC32) return 0;
    if(pay && !payload) return 0;
    link_make_request(out,(uint8_t)(op|(tagged?0x80:0)),seq,(uint8_t)beats,(uint8_t)(beats>>8));
    memv1_put32(out+8,addr); memv1_put32(out+12,arg);
    for(size_t i=0;i<pay;i++) out[16+i]=payload[i];
    uint16_t c=link_crc16_extend(link_crc16(out,6),out+8,(unsigned)(8+pay));
    out[16+pay]=(uint8_t)c; out[17+pay]=(uint8_t)(c>>8);
    return 18+pay;
}
static inline size_t memv1_encode_rd(uint8_t *out, size_t cap, uint8_t seq, uint32_t addr, uint32_t beats, bool tagged) {
    return memv1_encode(out,cap,MEMV1_RD,seq,addr,beats,0,NULL,tagged);
}
static inline size_t memv1_encode_crc32(uint8_t *out, size_t cap, uint8_t seq, uint32_t addr, uint32_t beats,
        uint32_t previous_crc, bool tagged) {
    return memv1_encode(out,cap,MEMV1_CRC32,seq,addr,beats,previous_crc,NULL,tagged);
}
/* WR: the payload CRC32 is computed here (descriptor arg). */
static inline size_t memv1_encode_wr(uint8_t *out, size_t cap, uint8_t seq, uint32_t addr, uint32_t beats,
        const uint8_t *payload, bool tagged) {
    if(!payload || beats<1 || beats>MEMV1_MAX_BEATS) return 0;
    return memv1_encode(out,cap,MEMV1_WR,seq,addr,beats,memv1_crc32(0,payload,(size_t)beats*16),payload,tagged);
}
/* Expected response length (after the optional 8-byte c3 prefix) once the first 8 bytes are known.
 * Returns 0 if the 8-byte header itself is not valid for q. */
static inline size_t memv1_response_len(const uint8_t q[8], const uint8_t r[8]) {
    uint16_t c=link_crc16(r,6);
    if(q[0]!=0xa5 || r[0]!=0x5a || r[2]!=q[2] || r[3]!=2 || r[6]!=(uint8_t)c || r[7]!=(uint8_t)(c>>8)) return 0;
    if(r[1]) return 8;
    switch(q[1]&0x7f) {
        case MEMV1_RD: return 10+(size_t)((unsigned)q[4]|((unsigned)q[5]<<8))*16;
        case MEMV1_CRC32: return 14;
        default: return 8;
    }
}
/* Validates a complete response (prefix already removed). Returns the LINK status (0..10) when the frame is
 * well formed for request q (including all trailers), or -1. A nonzero status is not a failure of the codec. */
static inline int memv1_validate_response(const uint8_t *r, size_t len, const uint8_t q[8]) {
    size_t want=memv1_response_len(q,r);
    unsigned op=q[1]&0x7f;
    if(!want || len!=want || r[1]>MEMV1_ST_STALE) return -1;
    if(r[1]) return (r[4]==0 && r[5]==0) || r[1]==MEMV1_ST_CANCELLED ? r[1] : -1;
    if(want>8) {
        uint16_t c=link_crc16_extend(link_crc16(r,6),r+8,(unsigned)(want-10));
        if(r[want-2]!=(uint8_t)c || r[want-1]!=(uint8_t)(c>>8)) return -1;
    }
    switch(op) {
        case MEMV1_CAPS: return (q[4]<=7 && q[5]==0) ? 0 : -1;
        case MEMV1_STATUS: return (q[4]<=7 && q[5]==0) ? 0 : -1;
        case MEMV1_CANCEL: return (q[4]==0 && q[5]==0) ? 0 : -1;
        case MEMV1_RD: case MEMV1_WR: case MEMV1_CRC32: return 0;
        case LINK_ID: case LINK_ECHO: case LINK_INVERT: case LINK_CAPS: return 0;
        default: return -1;
    }
}
/* CAPS word 0 must equal MEMV1_FORMAT (distinct from MEM_FORMAT 0x014d of the BIST diagnostic ABI). */
static inline bool memv1_caps_format_ok(const uint8_t r[8]) { return r[1]==0 && (r[4]|((unsigned)r[5]<<8))==MEMV1_FORMAT; }
