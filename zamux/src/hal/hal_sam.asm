; hal_sam.asm — ZAMUX HAL implementation for SAM Coupé
; Provides the HAL jump table and all platform implementations.
; Assembled as part of the kernel; placed at HAL_BASE (0x3F00) in page 0.
;
; Phase 0 implements: con_*, kbd_*, tick_* only.
; Phase 1 adds: blk_*, snd_*, sys_*.

        include "hal.inc"
        include "sam_const.inc"

        org     HAL_BASE

; =====================================================================
; HAL JUMP TABLE (must start exactly at HAL_BASE; 3 bytes per entry)
; =====================================================================
hal_table:
        jp      sam_con_init            ; HAL_CON_INIT
        jp      sam_con_putc            ; HAL_CON_PUTC
        jp      sam_con_cls             ; HAL_CON_CLS
        jp      sam_con_scroll          ; HAL_CON_SCROLL
        jp      sam_con_setattr         ; HAL_CON_SETATTR
        jp      sam_con_cursor          ; HAL_CON_CURSOR
        jp      sam_kbd_init            ; HAL_KBD_INIT
        jp      sam_kbd_poll            ; HAL_KBD_POLL
        jp      sam_tick_init           ; HAL_TICK_INIT
        jp      sam_tick_ack            ; HAL_TICK_ACK
        jp      sam_blk_read            ; HAL_BLK_READ   (Phase 1 stub)
        jp      sam_blk_write           ; HAL_BLK_WRITE  (Phase 1 stub)
        jp      sam_blk_geo             ; HAL_BLK_GEO    (Phase 1 stub)
        jp      sam_snd_tone            ; HAL_SND_TONE   (Phase 1 stub)
        jp      sam_snd_off             ; HAL_SND_OFF    (Phase 1 stub)
        jp      sam_sys_break           ; HAL_SYS_BREAK
        jp      sam_sys_page            ; HAL_SYS_PAGE
        jp      sam_sys_reboot          ; HAL_SYS_REBOOT

; =====================================================================
; CONSOLE — MODE 3, 512×192, 85×24 text with 6×8 embedded font
; =====================================================================

; Cursor position in kernel variables (kernel data page, 0x8000+)
CON_ROW         equ     0x8000          ; current cursor row  (byte)
CON_COL         equ     0x8001          ; current cursor col  (byte)
CON_INK         equ     0x8002          ; current ink colour  (0-3 for MODE 3)
CON_PAPER       equ     0x8003          ; current paper colour

; MODE 3 pixel layout: 2 bits per pixel, 4 pixels per byte, 128 bytes per row.
; Each character cell is FONT_W(6) × FONT_H(8) pixels.
; Row n starts at FRAMEBUF + n*8*128; col c starts at byte offset c*6/4.
; (6-pixel-wide font means columns are not byte-aligned; we handle sub-byte.)

; --- sam_con_init ---
; Set MODE 3, clear framebuffer, set CLUT, home cursor.
sam_con_init:
        di
        ; Set VMPR: MODE 3 (0x40) | display page 1 (page << 1 = 0x02) → 0x42
        ld      a, VMODE3 | (DISPLAY_PAGE << 1)
        out     (VMPR), a
        ; Load CLUT: index 0=black, 1=white, 2=cyan, 3=yellow
        ; SAM CLUT: OUT 0xF8 with A8-A11 = colour index (via high address)
        ; Simplified: write 4 entries via CLUT port
        ld      bc, 0x00F8      ; B=index 0, C=port 0xF8
        ld      a, 0x00         ; black (R2G2B2 = 000000)
        out     (c), a
        inc     b
        ld      a, 0x3F         ; white (111111)
        out     (c), a
        inc     b
        ld      a, 0x2A         ; cyan (001010 10 = 0x2A approx)
        out     (c), a
        inc     b
        ld      a, 0x15         ; yellow
        out     (c), a
        ; Clear framebuffer (24576 bytes at 0x4000)
        call    sam_con_cls
        ; Home cursor
        xor     a
        ld      (CON_ROW), a
        ld      (CON_COL), a
        ei
        ret

