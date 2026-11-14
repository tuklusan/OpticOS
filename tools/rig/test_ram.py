#!/usr/bin/env python3
"""Boot and exercise the RAM variant on the project's Z80 hardware rig.

No Sinclair ROM binary is required: execution starts at $6000 as it does
immediately after the ordinary ROM has loaded the TZX's CODE block.
"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rig import Spectrum

BIN = ROOT / "build" / "opticos_ram.bin"
image = BIN.read_bytes()
font = (ROOT / "font" / "font4x8.bin").read_bytes()
s = Spectrum(bytes(16384))
s.load(0x6000, image)
s.setregs(PC=0x6000, SP=0x5FF0)
s.frame(200)

rows = [row.rstrip("\x7f").rstrip() for row in s.text_rows(font)]
print("Boot screen rows 2/3/5:", repr([rows[2], rows[3], rows[5]]))
assert rows[2] == "OpticOS (c) 2026 Optica Technology Design", rows[2]
assert rows[3] == "OpticBASIC v1.0.3", rows[3]
assert rows[5] == "]", rows[5]
assert s.dpeek(0x5CB4) == 0xFFFF, "RAM size detection"
assert s.dpeek(0x5CB2) == 0xFC00, "RAMTOP placement"
assert s.regs()["IM"] == 2, "RAM ISR not enabled"
assert s.dpeek(0xFDFE) >= 0x6000, "IM2 ISR trampoline invalid"
assert s.peek(0xFDFD) == 0xC3, "missing IM2 JP instruction"
assert s.block(0xFE00, 257) == bytes([0xFD])*257, "invalid IM2 vector table"
assert s.block(0x6000, len(image)) == image, "the running engine modified its own code"

s.type('print "RAM OK"\n')
s.frame(100)
rows = [row.rstrip("\x7f").rstrip() for row in s.text_rows(font)]
print("Printed RAM test:", [x for x in rows if "RAM" in x])
assert any("RAM OK" in x for x in rows), "OpticBASIC PRINT failed after loading"
s.type("AUTO\n")
s.type("PRINT 40+2\n")
s.type("\n")  # blank line ends AUTO
s.type("RUN\n")
s.frame(80)
rows = [row.rstrip("\x7f").rstrip() for row in s.text_rows(font)]
print("Program RUN output:", [x for x in rows if "42" in x])
assert any(x.strip() == "42" for x in rows), "Stored OpticBASIC program failed"

s.type("NEW\n")
s.frame(80)
assert s.block(0x6000, len(image)) == image, "NEW clobbered the RAM executable"
assert s.regs()["IM"] == 2, "NEW did not reinstall IM2"

# Directly exercise the relocated software SAVE/LOAD primitives on a genuine
# EAR/MIC pulse feed.  In contrast to tape traps, this uses real timings.
import re
from rig import decode_pulses, NOTOGGLE
symbols = {}
for line in (ROOT / "build" / "opticos_ram.sym").read_text().splitlines():
    m = re.match(r"(\w+)\s+EQU\s+0?([0-9A-F]+)H", line)
    if m:
        symbols[m.group(1)] = int(m.group(2), 16)
assert "SA_BYTES" in symbols and "LD_BYTES" in symbols, "RAM symbols missing"

payload = bytes((i * 73 + 11) & 255 for i in range(80))
s.load(0xD000, payload)
s.mic_start(3)
s.call(symbols["SA_BYTES"], IX=0xD000, DE=len(payload),
       AF=0xFF00, IFF1=1, IFF2=1, IM=2, limit=900_000_000)
pulses = s.mic_pulses()[1:]
expected_parity = 0xFF
for b in payload:
    expected_parity ^= b
expected = b"\xff" + payload + bytes((expected_parity,))
decoded = decode_pulses(pulses)
assert decoded and decoded[0] == expected, "SA_BYTES parity/pulse regression"

loaded = Spectrum(bytes(16384))
loaded.load(0x6000, image)
loaded.setregs(PC=0x6000, SP=0x5FF0)
loaded.frame(200)
loaded.tape([NOTOGGLE | 35000] + pulses + [NOTOGGLE | 3500000])
result = loaded.call(symbols["LD_BYTES"], IX=0xD000, DE=len(payload),
                     AF=0xFF01, IFF1=1, IFF2=1, IM=2, limit=900_000_000)
assert result["AF"] & 1, "LD_BYTES reported an error"
assert loaded.block(0xD000, len(payload)) == payload, "LD_BYTES data mismatch"
print("PASS: RAM boot, IM2, PRINT, AUTO/RUN, NEW, and software tape round-trip")

