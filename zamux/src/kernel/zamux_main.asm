; zamux_main.asm — ZAMUX kernel entry point (Phase 0 bring-up stub)
; Assembled into page 0 at 0x0100.
; Phase 0 goal: boot → MODE 3 console → print banner → keyboard echo loop.

        include "../hal/hal.inc"
        include "../hal/sam_const.inc"

        org     0x0100

ZAMUX_ENTRY:
        ; --- HAL console init ---
        HALCALL HAL_CON_INIT

        ; --- HAL tick init (50 Hz IM2) ---
        HALCALL HAL_TICK_INIT

        ; --- print banner ---
        ld      hl, _banner
        call    puts

        ; --- main echo loop ---
echo_loop:
        HALCALL HAL_KBD_POLL
        or      a
        jr      z, echo_loop    ; no key
        HALCALL HAL_CON_PUTC
        jr      echo_loop

; --- puts: print NUL-terminated string at HL ---
puts:
        ld      a, (hl)
        or      a
        ret     z
        HALCALL HAL_CON_PUTC
        inc     hl
        jr      puts

_banner:
        db      "ZAMUX 0.1  (c) 2026 SANYALnet Labs / tuklusan", 10, 13
        db      "Native SAM Coupe port of ZX-UX", 10, 13
        db      "> ", 0
