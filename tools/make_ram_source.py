#!/usr/bin/env python3
"""Generate a packed, RAM-resident OpticBASIC assembly source from the ROM tree.

The ROM sources are left untouched.  This is deliberately a source-level
relocation: copying a compiled ROM to RAM would retain ROM-only RST/IM1 entry
points and wipe out the application during its cold-start memory test.
"""
from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ORG = 0x6000
RST = {8: "err_rst", 0x10: "print_a", 0x18: "tk",
       0x20: "skip1", 0x28: "fu_run", 0x30: "ev_int"}

RAM_BOOT = """boot:   di
        xor a
        out ($FE),a             ; border and beeper to zero
        ; A ROM cold start zeroed RAM, but we must only clear variables.
        ; Clear $5B00-$5FFF (Sinclair BASIC is no longer running).
        ld hl,$5B00
        ld (hl),0
        ld de,$5B01
        ld bc,$04FF
        ldir
        ; Never probe/clear RAM: the code executing now lives in it!
        ; The user-space application requires a full 48K ZX Spectrum.
        ld hl,$FFFF
        ld (P_RAMT),hl
        ld hl,$FC00             ; reserved upper RAM above the app stack
        ld (RAMTOP),hl
        ld sp,hl
        inc hl
        ld (UDG),hl
        ; A full 257-byte IM2 table handles any interrupting data-bus byte.
        ; Every vector points at $FDFD, a JP trampoline outside our stack.
        ld hl,$FE00
        ld (hl),$FD
        ld de,$FE01
        ld bc,256
        ldir
        ld a,$C3               ; JP ISR at $FDFD
        ld ($FDFD),a
        ld hl,ISR
        ld ($FDFE),hl
        ld a,$FE
        ld i,a
        ld iy,ERR_NR"""

def checked_sub(pattern: str, repl: str, s: str, label: str, flags: int = 0) -> str:
    changed, n = re.subn(pattern, lambda m: repl, s, count=1, flags=flags)
    if n != 1:
        raise ValueError(f"Cannot locate exactly one {label} in upstream source")
    return changed


def read_with_ram_patches(path: pathlib.Path) -> str:
    body = path.read_text(encoding="utf-8")
    if path.name == "boot.asm":
        body = checked_sub(
            r"^boot:\s+out \(\$FE\),a.*?^\s*ld iy,ERR_NR[^\n]*",
            RAM_BOOT, body, "ROM cold-start RAM test",
            re.MULTILINE | re.DOTALL,
        )
        body = checked_sub(r"^\s*im 1\b", "        im 2", body,
                           "IM 1 activation", re.MULTILINE)
    elif path.name == "sysvars.inc":
        body = checked_sub(r"^OPROG\s+equ\s+\$5DF0\b.*$",
                           "OPROG    equ ram_program ; follows packed RAM code",
                           body, "program start", re.MULTILINE)
        body = checked_sub(r"^FONT\s+equ\s+\$3E80\b.*$",
                           "FONT     equ ram_font ; packed font within image",
                           body, "font start", re.MULTILINE)
    elif path.name == "legacy.asm":
        body = checked_sub(
            r"^lg_prog:.*?^m_leg_e1:",
            """lg_prog:
        ; The ROM's Sinclair BASIC shim cannot safely execute arbitrary
        ; legacy loaders from inside a RAM program.  Keep OpticBASIC LOAD.
        xor a
        ld (LG_WANT),a
        call lg_fetch
        ld hl,(OPROG-4)         ; native tape signature "OB"
        ld de,$424F
        or a
        sbc hl,de
        jp z,ob_load
        call err_rst
        defb ERR_LEG
m_leg_e1:""",
            body, "legacy load entry", re.MULTILINE | re.DOTALL,
        )
        body = checked_sub(
            r"^lf_ok:\s+ld de,\(HDRBUF\+11\)[^\n]*",
            """lf_ok:  ld de,(HDRBUF+11)       ; length
        ; Protect RAM-resident code and the interpreter's workspace.
        ; Native programs load directly at OPROG-4; no temporary copy
        ; across the executable at $6000 is permitted.
        ld a,(HDRBUF)
        or a
        jr nz,lf_sizeok
        push de
        ld hl,OPROG-4
        add hl,de
        ld de,(HTOP)
        or a
        sbc hl,de
        pop de
        jp nc,err_nomem
lf_sizeok:""",
            body, "tape-load capacity check", re.MULTILINE,
        )
        body = checked_sub(r"^\s*ld ix,LEGPROG\b",
                           "        ld ix,OPROG-4",
                           body, "native-program load address", re.MULTILINE)
    elif path.name == "tape.asm":
        body = checked_sub(
            r"^ob_load:.*?(?=^\s*ld hl,\(HDRBUF\+13\))",
            """ob_load:
        ; Native blocks already loaded at OPROG-4, not LEGPROG.
        ; Their 4-byte signature is followed by the program and sentinel.
        ld bc,(HDRBUF+11)
        ld hl,OPROG-5
        add hl,bc
        ex de,hl                ; DE = last byte of program (PEND)
        call ws_ld
""",
            body, "native-program relocation", re.MULTILINE | re.DOTALL,
        )
    return body


