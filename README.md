# OpticOS — RAM edition for the ZX Spectrum 48K

[![Build RAM TZX](https://github.com/tuklusan/OpticOS/actions/workflows/ram-tzx.yml/badge.svg)](https://github.com/tuklusan/OpticOS/actions/workflows/ram-tzx.yml)
[![GitHub release](https://img.shields.io/github/v/release/tuklusan/OpticOS)](https://github.com/tuklusan/OpticOS/releases)
[![Downloads](https://img.shields.io/github/downloads/tuklusan/OpticOS/total)](https://github.com/tuklusan/OpticOS/releases)

**OpticOS RAM** is a TZX-loadable, RAM-resident AI-generated version of **OpticOS / OpticBASIC** for a standard **48K Sinclair ZX Spectrum**. It runs with the factory Sinclair ROM still installed: **no replacement ROM, modified emulator ROM, or ROM switcher is needed**.

This edition is **derived from the original [ROM-based OpticOS by Optica Technology Design](https://github.com/brixham99/OpticOS)**. The original project is a clean-room 16K replacement ROM containing the structured, line-number-free OpticBASIC language and 64-column display. This fork relocates that software into a normal RAM program and packages it as a tape image. The original ROM source and build remain available.

## Download the RAM/TZX edition

**[Download OpticOS-RAM.tzx (latest release)](https://github.com/tuklusan/OpticOS/releases/latest/download/OpticOS-RAM.tzx)**

Or browse the **[Releases page](https://github.com/tuklusan/OpticOS/releases)** and select `OpticOS-RAM.tzx` under **Assets**.

### Run it

1. Start a standard **ZX Spectrum 48K** with its **original Sinclair ROM**, on hardware or in an emulator.
2. Load the downloaded `OpticOS-RAM.tzx` as a tape image.
3. At the Sinclair BASIC prompt, type `LOAD ""` and play the tape. (On real hardware, use a suitable TZX-to-audio player or tape interface.)
4. The tape's BASIC autoloader loads OpticOS at **24576 (`$6000`)** and starts OpticBASIC.

The autoloader performs the equivalent of:

```basic
10 CLEAR VAL "24575"
20 LOAD "" CODE
30 RANDOMIZE USR VAL "24576"
```

When OpticBASIC starts, it uses the **`]` prompt**. Type statements directly, or enter a multi-line program with `AUTO`, finish with a blank line, and execute it with `RUN`.

A quick test at the OpticBASIC prompt:

```text
] PRINT "HELLO FROM RAM"
```

## What it provides

OpticOS retains the original OpticBASIC environment, including:

- A **64-column display** using the compact 4×8 font, with screen colours and graphics commands.
- **Structured BASIC without line numbers**, with named procedures/functions, loops, conditional blocks, arrays and strings.
- A ZX-inspired **line editor**, plus `AUTO`, `LIST`, `RUN` and `NEW`.
- Arithmetic, string operations, `PLOT`, `DRAW`, `BEEP` and machine-code access.
- Native OpticBASIC **SAVE/LOAD** through software-generated tape pulses.

These features come from the original implementation; **not every command has been re-tested in the RAM edition**.

## RAM edition versus the original ROM edition

| | This fork: RAM/TZX | Original OpticOS |
|---|---|---|
| Installation | Load a TZX into stock 48K Spectrum RAM | Replace the Spectrum's 16K ROM |
| Execution | Relocated interpreter starting at `$6000` | Interpreter runs from `$0000–$3FFF` |
| Interrupts | RAM-resident IM2 handler | ROM-resident interrupt handling |
| OpticBASIC | Yes | Yes |
| Ordinary Sinclair BASIC/game tape compatibility inside OpticOS | **No** — reset to Sinclair ROM first | Original ROM edition has a compatibility loader |
| Build | `make ram` | `make` |
| Main output | `build/OpticOS-RAM.tzx` | `build/opticos.rom` |

The RAM adapter converts fixed ROM origins and restart instructions into relocatable calls, includes the font in the RAM image, and keeps OpticBASIC program storage clear of the executable. The original 16K ROM build is **not replaced**.

## Build from source

Requires **Pasmo** (Z80 assembler), Python 3, and a C compiler for the headless Z80 test rig.

```sh
make ram                         # build/OpticOS-RAM.tzx
python3 -m unittest discover -s tools -p 'test_ram_tzx.py'
python3 tools/rig/test_ram.py   # RAM boot and interpreter smoke tests
```

To build the **original 16K ROM**, use `make` instead.

GitHub Actions builds and tests the RAM image on changes to `main`. Publishing a GitHub Release also builds the TZX and attaches it to the release's assets.

## Testing and limitations

The automated Z80 rig has passed RAM startup, screen/banner, IM2 setup, direct `PRINT`, stored `AUTO`/`RUN`, `NEW`, and a software-timed tape SAVE/LOAD round-trip. The TZX block framing and checksums have also been tested.

**Experimental hardware status:** Physical 48K hardware and the complete stock-ROM tape-bootstrap path have **not yet been verified end to end**. The test rig is useful, but it is not a CRT television and a battered cassette deck.

Other limits:

- A **48K Spectrum** is required; a 16K machine will not work.
- Loading ordinary Spectrum games or Sinclair BASIC tapes **inside** RAM OpticBASIC is unsupported. Reset the machine to regain the original Sinclair ROM environment.
- Custom tape routines may need emulator tape traps/acceleration disabled.
- Avoid overwriting the RAM interpreter or its workspace using `POKE`, `CALL` or machine-code loads.

For technical details, see the **[RAM memory map and implementation notes](docs/ram-tzx.md)**.

## Origin, documentation and licence

**Original OpticOS:** [brixham99/OpticOS](https://github.com/brixham99/OpticOS), copyright © 2026 Optica Technology Design. This project is a derivative RAM port maintained in [tuklusan/OpticOS](https://github.com/tuklusan/OpticOS), not a change submitted upstream.

The original README, including the ROM build, phase history, example program, editor guide, screenshots, and ROM layout, is preserved as **[Original ROM documentation](docs/original-rom-readme.md)**. The existing [OpticOS user manual](docs/manual/OpticOS_User_Manual.pdf), [specification](docs/spec.md), and [examples](examples) describe the original ROM system; RAM-specific differences and limits above take precedence.

Code remains under the **MIT licence**; artwork and documentation are under **CC BY 4.0**, as described in [LICENSE](LICENSE). The upstream copyright and attribution are retained.
