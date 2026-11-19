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
BOOT_BIN   := $(BUILD)/sam_boot.bin
KERNEL_BIN := $(BUILD)/zamux_kernel.bin
FLOPPY_MGT := $(BUILD)/zamux.mgt

# SAM floppy geometry (MGT DSDD 80-track 10-sector)
MGT_TRACKS := 80
MGT_SIDES  := 2
MGT_SECTORS:= 10
MGT_SECSIZE:= 512
MGT_SIZE   := $(shell expr $(MGT_TRACKS) \* $(MGT_SIDES) \* $(MGT_SECTORS) \* $(MGT_SECSIZE))

.PHONY: all boot kernel floppy clean test

all: floppy

# --- Boot sector ---
boot: $(BUILD)
	$(ASM) $(ASMFLAGS) --raw=$(BOOT_BIN) $(SRC_BOOT)/sam_boot.asm
	@size=$$(wc -c < $(BOOT_BIN)); \
	 if [ $$size -ne 512 ]; then echo "ERROR: boot sector must be 512 bytes (got $$size)"; exit 1; fi
	@echo "Boot sector OK (512 bytes)"

# --- Kernel (HAL + main) ---
kernel: $(BUILD)
	$(ASM) $(ASMFLAGS) \
		--inc=$(SRC_HAL) \
		--inc=$(SRC_KERNEL) \
		--raw=$(KERNEL_BIN) \
		$(SRC_HAL)/hal_sam.asm
	$(ASM) $(ASMFLAGS) \
		--inc=$(SRC_HAL) \
		--inc=$(SRC_KERNEL) \
		--raw=$(BUILD)/zamux_main.bin \
		$(SRC_KERNEL)/zamux_main.asm
	cat $(BUILD)/zamux_main.bin >> $(KERNEL_BIN)
	@echo "Kernel OK ($$(wc -c < $(KERNEL_BIN)) bytes)"

# --- MGT floppy image ---
floppy: boot kernel
	python3 tools/make_mgt.py $(BOOT_BIN) $(KERNEL_BIN) $(FLOPPY_MGT)
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
