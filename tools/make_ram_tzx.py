#!/usr/bin/env python3
"""Package a RAM-resident 48K OpticBASIC image as a self-booting TZX tape.

Standard-speed Spectrum header/data blocks only.  This file deliberately
does not need third-party Python packages or a copyrighted Sinclair ROM.
"""
from __future__ import annotations

import argparse
import pathlib
import struct

LOAD_ADDR = 0x6000
CLEAR_TO = LOAD_ADDR - 1
MAX_IMAGE = 0xE900 - LOAD_ADDR - 1024   # leave room for an OpticBASIC program


def basic_line(number: int, statement: bytes) -> bytes:
    data = statement + b"\r"
    return struct.pack(">H", number) + struct.pack("<H", len(data)) + data


def loader_program() -> bytes:
    # Tokens: CLEAR=FD, VAL=B0, LOAD=EF, CODE=AF, RANDOMIZE=F9, USR=C0.
    # VAL "digits" avoids the ROM's floating-point literal encoding.
    return b"".join((
        basic_line(10, b'\xfd \xb0 "24575"'),
        basic_line(20, b'\xef "" \xaf'),
        basic_line(30, b'\xf9 \xc0 \xb0 "24576"'),
    ))


def header(kind: int, name: str, length: int, arg1: int, arg2: int) -> bytes:
    label = name.encode("ascii")
    if len(label) > 10:
        raise ValueError("Tape name is longer than 10 ASCII characters")
    return struct.pack("<B10sHHH", kind, label.ljust(10, b" "), length, arg1, arg2)


def block(payload: bytes, flag: int, pause_ms: int = 1000) -> bytes:
    raw = bytes((flag,)) + payload
    checksum = 0
    for byte in raw:
        checksum ^= byte
    raw += bytes((checksum,))
    if len(raw) > 65535:
        raise ValueError("Standard-speed TZX block is too large")
    return b"\x10" + struct.pack("<HH", pause_ms, len(raw)) + raw


def make_tzx(image: bytes) -> bytes:
    if not image:
        raise ValueError("Empty RAM binary")
    if len(image) >= MAX_IMAGE:
        raise ValueError("RAM image leaves too little room for OpticBASIC")
    basic = loader_program()
    return b"".join((
        b"ZXTape!\x1a\x01\x14",
        block(header(0, "OPTIC LOAD", len(basic), 10, len(basic)), 0),
        block(basic, 0xFF),
        block(header(3, "OPTIC RAM", len(image), LOAD_ADDR, 0x8000), 0),
        block(image, 0xFF),
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=pathlib.Path, help="assembled .bin image")
    parser.add_argument("output", type=pathlib.Path, help="output .tzx path")
    args = parser.parse_args()
    tape = make_tzx(args.input.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(tape)
    print(f"Wrote {args.output}: {len(tape)} bytes, bootstraps via Sinclair ROM")


if __name__ == "__main__":
    main()
