#!/usr/bin/env python3
"""
make_mgt.py — Build a minimal MGT SAM Coupé floppy image for ZAMUX.

Usage: make_mgt.py <boot.bin> <kernel.bin> <output.mgt>

MGT geometry: 80 tracks × 2 sides × 10 sectors × 512 bytes = 819,200 bytes.
SAMDOS boot: track 4, sector 1 (side 0) = the boot sector (512 bytes).
Kernel: placed starting at track 4, sector 2 onwards.

Sector numbering in MGT images: (track * 2 + side) * 10 + (sector - 1) × 512.
Track 4, side 0, sector 1 → offset = (4*2+0)*10*512 + 0*512 = 40960.
"""

import sys
import struct
import os

TRACKS  = 80
SIDES   = 2
SECTORS = 10
SECSIZE = 512
TOTAL   = TRACKS * SIDES * SECTORS * SECSIZE  # 819200

def sector_offset(track, side, sector):
    """Return byte offset of a sector in the MGT image (1-indexed sector)."""
    return ((track * SIDES + side) * SECTORS + (sector - 1)) * SECSIZE

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} boot.bin kernel.bin output.mgt")
        sys.exit(1)

    boot_path, kernel_path, out_path = sys.argv[1:]

    boot = open(boot_path, 'rb').read()
    kernel = open(kernel_path, 'rb').read()

    if len(boot) != SECSIZE:
        print(f"ERROR: boot.bin must be exactly {SECSIZE} bytes (got {len(boot)})")
        sys.exit(1)

    img = bytearray(TOTAL)

    # Boot sector: track 4, side 0, sector 1
    off = sector_offset(4, 0, 1)
    img[off:off + SECSIZE] = boot
    print(f"Boot sector → track 4, side 0, sector 1 (offset 0x{off:05X})")

    # Kernel: track 4, side 0, sectors 2-10, then track 4 side 1, etc.
    kdata = kernel
    sec = 2
    track = 4
    side = 0
    written = 0
    while kdata:
        chunk, kdata = kdata[:SECSIZE], kdata[SECSIZE:]
        chunk = chunk.ljust(SECSIZE, b'\x00')
        off = sector_offset(track, side, sec)
        img[off:off + SECSIZE] = chunk
        written += len(chunk)
        sec += 1
        if sec > SECTORS:
            sec = 1
            side += 1
            if side >= SIDES:
                side = 0
                track += 1
            if track >= TRACKS:
                print("ERROR: kernel too large for floppy")
                sys.exit(1)

    print(f"Kernel ({len(kernel)} bytes) → {written} bytes written from track 4, side 0, sector 2")

    open(out_path, 'wb').write(bytes(img))
    print(f"Written: {out_path} ({len(img)} bytes, {len(img)//1024} KB)")

if __name__ == '__main__':
    main()
