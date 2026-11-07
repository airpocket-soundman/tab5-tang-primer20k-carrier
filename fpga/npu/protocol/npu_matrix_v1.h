#ifndef TAB5_NPU_MATRIX_V1_H
#define TAB5_NPU_MATRIX_V1_H
#include <stdint.h>
/* Explicit experimental capability, not supported by 4E20/4E23. */
#define NPU_MATRIX_V1_CAPABILITY UINT16_C(0x4e24)
#define NPU_MATRIX_V1_USERCODE UINT32_C(0x00004e24)
#define NPU_MATRIX_V1_RUN 0x78u
#define NPU_MATRIX_V1_STATUS 0x79u
#define NPU_MATRIX_V1_ACCEPTED_LO 0x7au
#define NPU_MATRIX_V1_ACCEPTED_HI 0x7bu
#define NPU_MATRIX_V1_COMPLETED_LO 0x7cu
#define NPU_MATRIX_V1_COMPLETED_HI 0x7du
#define NPU_MATRIX_V1_PAYLOAD_BYTES 36u
/* Nine unsigned32 values serialized LITTLE ENDIAN, not native struct bytes. */
#define NPU_MATRIX_V1_M_OFFSET 0u
#define NPU_MATRIX_V1_K_OFFSET 4u
#define NPU_MATRIX_V1_N_OFFSET 8u
#define NPU_MATRIX_V1_A_BASE_OFFSET 12u
#define NPU_MATRIX_V1_A_PITCH_OFFSET 16u
#define NPU_MATRIX_V1_B_BASE_OFFSET 20u
#define NPU_MATRIX_V1_B_PITCH_OFFSET 24u
#define NPU_MATRIX_V1_C_BASE_OFFSET 28u
#define NPU_MATRIX_V1_C_PITCH_OFFSET 32u
#define NPU_MATRIX_V1_READY_BIT 0u
#define NPU_MATRIX_V1_BUSY_BIT 1u
#define NPU_MATRIX_V1_ERROR_BIT 2u
#define NPU_MATRIX_V1_QUARANTINED_BIT 3u
#define NPU_MATRIX_V1_RESULT_VALID_BIT 4u
#define NPU_MATRIX_V1_ERROR_CODE_SHIFT 8u
/* Status5 returns sequencer error1..9 in response R16. Any failed job
 * invalidates its entire C region; DISARM/coordinated reset before reuse.
 * See docs/NPU_DDR_MATRIX_V1.md for CRC, leases, watchdog and DDR layouts. */
#endif