def flatten(path: pathlib.Path, chain: tuple[pathlib.Path, ...] = ()):
    if path in chain:
        raise ValueError(f"Recursive assembly include: {path}")
    body = read_with_ram_patches(path)
    yield f"\n; ===== BEGIN {path.relative_to(ROOT)} =====\n"
    for line in body.splitlines(keepends=True):
        inc = re.match(r'^\s*include\s+"([^"]+)"\s*(?:;.*)?$', line, re.I)
        if inc:
            yield from flatten((path.parent / inc.group(1)).resolve(), chain + (path,))
        else:
            yield line
    yield f"\n; ===== END {path.relative_to(ROOT)} =====\n"


def convert_assembly(text: str) -> str:
    out = []
    orgs = 0
    replacements = 0
    current_file = ""
    timing_modules = {"src/edge.asm", "src/load.asm", "src/save.asm",
                      "src/sound.asm", "src/keyboard.asm"}
    for line in text.splitlines(keepends=True):
        if line.startswith("; ===== BEGIN "):
            current_file = line[len("; ===== BEGIN "):].split(" =====")[0]
        code, semi, comment = line.partition(";")
        if re.match(r"^\s*org\s+", code, re.I):
            orgs += 1
            if orgs == 1:
                line = "        org $6000 ; user RAM entry point\n"
            elif re.match(r"^\s*org\s+FONT\s*$", code, re.I):
                # The packed font reader INC E assumes 8-byte pairs do not
                # cross a page boundary.
                line = "        org (($ + 7) & $FFF8)\nram_font:\n"
            else:
                line = "; removed ROM-only fixed ORG: " + line
            out.append(line)
            continue

        def change(m: re.Match[str]) -> str:
            nonlocal replacements
            operand = m.group(1)
            addr = int(operand[1:], 16) if operand.startswith("$") else int(operand, 10)
            replacements += 1
            if addr == 0:
                # NEW must restart OpticOS in RAM, not invoke Sinclair reset.
                return "jp RESET"
            if addr not in RST:
                raise ValueError(f"Unknown ROM restart 0x{addr:02x} in {line.rstrip()}")
            return "call " + RST[addr]

        code = re.sub(r"\brst\s+(\$[0-9a-fA-F]+|\d+)\b", change, code, flags=re.I)
        # RST->CALL expands branches by 2 bytes. Most of the ROM used
        # tight JR reachability; use absolute JP in non-timing modules.
        # Keep exact short branch timing in the tape and beeper loops.
        if current_file not in timing_modules:
            code = re.sub(r"\bjr\b", "jp", code, flags=re.I)
        out.append(code + semi + comment if semi else code)
    if orgs < 8 or replacements < 90:
        raise ValueError(f"Unexpected source layout: {orgs} ORGs / {replacements} RSTs")
    result = "".join(out)
    result += """
; RAM code ends here.  Four writable bytes immediately following the
; loaded binary hold the OpticBASIC tape signature when saving/loading.
ram_image_end:
ram_program equ ram_image_end+4
"""
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", default=str(ROOT / "build" / "opticos_ram.asm"))
    args = p.parse_args()
    dst = pathlib.Path(args.output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = "".join(flatten(SRC / "opticos.asm"))
    dst.write_text(convert_assembly(src), encoding="utf-8")
    print(f"Generated {dst} from unchanged ROM sources")


if __name__ == "__main__":
    main()
