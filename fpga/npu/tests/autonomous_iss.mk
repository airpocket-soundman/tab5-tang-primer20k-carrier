# Additional targets included after the pinned upstream Makefile.
# AUTONOMOUS_CARRIER_ROOT is an absolute POSIX path in WSL.
AUTONOMOUS_ISS_SRC := $(AUTONOMOUS_CARRIER_ROOT)/fpga/npu/tests/autonomous_iss_runner.c
$(OUT)/autonomous_iss_runner.o: $(AUTONOMOUS_ISS_SRC) $(AUTONOMOUS_CARRIER_ROOT)/fpga/npu/firmware/autonomous/abi.h $(EFFECTIVE_CONFIG_STAMP) | $(OUT)
	$(CC) $(CFLAGS) -Iinclude -c $(AUTONOMOUS_ISS_SRC) -o $@
$(OUT)/autonomous_iss_runner: $(OUT)/autonomous_iss_runner.o $(LIBRV32EMU)
	$(CC) $< $(LIBRV32EMU) $(LDFLAGS) -o $@
