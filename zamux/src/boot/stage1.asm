; stage1.asm - ZAMUX Phase 0 smoke-test payload
; Loaded by SAMDOS AUTORUN at 0x8000 (section C, page 1).
; Diagnostic border colours show progress; final result = white screen in MODE 3.

    org     0x8000

LMPR    equ     0xFA
VMPR    equ     0xFC
CLUT    equ     0xF8
BORDER  equ     0xFE

VMPR_MODE3_P2   equ     0x42    ; MODE 3, display pages 2+3
LMPR_P2         equ     0x22    ; ROM0 OFF, page 2@A, page 3@B
WHITE           equ     127
FB_SIZE         equ     0x6000  ; 24576 bytes = 192 rows × 128 bytes

start:
    di

    ; Step 1: border = RED (confirms code reached 0x8000)
    ld      a, 2
    out     (BORDER), a

    ; Step 2: set MODE 3, pages 2+3 as display
    ld      a, VMPR_MODE3_P2
    out     (VMPR), a

    ; Step 3: border = BLUE (confirms VMPR write)
    ld      a, 1
    out     (BORDER), a

    ; Step 4: map pages 2+3 to sections A+B (writable framebuffer)
    ld      a, LMPR_P2
    out     (LMPR), a

    ; Step 5: border = GREEN (confirms LMPR write)
    ld      a, 4
    out     (BORDER), a

    ; Step 6: set CLUT entries 0-3 all to white (palette 127)
    ; OUT (C),A: B = CLUT entry index (port high byte), C = 0xF8, A = palette colour
    ld      c, CLUT
    ld      a, WHITE
    ld      b, 0
    out     (c), a      ; CLUT[0] = white
    inc     b
    out     (c), a      ; CLUT[1] = white
    inc     b
    out     (c), a      ; CLUT[2] = white
    inc     b
    out     (c), a      ; CLUT[3] = white

    ; Step 7: border = CYAN (confirms CLUT writes)
    ld      a, 5
    out     (BORDER), a

    ; Step 8: fill 24576-byte framebuffer with 0xFF
    ; 0xFF in 2bpp = pixel 3 everywhere; mode3_mapping[3]=CLUT[3]=white
    ; section A (0x0000-0x3FFF) = page 2 (first 16 KB of framebuffer)
    ; section B (0x4000-0x5FFF) = page 3 (last 8 KB of framebuffer)
    ld      hl, 0x0000
    ld      (hl), 0xFF
    ld      de, 0x0001
    ld      bc, FB_SIZE - 1
    ldir

    ; Step 9: border = WHITE (fill done — final steady state)
    ld      a, 7
    out     (BORDER), a

.loop:
    jr      .loop
