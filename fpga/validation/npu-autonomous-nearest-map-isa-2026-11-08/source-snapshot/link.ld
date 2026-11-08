OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { FW (rwx) : ORIGIN = 0x05000000, LENGTH = 8M }
SECTIONS {
 .text : { KEEP(*(.text.start)) *(.text .text.*) } > FW
 .rodata : { *(.srodata .srodata.* .rodata .rodata.*) } > FW
 .data : { *(.data .data.* .sdata .sdata.*) } > FW
 .bss ALIGN(16) (NOLOAD) : {
  __bss_start = .;
  *(.bss .bss.* .sbss .sbss.* COMMON)
  . = ALIGN(16);
  __bss_end = .;
 } > FW
 __global_pointer$ = __bss_start + 0x800;
 __firmware_end = .;
 __stack_top = 0x07fe0000;
 __heap_start = 0x06000000;
 __heap_end = 0x07000000;
 /DISCARD/ : { *(.eh_frame .eh_frame.* .comment) }
 ASSERT(__firmware_end <= 0x05800000, "firmware overlaps RQG metadata")
}
