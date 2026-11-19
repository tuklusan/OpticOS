################################################################################
# ZAMUX — Native SAM Coupé port of ZX-UX
# Build system (Phase 0)
################################################################################

ASM        := /home/user/tools/sjasmplus/sjasmplus
ASMFLAGS   := --nologo

BUILD      := build
SRC_HAL    := src/hal
SRC_KERNEL := src/kernel
SRC_BOOT   := src/boot

# Output files
STAGE1_BIN := $(BUILD)/stage1.bin
KERNEL_BIN := $(BUILD)/zamux_kernel.bin
FLOPPY_MGT := $(BUILD)/zamux.mgt

.PHONY: all stage1 kernel floppy clean test

all: floppy

# --- Stage1 smoke-test payload (the SAMDOS CODE file) ---
stage1: $(BUILD)
	$(ASM) $(ASMFLAGS) --raw=$(STAGE1_BIN) $(SRC_BOOT)/stage1.asm
	@echo "Stage1 OK ($$(wc -c < $(STAGE1_BIN)) bytes)"

# --- Kernel (HAL + main) — compiled for reference; not yet in floppy ---
kernel: $(BUILD)
	$(ASM) $(ASMFLAGS) \
		--inc=$(SRC_HAL) \
		--raw=$(KERNEL_BIN) \
		$(SRC_HAL)/hal_sam.asm
	$(ASM) $(ASMFLAGS) \
		--inc=$(SRC_HAL) \
		--raw=$(BUILD)/zamux_main.bin \
		$(SRC_KERNEL)/zamux_main.asm
	cat $(BUILD)/zamux_main.bin >> $(KERNEL_BIN)
	@echo "Kernel OK ($$(wc -c < $(KERNEL_BIN)) bytes)"

# --- MGT floppy image (stage1 as the SAMDOS BOOT file) ---
floppy: stage1
	python3 tools/make_mgt.py $(STAGE1_BIN) $(FLOPPY_MGT)
	@echo "Floppy image: $(FLOPPY_MGT)"

# --- SimCoupé headless smoke test ---
test: floppy
	@echo "Running smoke test in SimCoupé..."
	python3 tools/smoke_test.py $(FLOPPY_MGT)

# --- Housekeeping ---
$(BUILD):
	mkdir -p $(BUILD)

clean:
	rm -rf $(BUILD)

################################################################################
# Dependency notes:
#   sjasmplus   : apt install sjasmplus, or build from source
#   simcoupe    : /home/user/tools/simcoupe/build/simcoupe (stock, unmodified)
#   python3     : system python3
################################################################################
