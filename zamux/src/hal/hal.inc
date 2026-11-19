; hal.inc — ZAMUX Hardware Abstraction Layer interface contract
; Shared by the kernel and all hal_*.asm platform files.
; The HAL is a CP/M-BIOS-style jump table at HAL_BASE; each slot is 3 bytes (JP nn).
; The kernel calls through offsets; it never touches a port or ROM address directly.

HAL_BASE        equ     0x3F00          ; jump table lives at top of kernel page

; Slot offsets (3 bytes each = JP nn)
HAL_CON_INIT    equ     0               ; console init
HAL_CON_PUTC    equ     3               ; A=char → output at cursor, advance
HAL_CON_CLS     equ     6               ; clear screen, home cursor
HAL_CON_SCROLL  equ     9               ; scroll one line up
HAL_CON_SETATTR equ     12              ; B=ink (0-15) C=paper (0-15)
HAL_CON_CURSOR  equ     15              ; B=row (0-23) C=col (0-84)
HAL_KBD_INIT    equ     18              ; keyboard init
HAL_KBD_POLL    equ     21              ; → A=ASCII (0 = no key)
HAL_TICK_INIT   equ     24              ; install 50Hz IM2 ISR
HAL_TICK_ACK    equ     27              ; acknowledge tick (call from ISR)
HAL_BLK_READ    equ     30              ; HL=buf DE=LBA → read 512-byte sector; CF=err
HAL_BLK_WRITE   equ     33              ; HL=buf DE=LBA → write 512-byte sector; CF=err
HAL_BLK_GEO     equ     36              ; → DE=total sectors, B=heads, C=spt
HAL_SND_TONE    equ     39              ; HL=freq(Hz) DE=duration(ms)
HAL_SND_OFF     equ     42              ; silence
HAL_SYS_BREAK   equ     45              ; → CF=1 if BREAK pressed
HAL_SYS_PAGE    equ     48              ; A=page-number B=section(0-3) → page in
HAL_SYS_REBOOT  equ     51              ; warm reboot

HAL_TABLE_SIZE  equ     54              ; total bytes in table

; Convenience macro: call a HAL entry
; Usage:  HALCALL HAL_CON_PUTC
        macro HALCALL entry
        call HAL_BASE + entry
        endm
