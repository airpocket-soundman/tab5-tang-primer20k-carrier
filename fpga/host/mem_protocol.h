#pragma once
#include "link_protocol.h"
#include <stddef.h>

/* Optional standalone MEM diagnostic, not a GFX or generic RAMdisk ABI. */
enum { MEM_CAPS=0x50,MEM_BASE_LO=0x51,MEM_BASE_HI=0x52,
 MEM_BEATS_LO=0x53,MEM_BEATS_HI=0x54,MEM_SEED_LO=0x55,MEM_SEED_HI=0x56,
 MEM_START=0x57,MEM_SNAPSHOT=0x58,MEM_WORD=0x59,MEM_CANCEL=0x5a,
 MEM_RECALIBRATE=0x5b,MEM_SYSQUERY=0x5c,
 MEM_SNAPSHOT_WORDS=32,MEM_FORMAT=0x014d,MEM_CONFIGURED_BYTES=134217728 };
enum { MEM_SYS_CALIBRATED=1,MEM_SYS_BUSY=2,MEM_SYS_USER_FAULT=4,
 MEM_SYS_BANK_VALID=8,MEM_SYS_BANK_STALE=16,MEM_SYS_MAILBOX_TIMEOUT=32,
 MEM_SYS_CONTEXT_LOST=64,MEM_SYS_CAL_GUARD_READY=128,MEM_SYS_USER_READY=256,
 MEM_SYS_HEARTBEAT_FRESH=512,MEM_SYS_LOSS_USER_RESET=1024,
 MEM_SYS_LOSS_CALIBRATION=2048,MEM_SYS_LOSS_HEARTBEAT=4096,
 MEM_SYS_LOSS_PENDING_RESET=8192 };
enum { MEM_ERROR_NONE=0,MEM_ERROR_UNCALIBRATED=1,MEM_ERROR_RANGE=2,
 MEM_ERROR_WRITE_TIMEOUT=3,MEM_ERROR_READ_TIMEOUT=4,MEM_ERROR_READ_ORDER=5,
 MEM_ERROR_MISMATCH=6,MEM_ERROR_CANCEL=7,MEM_ERROR_CALIBRATION_LOST=8,
 MEM_ERROR_TOTAL_DEADLINE=9 };
enum { MEM_DIAG_FORMAT=0x014e,MEM_DIAG_WORDS=11,
 MEM_QUERY_DIAG_CAPS=8,MEM_QUERY_DIAG_FLAGS=9,MEM_QUERY_DIAG_INDEX_LO=10,
 MEM_QUERY_DIAG_COMMANDS_LO=12,MEM_QUERY_DIAG_DATA_LO=14,
 MEM_QUERY_DIAG_READS_LO=16,MEM_QUERY_DIAG_LAST_ADDRESS_LO=18 };
enum { MEM_DIAG_COMMAND_VALID=1,MEM_DIAG_COMMAND_READY=2,
 MEM_DIAG_DATA_VALID=4,MEM_DIAG_DATA_READY=8,MEM_DIAG_COMMAND_SENT=16,
 MEM_DIAG_DATA_SENT=32,MEM_DIAG_READ_PENDING=64,MEM_DIAG_GAP=128,
 MEM_DIAG_READ_VALID=256,MEM_DIAG_RESET_RELEASED=512,
 MEM_DIAG_CALIBRATED=1024,MEM_DIAG_FAULT_LATCHED=2048 };
static inline uint32_t mem_words32(const uint16_t *w) {
 return (uint32_t)w[0]|((uint32_t)w[1]<<16);
}
static inline uint64_t mem_words64(const uint16_t *w) {
 return (uint64_t)mem_words32(w)|((uint64_t)mem_words32(w+2)<<32);
}
static inline bool mem_range_valid(uint32_t base,uint32_t beats) {
 return !(base&15)&&beats>=1&&beats<=8388608u&&
        (uint64_t)base+(uint64_t)beats*16<=MEM_CONFIGURED_BYTES;
}
/* A CRC/sequence-valid diagnostic error is a valid frame, never a PASS. */
static inline bool mem_validate_response(const uint8_t r[8],const uint8_t q[8]) {
 uint16_t qc=link_crc16(q,6),rc=link_crc16(r,6);
 unsigned op=q[1]&127,value=(unsigned)r[4]|((unsigned)r[5]<<8);
 if(q[0]!=0xa5||q[3]!=2||q[6]!=(uint8_t)qc||q[7]!=(uint8_t)(qc>>8)||
    op<MEM_CAPS||op>MEM_SYSQUERY||r[0]!=0x5a||r[2]!=q[2]||r[3]!=2||
    r[6]!=(uint8_t)rc||r[7]!=(uint8_t)(rc>>8)||r[1]>5)return false;
 if(r[1])return value==0;
 if(op>=MEM_BASE_LO&&op<=MEM_SEED_HI)return value==((unsigned)q[4]|((unsigned)q[5]<<8));
 switch(op) {
 case MEM_CAPS:return !q[4]&&!q[5]&&value==MEM_FORMAT;
 case MEM_START:case MEM_SNAPSHOT:return !q[4]&&!q[5];
 case MEM_CANCEL:case MEM_RECALIBRATE:return !q[4]&&!q[5]&&!value;
 case MEM_WORD:return q[4]<32&&!q[5];
 case MEM_SYSQUERY:
  if(q[5])return false;
  switch(q[4]) {
   case 0:return value==MEM_FORMAT;case 1:return value==2048;
   case 2:return value==0x0d0a;case 3:return value==0x0310;
   case 4:return value==324;case 5:return value==81;
   case 6:return !(value&0xc000);case 7:return true;
   case 8:return value==MEM_DIAG_FORMAT;
   case 9:case 10:case 11:case 12:case 13:case 14:case 15:case 16:case 17:case 18:case 19:return true;
   default:return false;
  }
 default:return false;
 }
}
/* Call only AFTER all32WORD replies, a fresh SYSQUERY6 and SYSQUERY7.
 * Never credit old DONE from a stale bank, an epoch loss or a torn generation.
 * Equal generations alone do not establish freshness across reset/wrap;
 * caller must have just successfully acknowledged MEM_SNAPSHOT in this epoch.
 */
static inline bool mem_snapshot_done_pass(const uint16_t w[32],uint32_t job,
 uint32_t beats,uint16_t acknowledged_generation,uint16_t post_generation,uint16_t post_sys_flags) {
 const unsigned required=MEM_SYS_CALIBRATED|MEM_SYS_BANK_VALID|
  MEM_SYS_CAL_GUARD_READY|MEM_SYS_USER_READY|MEM_SYS_HEARTBEAT_FRESH;
 const unsigned forbidden=MEM_SYS_BUSY|MEM_SYS_USER_FAULT|MEM_SYS_BANK_STALE|
  MEM_SYS_MAILBOX_TIMEOUT|MEM_SYS_CONTEXT_LOST|0xfc00;
 return beats&&beats<=8388608u&&acknowledged_generation==post_generation&&
  (post_sys_flags&required)==required&&!(post_sys_flags&forbidden)&&
  w[31]==MEM_FORMAT&&w[30]==81&&(w[0]&31)==5&&!(w[0]&0xffa0)&&w[1]==0x0500&&
  mem_words32(w+2)==job&&mem_words32(w+4)==2u*beats&&
  mem_words32(w+6)==0&&mem_words64(w+26)!=0;
}
