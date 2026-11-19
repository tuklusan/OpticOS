; sam_const.inc — SAM Coupé hardware constants for ZAMUX
; Replaces ZX-UX const.inc (which references Spectrum ROM addresses and ports).
; All constants are native SAM hardware — no Spectrum ROM dependency.

; --- Memory paging ports ---
LMPR            equ     0xFA            ; Lower Memory Page Register
HMPR            equ     0xFB            ; Upper Memory Page Register
VMPR            equ     0xFC            ; Video Memory Page Register
CLUT            equ     0xF8            ; Colour Look-Up Table port

; --- VMPR values (video mode | display page) ---
VMODE1          equ     0x00            ; MODE 1 (Spectrum-compat, 256x192, 2bpp)
VMODE2          equ     0x20            ; MODE 2 (512x192, 1bpp, hi-res mono)
VMODE3          equ     0x40            ; MODE 3 (512x192, 4-colour palette)
VMODE4          equ     0x60            ; MODE 4 (256x192, 16-colour CLUT)
VPAGE_DISPLAY   equ     0x01            ; display uses page 1 (0x4000 in section B)

; --- Keyboard ---
; SAM keyboard matrix rows decoded via port 0xFFFE with address lines A8-A15
; Bit layout identical to ZX Spectrum bits 0-4
KBD_PORT        equ     0xFE            ; same port as Spectrum (A8=0 selects row)

; --- Tape (EAR) ---
EAR_PORT        equ     0xFE
EAR_BIT         equ     6               ; bit 6 of port 0xFE (same as Spectrum)
EAR_MASK        equ     (1 << EAR_BIT)

; --- FDC (MGT floppy) ---
FDC_STATUS      equ     0xE7            ; FDC status/command register
FDC_TRACK       equ     0xE7            ; (same port, different context)
FDC_DATA        equ     0xEF            ; FDC data register

; --- Sound (SAA1099) ---
SAA_DATA        equ     0xFF            ; SAA1099 data port
SAA_ADDR        equ     0xFE            ; SAA1099 address port (A8=1 selects)

; --- ZAMUX kernel memory map ---
KERNEL_PAGE     equ     0               ; page 0: kernel code + HAL table
DISPLAY_PAGE    equ     1               ; page 1: MODE 3 framebuffer
KDATA_PAGE      equ     2               ; page 2: kernel data + inode FS RAM
USER_PAGE_BASE  equ     3               ; pages 3+: user process arena

; --- Display geometry (MODE 3) ---
DISPLAY_COLS    equ     85              ; characters per row  (512 / 6 pixel font)
DISPLAY_ROWS    equ     24              ; rows
FONT_W          equ     6               ; font width in pixels
FONT_H          equ     8               ; font height in pixels
FRAMEBUF        equ     0x4000          ; framebuffer base (section B = display page)
FRAMEBUF_SIZE   equ     (512 * 192 / 4) ; MODE 3: 2 bits per pixel = 24576 bytes

; --- Spectrum compatibility sysvar addresses (for ported kernel code) ---
; ZX-UX kernel references some Spectrum sysvars; we keep them at the same
; addresses since section C (0x8000-) is kernel data and we can place them there.
; These are ZAMUX kernel variables, not Spectrum ROM sysvars.
SV_ATTRP        equ     0x5C8D          ; current permanent attribute (kernel uses this)
SV_ATTRT        equ     0x5C8F          ; temporary attribute
