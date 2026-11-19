#!/usr/bin/env python3
"""
make_mgt.py — Build a minimal MGT SAM Coupé floppy image for ZAMUX.

Usage: make_mgt.py <payload.bin> <output.mgt>

The payload is wrapped as a SAMDOS CODE file named "BOOT" in the directory
(track 0, side 0, sector 0).  Data sectors begin at track 4, side 0, sector 1.

MGT geometry  : 80 tracks × 2 sides × 10 sectors × 512 bytes = 819 200 bytes.
Sector payload: 510 bytes of data + 2 bytes (next_track | side<<7, next_sector).
                next_sector = 0 marks the final sector.

SAMDOS directory entry (occupies one full 512-byte sector):
  [0]       file type  (19 = CODE)
  [1-10]    filename   (10 bytes, space-padded)
  [11-12]   sector count big-endian
  [13]      start track
  [14]      start sector (1-based)
  [15-235]  sector bitmap  (1 bit per sector from start, LSB first)
  [236]     start page (HMPR page SAMDOS maps while loading)
  [237-238] load address   (little-endian, absolute CPU address)
  [239]     page count     (whole 16 KB pages in file)
  [240-241] size mod 16384 (little-endian)
  [242]     execute type   (2 = auto-execute with normal paging)
  [243-244] execute address (little-endian)
"""

import sys
import struct
import math
import os

TRACKS   = 80
SIDES    = 2
SECTORS  = 10
SECSIZE  = 512
PAYLOAD  = SECSIZE - 2        # usable bytes per data sector
TOTAL    = TRACKS * SIDES * SECTORS * SECSIZE  # 819 200

DIR_TRACKS = 4   # tracks 0-3 are directory; data starts at track 4

LOAD_ADDR = 0x8000   # SAMDOS loads CODE file here (start of section C)
EXEC_ADDR = 0x8000   # execute at load address
LOAD_PAGE = 1        # HMPR page SAMDOS sets while loading


def sector_offset(track, side, sector):
    """Byte offset of a 1-based sector in the MGT image."""
    return ((track * SIDES + side) * SECTORS + (sector - 1)) * SECSIZE


def next_sector_coords(track, side, sector):
    """Return (next_track, next_side, next_sector) in sequential order."""
    sector += 1
    if sector > SECTORS:
        sector = 1
        side += 1
        if side >= SIDES:
            side = 0
            track += 1
    return track, side, sector


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} payload.bin output.mgt")
        sys.exit(1)

    payload_path, out_path = sys.argv[1:]
    payload = open(payload_path, 'rb').read()
    file_size = len(payload)
    print(f"Payload: {payload_path}  ({file_size} bytes)")

    # --- calculate sector count ---
    num_sectors = math.ceil(file_size / PAYLOAD)
    if num_sectors == 0:
        num_sectors = 1
    print(f"Data sectors needed: {num_sectors}")

    # sanity: data must fit on the disk
    max_sectors = (TRACKS - DIR_TRACKS) * SIDES * SECTORS
    if num_sectors > max_sectors:
        print(f"ERROR: payload too large ({num_sectors} sectors > {max_sectors})")
        sys.exit(1)

    img = bytearray(TOTAL)

    # ----------------------------------------------------------------
    # Directory entry in track 0, side 0, sector 0 (sector 1, index 0)
    # ----------------------------------------------------------------
    dir_entry = bytearray(SECSIZE)

    dir_entry[0] = 19                              # file type CODE

    name = b'AUTORUN   '[:10]                      # 10-char name; SAM BOOT cmd looks for AUTO*
    dir_entry[1:11] = name

    dir_entry[11] = (num_sectors >> 8) & 0xFF      # sector count, big-endian
    dir_entry[12] = num_sectors & 0xFF

    dir_entry[13] = DIR_TRACKS                     # start track (4)
    dir_entry[14] = 1                              # start sector (1-based)

    # sector bitmap: 1 bit per sector starting from sector 0 of the chain
    for s in range(num_sectors):
        byte_idx = 15 + s // 8
        bit_idx  = s % 8
        dir_entry[byte_idx] |= (1 << bit_idx)

    # load/exec parameters (bytes 236-244)
    page_count   = file_size >> 14                 # whole 16 KB pages
    size_mod     = file_size & 0x3FFF              # remainder bytes

    dir_entry[236] = LOAD_PAGE
    dir_entry[237] = LOAD_ADDR & 0xFF
    dir_entry[238] = (LOAD_ADDR >> 8) & 0xFF
    dir_entry[239] = page_count
    dir_entry[240] = size_mod & 0xFF
    dir_entry[241] = (size_mod >> 8) & 0x3F
    dir_entry[242] = 2                             # auto-execute, normal paging
    dir_entry[243] = EXEC_ADDR & 0xFF
    dir_entry[244] = (EXEC_ADDR >> 8) & 0xFF

    off = sector_offset(0, 0, 1)
    img[off:off + SECSIZE] = dir_entry
    print(f"Directory entry written at track 0, side 0, sector 1 (offset 0x{off:05X})")

    # ----------------------------------------------------------------
    # Data sectors starting at track 4, side 0, sector 1
    # ----------------------------------------------------------------
    track, side, sector = DIR_TRACKS, 0, 1
    remaining = payload

    for i in range(num_sectors):
        chunk = remaining[:PAYLOAD]
        remaining = remaining[PAYLOAD:]
        chunk = chunk.ljust(PAYLOAD, b'\x00')      # pad final sector

        is_last = (i == num_sectors - 1)
        if is_last:
            next_t, next_s_num = 0, 0              # EOF marker
        else:
            nt, ns_ide, ns_ec = next_sector_coords(track, side, sector)
            next_t  = nt | (ns_ide << 7)
            next_s_num = ns_ec

        sector_data = chunk + bytes([next_t, next_s_num])
        off = sector_offset(track, side, sector)
        img[off:off + SECSIZE] = sector_data

        print(f"  sector {i+1}/{num_sectors}: track {track} side {side} sec {sector}"
              f"  offset 0x{off:05X}"
              f"  → next ({next_t & 0x7F}, side {next_t >> 7}, {next_s_num})")

        track, side, sector = next_sector_coords(track, side, sector)

    open(out_path, 'wb').write(bytes(img))
    print(f"\nWritten: {out_path}  ({len(img)} bytes, {len(img) // 1024} KB)")


if __name__ == '__main__':
    main()
