; sam_boot.asm — ZAMUX MGT boot sector
; 512-byte MGT disk boot sector loaded by SAM ROM SAMDOS at 0x8000.
; Sets up paging and jumps to the ZAMUX kernel entry point.
;
; SAM SAMDOS boot: loads 512 bytes from track 4, sector 1 to 0x8000, runs it.
; At entry: SAM ROM is mapped (page 0 = ROM in section A), SP=0x7FFF.

        DEVICE  NOSLOT64K
        org     0x8000

BOOT_MAGIC      equ     0xAA55          ; standard boot signature

        ; --- disable interrupts, set up clean paging ---
        di
        ; LMPR = 0x20: section A = page 0 (kernel), write-enable low RAM, ROM off
        ld      a, 0x20
        out     (0xFA), a       ; LMPR
        ; HMPR = 0x01: section C = page 1 (display), section D = page 2 (kdata)
        ld      a, 0x01
        out     (0xFB), a       ; HMPR
        ; VMPR = MODE 3 | display page 1 → 0x42
        ld      a, 0x42
        out     (0xFC), a       ; VMPR
        ; Stack in section C (kernel data page at 0x8000)
        ld      sp, 0xBFFF
        ; Jump to ZAMUX kernel entry (linked at 0x0100 in page 0)
        jp      ZAMUX_ENTRY

ZAMUX_ENTRY     equ     0x0100          ; kernel entry point in page 0

        ; Pad to 510 bytes, then append boot signature
        ds      510 - ($ - 0x8000), 0
        dw      BOOT_MAGIC