; --- sam_con_cls ---
; Clear framebuffer, home cursor.
sam_con_cls:
        ld      hl, FRAMEBUF
        ld      de, FRAMEBUF + 1
        ld      bc, FRAMEBUF_SIZE - 1
        ld      (hl), 0
        ldir
        xor     a
        ld      (CON_ROW), a
        ld      (CON_COL), a
        ret

; --- sam_con_scroll ---
; Scroll framebuffer up one character row (8 pixel rows = 8*128 = 1024 bytes).
; Blank the bottom row.
sam_con_scroll:
        ld      hl, FRAMEBUF + 128*8    ; source: row 1
        ld      de, FRAMEBUF            ; dest:   row 0
        ld      bc, 128 * 8 * (DISPLAY_ROWS - 1)
        ldir
        ; blank last row
        ld      hl, FRAMEBUF + 128 * 8 * (DISPLAY_ROWS - 1)
        ld      de, FRAMEBUF + 128 * 8 * (DISPLAY_ROWS - 1) + 1
        ld      bc, 128 * 8 - 1
        ld      (hl), 0
        ldir
        ret

; --- sam_con_setattr ---
; B=ink C=paper (ignored in Phase 0; MODE 3 uses palette index)
sam_con_setattr:
        ld      a, b
        and     3               ; only 2 bits in MODE 3
        ld      (CON_INK), a
        ld      a, c
        and     3
        ld      (CON_PAPER), a
        ret

; --- sam_con_cursor ---
; B=row C=col — set cursor position.
sam_con_cursor:
        ld      a, b
        ld      (CON_ROW), a
        ld      a, c
        ld      (CON_COL), a
        ret

; --- sam_con_putc ---
; A=char. Render at current cursor, advance. Handle \n, \r, scroll.
sam_con_putc:
        cp      10              ; LF
        jr      z, .newline
        cp      13              ; CR
        jr      z, .cr
        cp      8               ; BS
        jr      z, .backspace
        ; printable: render glyph
        push    af
        push    bc
        push    de
        push    hl
        call    con_render_char
        pop     hl
        pop     de
        pop     bc
        pop     af
        ; advance col
        ld      hl, CON_COL
        inc     (hl)
        ld      a, (hl)
        cp      DISPLAY_COLS
        jr      c, .putc_ret
        ; wrap to next line
        ld      (hl), 0
.newline:
        ld      hl, CON_ROW
        inc     (hl)
        ld      a, (hl)
        cp      DISPLAY_ROWS
        jr      c, .putc_ret
        dec     (hl)            ; stay on last row
        call    sam_con_scroll
        jr      .putc_ret
.cr:
        xor     a
        ld      (CON_COL), a
        jr      .putc_ret
.backspace:
        ld      hl, CON_COL
        ld      a, (hl)
        or      a
        jr      z, .putc_ret
        dec     (hl)
.putc_ret:
        ret

; --- con_render_char ---
; Render character A at (CON_ROW, CON_COL) in MODE 3 framebuffer.
; Uses embedded 6×8 font at sam_font.
; In MODE 3: 2bpp, 4 pixels/byte, 128 bytes/scanline.
; Column c starts at bit-offset c*6 within the scanline.
con_render_char:
        sub     32              ; font starts at ASCII 32
        jr      c, .skip        ; below space → skip
        cp      96              ; 128 chars in font (32-127)
        jr      nc, .skip
        ; font offset = A * 8
        ld      l, a
        ld      h, 0
        add     hl, hl
        add     hl, hl
        add     hl, hl          ; HL = char * 8
        ld      de, sam_font
        add     hl, de          ; HL → first font row byte
        ; compute framebuffer address for (CON_ROW, CON_COL)
        ; pixel_row = CON_ROW * 8; pixel_col = CON_COL * 6
        ; byte_offset = pixel_row * 128 + pixel_col / 4
        ; bit_shift   = (pixel_col mod 4) * 2
        ld      a, (CON_ROW)
        ld      e, a
        ld      d, 0
        ; DE = row * 128: shift left 7
        sla     e
        rl      d
        sla     e
        rl      d
        sla     e
        rl      d
        sla     e
        rl      d
        sla     e
        rl      d
        sla     e
        rl      d
        sla     e
        rl      d               ; DE = row * 128
        ld      bc, FRAMEBUF
        add     hl, bc          ; temporarily (re-use below)
        ex      de, hl          ; DE = font ptr; HL = row offset + FRAMEBUF?
        ; (Simplified phase-0 implementation: draw via byte-aligned 8-wide cell)
        ; TODO Phase 0.2: proper 6-wide sub-byte rendering
        ; For now: use 8-pixel (1 byte) wide cells at col/2 alignment → 64 cols
        ; This gets us a working display; exact 85-col sub-byte rendering is P0.3
        ld      a, (CON_COL)
        ld      c, a            ; col
        ld      a, (CON_ROW)
        ; pixel address: FRAMEBUF + row*128 + col
        ld      h, 0
        ld      l, c
        ld      bc, FRAMEBUF
        add     hl, bc
        ; add row*128
        ld      a, (CON_ROW)
        ld      b, a
        ld      a, 0
