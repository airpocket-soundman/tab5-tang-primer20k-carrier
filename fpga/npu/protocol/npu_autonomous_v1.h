#ifndef NPU_AUTONOMOUS_V1_H
#define NPU_AUTONOMOUS_V1_H
#include <stdint.h>
/* Experimental profile, separate from 4E24. All values are little endian. */
#define NPU_AUTONOMOUS_CAPS 0x4e30u
#define NPU_AUTONOMOUS_CONTROL 0x7eu
#define NPU_AUTONOMOUS_MONITOR 0x7fu
#define NPU_AUTONOMOUS_ACTION_STATUS 0u
#define NPU_AUTONOMOUS_ACTION_START 1u
#define NPU_AUTONOMOUS_ACTION_ABORT 2u
#define NPU_AUTONOMOUS_ACTION_CLEAR 3u
#define NPU_AUTONOMOUS_MEMORY_READY (1u << 0)
#define NPU_AUTONOMOUS_RUNNING (1u << 1)
#define NPU_AUTONOMOUS_COMPLETE (1u << 2)
#define NPU_AUTONOMOUS_ERROR (1u << 3)
#define NPU_AUTONOMOUS_QUARANTINED (1u << 4)
#define NPU_AUTONOMOUS_TRAP (1u << 5)
#define NPU_AUTONOMOUS_ABORTED (1u << 6)
#define NPU_AUTONOMOUS_START_READY (1u << 7)
#define NPU_AUTONOMOUS_PROGRAM_BASE 0x05000000u
#define NPU_AUTONOMOUS_METADATA_BASE 0x05800000u
#define NPU_AUTONOMOUS_RGB_BASE 0x05900000u
#define NPU_AUTONOMOUS_MAILBOX_BASE 0x07ff0000u
/* CONTROL: payload action:u32, token:u32; STATUS requires token=0, others
 * require the currently bound 0x75 token. Reply value:u16 is immediate.
 * MONITOR: payload selector:u32, 0..127. word=selector>>1, half=selector&1;
 * reply value:u16. Words:0status,1node,2stage,3app_error,4finish,5CPUerror,
 * 6epoch,7run_id,8cycles_low,9cycles_high. Unassigned words read zero.
 * Multiword counters require high/low/high sampling; they are not atomic. */
#endif
