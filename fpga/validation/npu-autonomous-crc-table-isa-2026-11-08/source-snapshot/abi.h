#pragma once
#include <stdint.h>
/* Isolated FPGA-local CPU ABI; not a published host wire opcode/capability. */
#define AUTONOMOUS_ABI 1u
#define AUTONOMOUS_MAGIC 0x31545041u
#define AUTONOMOUS_MAILBOX_BASE 0x07ff0000u
#define AUTONOMOUS_MMIO_BASE 0x10000000u
#define AUTONOMOUS_MMIO_STATUS 0x00u
#define AUTONOMOUS_MMIO_COMMAND 0x04u
#define AUTONOMOUS_MMIO_ACK 0x08u
#define AUTONOMOUS_MMIO_ABORT 0x0cu
#define AUTONOMOUS_MMIO_ERROR 0x10u
#define AUTONOMOUS_MMIO_EPOCH 0x18u
#define AUTONOMOUS_MMIO_NODE 0x20u
#define AUTONOMOUS_MMIO_STAGE 0x24u
#define AUTONOMOUS_MMIO_APP_ERROR 0x28u
#define AUTONOMOUS_MMIO_FINISH 0x2cu
#define AUTONOMOUS_MMIO_DESCRIPTOR 0x40u
#define AUTONOMOUS_READY (1u<<0)
#define AUTONOMOUS_BUSY (1u<<1)
#define AUTONOMOUS_DONE (1u<<2)
#define AUTONOMOUS_ERROR (1u<<3)
#define AUTONOMOUS_QUARANTINED (1u<<4)
#define AUTONOMOUS_RESULT_VALID (1u<<5)
#define AUTONOMOUS_MEMORY_READY (1u<<6)
enum AutonomousState { AP_BOOT=1, AP_CHECKING=2, AP_RUNNING=3, AP_COMPLETE=4, AP_FAILED=5, AP_CANCELLED=6 };
struct AutonomousMailbox {
 uint32_t magic,abi,command,cancel;
 uint32_t token,metadata_base,metadata_bytes,constant_base;
 uint32_t arena_base,scratch_base,scratch_bytes,reserved;
 uint32_t state,error,progress,total;
 uint32_t nodes,conv,matmul,output_base;
 uint32_t output_count,epoch,firmware_abi,completed_token;
 uint32_t tile_jobs,matrix_jobs,softcore_nonmac,hard_mac;
 char error_text[96];
};