.row_add:
        or      b
        jr      z, .rowdone
        ld      bc, 128
        add     hl, bc
        dec     b
        jr      .row_add
.rowdone:
        ; HL = framebuffer address for top-left of cell
        ex      de, hl          ; DE = framebuffer dest; HL = font src
        ld      b, 8            ; 8 pixel rows
.glyph_row:
        ld      a, (hl)         ; font byte
        ld      (de), a         ; write to framebuffer (8px wide, 1 byte)
        inc     hl
        inc     de
        ; advance DE to next framebuffer row (128 bytes/row - 1 already inc'd)
        push    hl
        ld      hl, 127
        add     hl, de
        ex      de, hl
        pop     hl
        djnz    .glyph_row
.skip:
        ret

; =====================================================================
; KEYBOARD — SAM matrix, same encoding as ZX Spectrum bits 0-4
; =====================================================================

sam_kbd_init:
        ret                     ; no init needed; matrix always live

; --- sam_kbd_poll ---
; Scan all keyboard rows; return first pressed key as ASCII in A.
; Returns A=0 if no key pressed. Handles CAPS SHIFT for uppercase.
; SAM keyboard matrix (identical to ZX Spectrum):
;   Port read: B=row_high_byte, C=0xFE → IN A,(C); bits 0-4, active low.
;   Row 0xFE: CAPS Z X C V     Row 0xFD: A S D F G
;   Row 0xFB: Q W E R T        Row 0xF7: 1 2 3 4 5
;   Row 0xEF: 0 9 8 7 6        Row 0xDF: P O I U Y
;   Row 0xBF: ENTER L K J H    Row 0x7F: SPACE SS M N B
sam_kbd_poll:
        ; Quick check: any key pressed at all?
        ld      bc, 0xFEFE
        in      a, (c)
        and     0x1F
        cp      0x1F
        jr      nz, .do_scan
        xor     a
        ret
.do_scan:
        ; Check CAPS SHIFT (row 0xFE bit 0) → uppercase flag
        ld      bc, 0xFEFE
        in      a, (c)
        ld      (_kbd_shift), a         ; save row 0 (has CAPS bit 0)
        ; Scan all 8 rows with their key tables
        ld      hl, _kbd_table          ; HL → table: row_hi, 5 key bytes
        ld      d, 8                    ; 8 rows
.row_loop:
        ld      b, (hl)                 ; B = row high byte
        inc     hl
        ld      c, 0xFE
        in      a, (c)                  ; read row
        cpl                             ; invert: 1=pressed
        and     0x1F                    ; mask 5 key bits
        jr      z, .row_skip            ; nothing in this row
        ; Find lowest set bit
        ld      e, a
        ld      a, 0
.bit_find:
        inc     a                       ; bit index 1-5
        rr      e
        jr      c, .got_bit
        cp      5
        jr      nz, .bit_find
        jr      .row_skip
.got_bit:
        ; A = bit position (1-5); HL points at the 5 key bytes for this row
        ld      c, a
        ld      b, 0
        add     hl, bc                  ; HL → key byte
        ld      a, (hl)
        or      a
        jr      z, .row_skip            ; unmapped key
        ; Apply CAPS SHIFT: if shift pressed and key is a-z, uppercase it
        ld      e, a
        ld      a, (_kbd_shift)
        cpl
        and     0x01                    ; bit 0 = CAPS SHIFT pressed
        jr      z, .no_shift
        ld      a, e
        cp      'a'
        jr      c, .no_shift
        cp      'z' + 1
        jr      nc, .no_shift
        sub     32                      ; to uppercase
        ret
.no_shift:
        ld      a, e
        ret
.row_skip:
        ld      a, (hl)                 ; skip 5 key bytes of this row
        inc     hl
        inc     hl
        inc     hl
        inc     hl
        inc     hl
        dec     d
        jr      nz, .row_loop
        xor     a
        ret

_kbd_shift: db  0xFF                    ; cached row 0xFE read

; Keyboard table: row_high_byte, key[bit0..bit4] (ASCII, 0=unmapped)
; Bit order: bit0=leftmost key in row description above.
_kbd_table:
        db      0xFE, 0, 'z', 'x', 'c', 'v'       ; row 0: CAPS Z X C V
        db      0xFD, 'a', 's', 'd', 'f', 'g'      ; row 1: A S D F G
        db      0xFB, 'q', 'w', 'e', 'r', 't'      ; row 2: Q W E R T
        db      0xF7, '1', '2', '3', '4', '5'      ; row 3: 1 2 3 4 5
        db      0xEF, '0', '9', '8', '7', '6'      ; row 4: 0 9 8 7 6
        db      0xDF, 'p', 'o', 'i', 'u', 'y'      ; row 5: P O I U Y
        db      0xBF, 13,  'l', 'k', 'j', 'h'      ; row 6: ENTER L K J H
        db      0x7F, ' ', 0,   'm', 'n', 'b'       ; row 7: SPACE SS M N B

; =====================================================================
; TICK — IM2 50 Hz timer via SAM line interrupt
; =====================================================================

TICK_COUNT      equ     0x8010          ; 32-bit tick counter in kernel data

sam_tick_init:
        ; Install IM2 vector table at 0xFD00; ISR at 0xFDFD
        ; (Standard SAM practice: 257-byte table, all entries point to ISR)
        di
        ld      hl, 0xFD00
        ld      a, 0xFD
        ld      b, 0
.fill:  ld      (hl), a
        inc     hl
        djnz    .fill
        ld      (hl), a         ; 257th byte
        ; Write ISR at 0xFDFD
        ld      hl, 0xFDFD
        ld      (hl), 0xFB      ; EI
        inc     hl
        ld      (hl), 0xED      ; RETI
        inc     hl
        ld      (hl), 0x4D
        ; Point I register to 0xFD (table at 0xFD00)
        ld      a, 0xFD
        ld      i, a
        im      2
        ei
        ret

sam_tick_ack:
        ; SAM clears line interrupt by reading status; nothing to do in ISR
        ret

; =====================================================================
; BLOCK STORAGE — Phase 1 stubs (return error)
; =====================================================================
sam_blk_read:
sam_blk_write:
        scf                     ; CF=1 → error (not implemented yet)
        ret

sam_blk_geo:
        ld      de, 0
        ld      bc, 0
        ret

; =====================================================================
; SOUND — Phase 1 stubs
; =====================================================================
sam_snd_tone:
sam_snd_off:
        ret

; =====================================================================
; SYSTEM
; =====================================================================

; --- sam_sys_break ---
; Returns CF=1 if BREAK (SPACE + SHIFT) is pressed.
sam_sys_break:
        ld      a, 0x7F         ; row: space / symbol-shift / M-N-B
        in      a, (0xFE)
        and     0x01            ; bit 0 = SPACE
        ld      b, a
        ld      a, 0xFE         ; row: CAPS-SHIFT / Z-X-C-V
        in      a, (0xFE)
        and     0x01            ; bit 0 = CAPS-SHIFT
        and     b               ; both pressed?
        jr      z, .no_break
        scf
        ret
.no_break:
        or      a               ; CF=0
        ret

; --- sam_sys_page ---
; A=page-number B=section(0-3). Page in a RAM page at the given section.
; Section 0=0x0000-0x3FFF (LMPR bits 5:0), Section 1=0x4000-0x7FFF (LMPR bits 13:8 via HMPR)
; Section 2/3 controlled via HMPR.
sam_sys_page:
        ; Simplified: for section A (B=0) update LMPR bits 5:0
        ld      c, a            ; save page number
        ld      a, b
        or      a
        jr      nz, .upper
        ; section 0: LMPR = page | 0x20 (write-enable low RAM, ROM off)
        ld      a, c
        or      0x20
        out     (LMPR), a
        ret
.upper:
        ; section 1: VMPR display page — do not change (display is pinned to page 1)
        ; section 2/3: HMPR
        ld      a, c
        out     (HMPR), a
        ret

; --- sam_sys_reboot ---
sam_sys_reboot:
        di
        xor     a
        out     (LMPR), a       ; map ROM back into section A
        rst     0               ; jump to SAM ROM reset

; =====================================================================
; EMBEDDED 6×8 FONT (96 characters, ASCII 32-127)
; Each character: 8 bytes, MSB=leftmost pixel.
; This is a compact VT100-style bitmap font.
; =====================================================================
sam_font:
        ; ASCII 32 (space) through 127 (~)
        ; Using a minimal 8×8 font here (displayed 8-wide in Phase 0;
        ; will be rendered 6-wide with sub-byte packing in Phase 0.3)
        ; Format: 8 bytes per char, top row first, bit7=leftmost

        ; 32 ' '
        db      0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00
        ; 33 '!'
        db      0x18,0x18,0x18,0x18,0x18,0x00,0x18,0x00
        ; 34 '"'
        db      0x66,0x66,0x24,0x00,0x00,0x00,0x00,0x00
        ; 35 '#'
        db      0x36,0x36,0x7F,0x36,0x7F,0x36,0x36,0x00
        ; 36 '$'
        db      0x0C,0x3E,0x03,0x1E,0x30,0x1F,0x0C,0x00
        ; 37 '%'
        db      0x63,0x33,0x18,0x0C,0x06,0x33,0x31,0x00
        ; 38 '&'
        db      0x1C,0x36,0x1C,0x6E,0x3B,0x33,0x6E,0x00
        ; 39 '\''
        db      0x0C,0x0C,0x06,0x00,0x00,0x00,0x00,0x00
        ; 40 '('
        db      0x18,0x0C,0x06,0x06,0x06,0x0C,0x18,0x00
        ; 41 ')'
        db      0x06,0x0C,0x18,0x18,0x18,0x0C,0x06,0x00
        ; 42 '*'
        db      0x00,0x66,0x3C,0xFF,0x3C,0x66,0x00,0x00
        ; 43 '+'
        db      0x00,0x0C,0x0C,0x3F,0x0C,0x0C,0x00,0x00
        ; 44 ','
        db      0x00,0x00,0x00,0x00,0x00,0x0C,0x0C,0x06
        ; 45 '-'
        db      0x00,0x00,0x00,0x3F,0x00,0x00,0x00,0x00
        ; 46 '.'
        db      0x00,0x00,0x00,0x00,0x00,0x0C,0x0C,0x00
        ; 47 '/'
        db      0x60,0x30,0x18,0x0C,0x06,0x03,0x01,0x00
        ; 48-57: digits 0-9
        db      0x3E,0x63,0x73,0x7B,0x6F,0x67,0x3E,0x00  ; '0'
        db      0x0C,0x0E,0x0C,0x0C,0x0C,0x0C,0x3F,0x00  ; '1'
        db      0x1E,0x33,0x30,0x1C,0x06,0x33,0x3F,0x00  ; '2'
        db      0x1E,0x33,0x30,0x1C,0x30,0x33,0x1E,0x00  ; '3'
        db      0x38,0x3C,0x36,0x33,0x7F,0x30,0x78,0x00  ; '4'
        db      0x3F,0x03,0x1F,0x30,0x30,0x33,0x1E,0x00  ; '5'
        db      0x1C,0x06,0x03,0x1F,0x33,0x33,0x1E,0x00  ; '6'
        db      0x3F,0x33,0x30,0x18,0x0C,0x0C,0x0C,0x00  ; '7'
        db      0x1E,0x33,0x33,0x1E,0x33,0x33,0x1E,0x00  ; '8'
        db      0x1E,0x33,0x33,0x3E,0x30,0x18,0x0E,0x00  ; '9'
        ; 58 ':'
        db      0x00,0x0C,0x0C,0x00,0x00,0x0C,0x0C,0x00
        ; 59 ';'
        db      0x00,0x0C,0x0C,0x00,0x00,0x0C,0x0C,0x06
        ; 60 '<'
        db      0x18,0x0C,0x06,0x03,0x06,0x0C,0x18,0x00
        ; 61 '='
        db      0x00,0x00,0x3F,0x00,0x00,0x3F,0x00,0x00
        ; 62 '>'
        db      0x06,0x0C,0x18,0x30,0x18,0x0C,0x06,0x00
        ; 63 '?'
        db      0x1E,0x33,0x30,0x18,0x0C,0x00,0x0C,0x00
        ; 64 '@'
        db      0x3E,0x63,0x7B,0x7B,0x7B,0x03,0x1E,0x00
        ; 65-90: A-Z
        db      0x0C,0x1E,0x33,0x33,0x3F,0x33,0x33,0x00  ; A
        db      0x3F,0x66,0x66,0x3E,0x66,0x66,0x3F,0x00  ; B
        db      0x3C,0x66,0x03,0x03,0x03,0x66,0x3C,0x00  ; C
        db      0x1F,0x36,0x66,0x66,0x66,0x36,0x1F,0x00  ; D
        db      0x7F,0x46,0x16,0x1E,0x16,0x46,0x7F,0x00  ; E
        db      0x7F,0x46,0x16,0x1E,0x16,0x06,0x0F,0x00  ; F
        db      0x3C,0x66,0x03,0x03,0x73,0x66,0x7C,0x00  ; G
        db      0x33,0x33,0x33,0x3F,0x33,0x33,0x33,0x00  ; H
        db      0x1E,0x0C,0x0C,0x0C,0x0C,0x0C,0x1E,0x00  ; I
        db      0x78,0x30,0x30,0x30,0x33,0x33,0x1E,0x00  ; J
        db      0x67,0x66,0x36,0x1E,0x36,0x66,0x67,0x00  ; K
        db      0x0F,0x06,0x06,0x06,0x46,0x66,0x7F,0x00  ; L
        db      0x63,0x77,0x7F,0x7F,0x6B,0x63,0x63,0x00  ; M
        db      0x63,0x67,0x6F,0x7B,0x73,0x63,0x63,0x00  ; N
        db      0x1C,0x36,0x63,0x63,0x63,0x36,0x1C,0x00  ; O
        db      0x3F,0x66,0x66,0x3E,0x06,0x06,0x0F,0x00  ; P
        db      0x1E,0x33,0x33,0x33,0x3B,0x1E,0x38,0x00  ; Q
        db      0x3F,0x66,0x66,0x3E,0x36,0x66,0x67,0x00  ; R
        db      0x1E,0x33,0x07,0x0E,0x38,0x33,0x1E,0x00  ; S
        db      0x3F,0x2D,0x0C,0x0C,0x0C,0x0C,0x1E,0x00  ; T
        db      0x33,0x33,0x33,0x33,0x33,0x33,0x3F,0x00  ; U
        db      0x33,0x33,0x33,0x33,0x33,0x1E,0x0C,0x00  ; V
        db      0x63,0x63,0x63,0x6B,0x7F,0x77,0x63,0x00  ; W
        db      0x63,0x63,0x36,0x1C,0x1C,0x36,0x63,0x00  ; X
        db      0x33,0x33,0x33,0x1E,0x0C,0x0C,0x1E,0x00  ; Y
        db      0x7F,0x63,0x31,0x18,0x4C,0x66,0x7F,0x00  ; Z
        ; 91 '['
        db      0x1E,0x06,0x06,0x06,0x06,0x06,0x1E,0x00
        ; 92 '\'
        db      0x03,0x06,0x0C,0x18,0x30,0x60,0x40,0x00
        ; 93 ']'
        db      0x1E,0x18,0x18,0x18,0x18,0x18,0x1E,0x00
        ; 94 '^'
        db      0x08,0x1C,0x36,0x63,0x00,0x00,0x00,0x00
        ; 95 '_'
        db      0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xFF
        ; 96 '`'
        db      0x0C,0x0C,0x18,0x00,0x00,0x00,0x00,0x00
        ; 97-122: a-z
        db      0x00,0x00,0x1E,0x30,0x3E,0x33,0x6E,0x00  ; a
        db      0x07,0x06,0x06,0x3E,0x66,0x66,0x3B,0x00  ; b
        db      0x00,0x00,0x1E,0x33,0x03,0x33,0x1E,0x00  ; c
        db      0x38,0x30,0x30,0x3e,0x33,0x33,0x6E,0x00  ; d
        db      0x00,0x00,0x1E,0x33,0x3f,0x03,0x1E,0x00  ; e
        db      0x1C,0x36,0x06,0x0f,0x06,0x06,0x0F,0x00  ; f
        db      0x00,0x00,0x6E,0x33,0x33,0x3E,0x30,0x1F  ; g
        db      0x07,0x06,0x36,0x6E,0x66,0x66,0x67,0x00  ; h
        db      0x0C,0x00,0x0E,0x0C,0x0C,0x0C,0x1E,0x00  ; i
        db      0x30,0x00,0x30,0x30,0x30,0x33,0x33,0x1E  ; j
        db      0x07,0x06,0x66,0x36,0x1E,0x36,0x67,0x00  ; k
        db      0x0E,0x0C,0x0C,0x0C,0x0C,0x0C,0x1E,0x00  ; l
        db      0x00,0x00,0x33,0x7F,0x7F,0x6B,0x63,0x00  ; m
        db      0x00,0x00,0x1F,0x33,0x33,0x33,0x33,0x00  ; n
        db      0x00,0x00,0x1E,0x33,0x33,0x33,0x1E,0x00  ; o
        db      0x00,0x00,0x3B,0x66,0x66,0x3E,0x06,0x0F  ; p
        db      0x00,0x00,0x6E,0x33,0x33,0x3E,0x30,0x78  ; q
        db      0x00,0x00,0x3B,0x6E,0x66,0x06,0x0F,0x00  ; r
        db      0x00,0x00,0x3E,0x03,0x1E,0x30,0x1F,0x00  ; s
        db      0x08,0x0C,0x3E,0x0C,0x0C,0x2C,0x18,0x00  ; t
        db      0x00,0x00,0x33,0x33,0x33,0x33,0x6E,0x00  ; u
        db      0x00,0x00,0x33,0x33,0x33,0x1E,0x0C,0x00  ; v
        db      0x00,0x00,0x63,0x6B,0x7F,0x7F,0x36,0x00  ; w
        db      0x00,0x00,0x63,0x36,0x1C,0x36,0x63,0x00  ; x
        db      0x00,0x00,0x33,0x33,0x33,0x3E,0x30,0x1F  ; y
        db      0x00,0x00,0x3F,0x19,0x0C,0x26,0x3F,0x00  ; z
        ; 123 '{'
        db      0x38,0x0C,0x0C,0x07,0x0C,0x0C,0x38,0x00
        ; 124 '|'
        db      0x18,0x18,0x18,0x00,0x18,0x18,0x18,0x00
        ; 125 '}'
        db      0x07,0x0C,0x0C,0x38,0x0C,0x0C,0x07,0x00
        ; 126 '~'
        db      0x6E,0x3B,0x00,0x00,0x00,0x00,0x00,0x00
        ; 127 DEL (block)
        db      0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF
