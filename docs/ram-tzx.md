# Experimental RAM/TZX build for a stock 48K ZX Spectrum

This is a separate build, not a replacement for the original OpticOS ROM.
The stock Sinclair ROM loads a normal BASIC+CODE tape, then the relocated
OpticBASIC engine takes over in RAM.

## Build and run

Requires pasmo 0.5.3 and Python 3.

    make ram

Output: build/OpticOS-RAM.tzx, with accompanying BIN and symbol map.

Select a standard 48K Spectrum, enter LOAD "" and start playback.  The
autostarting Sinclair BASIC loader does the following:

    10 CLEAR VAL "24575"
    20 LOAD "" CODE
    30 RANDOMIZE USR VAL "24576"

On real hardware convert the TZX to audio or play it using suitable tape
hardware. TZX is a tape image, not a sound waveform.

## Memory map

| Address range | Purpose |
| --- | --- |
| 0000-3FFF | Original Sinclair ROM (unmodified) |
| 4000-5AFF | ZX display and attributes |
| 5B00-5DFF | OpticBASIC variables/editor (overwrites old BASIC program) |
| 6000 onward | RAM executable, with packed built-in font |
| After executable | OpticBASIC program/variables/string heap |
| E900-FC00 | Interpreter workspace and stack |
| FDFD-FDFF | IM2 JP ISR trampoline |
| FE00-FF00 | Full 257-byte IM2 interrupt vector table |

The BASIC loader CLEARs to 5FFF before loading. The RAM boot does NOT
probe/clear RAM, as the original ROM version does. It installs IM2 rather
than attempting to write to the Sinclair interrupt handler at 0038. All
ROM-style restart calls are rewritten to direct in-program calls.

## Limitations

- 48K hardware only. A 16K machine cannot run code at 6000.
- This is an experimental build. Assembly and TZX validation do not
  establish correct behavior on a physical Spectrum. Real tape and TV
  testing are required.
- The original ROM's legacy Sinclair BASIC/game-tape loader is not
  available in this RAM build. It relies on replacing published ROM
  entry-point addresses. Reset the Spectrum to load ordinary games.
- OpticBASIC SAVE/LOAD/VERIFY use software-generated tape pulses, not
  emulator ROM-specific fast-tape traps. Disable tape acceleration if
  emulators try to hook the relocated routines.
- OpticBASIC machine-code loads and POKE/CALL can overwrite its RAM code.
  Code must be placed outside the interpreter and its workspace.
- Reset restores the ordinary stock Sinclair ROM.

## Implementation

The RAM source generator expands the original includes, drops ROM-only
fixed address ORGs, translates RST instructions to application-local
CALLs, and gives long branches to code expanded by that translation.
It also changes NEW to restart OpticBASIC, locates program memory after
the executable, loads native OpticBASIC programs without first copying
through the executable, and sets up a real RAM-resident IM2 ISR.

The original source and 16K ROM build are unchanged.

The TZX generator writes standard-speed BASIC and CODE tape blocks with
XOR checksums. CI runs an assembler build and TZX-framing unit tests and
uploads the assembled tape as a GitHub Actions artifact.
