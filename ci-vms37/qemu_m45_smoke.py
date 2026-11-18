#!/usr/bin/env python3
"""Run the exact M46 floppy on a real QEMU system emulator, via COM1."""
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "qemu-m46-serial.log"
FLOPPY = ROOT / "vms37lab-m46.ima"
DISK = ROOT / "portdisk.img"
CHECKS = (
    ("SHOW CLOCK", b"PIT IRQ0 ticks"),
    ("SHOW CPU", b"CPUID vendor"),
    ("SHOW SERIAL", b"COM1 active="),
    ("SHOW A20", b"A20 enabled and verified."),
    ("SHOW RAM", b"3MiB RAM window alias probe PASS."),
    ("TEST RING3", b"PASS: CPL3 entry, syscall, kernel stack, EXIT."),
    ("TEST DISK", b"PASS: native ATA PIO LBA1/LBA2, signature and checksum."),
)

def run():
    qemu = shutil.which("qemu-system-i386")
    if not qemu:
        raise RuntimeError("qemu-system-i386 not installed")
    args = [qemu, "-display", "none", "-monitor", "none", "-serial", "stdio",
            "-m", "128", "-boot", "a", "-no-reboot", "-accel", "tcg",
            "-drive", f"if=floppy,format=raw,file={FLOPPY},snapshot=on",
            "-drive", f"if=ide,index=0,media=disk,format=raw,file={DISK},snapshot=on"]
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    log = bytearray()
    deadline = time.monotonic() + 120.0
    def wait_for(needle, seconds, offset=0):
        until = min(time.monotonic() + seconds, deadline)
        while time.monotonic() < until:
            if needle in log[offset:]:
                return True
            if proc.poll() is not None:
                return False
            ready, _, _ = select.select([proc.stdout], [], [], min(0.5, max(0.0, until-time.monotonic())))
            if ready:
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    return False
                log.extend(chunk)
        return needle in log[offset:]
    try:
        if not wait_for(b"PORTLAB> ", 45.0):
            raise RuntimeError("no guest PORTLAB serial prompt (QEMU exit %s)" % proc.poll())
        print("PASS: M46 protected-mode kernel booted to serial prompt", flush=True)
        for command, expected in CHECKS:
            offset = len(log)
            for char in (command + "\r").encode("ascii"):
                proc.stdin.write(bytes((char,)))
                proc.stdin.flush()
                time.sleep(0.02)
            if not wait_for(expected, 12.0, offset):
                if command == "TEST DISK" and proc.poll() is None:
                    for char in b"SHOW DISK\r":
                        proc.stdin.write(bytes((char,)))
                        proc.stdin.flush()
                        time.sleep(0.02)
                    wait_for(b"ATA PIO reads", 5.0, len(log)-1)
                    wait_for(b"PORTLAB> ", 5.0, len(log)-1)
                raise RuntimeError(f"{command} did not yield {expected!r} (QEMU exit {proc.poll()})")
            if not wait_for(b"PORTLAB> ", 12.0, offset):
                raise RuntimeError(f"{command} did not return to prompt")
            print(f"PASS: {command}", flush=True)
        print("PASS: actual M46 QEMU boot + seven guest commands", flush=True)
        return 0
    except (RuntimeError, BrokenPipeError) as exc:
        print("FAIL:", exc, file=sys.stderr, flush=True)
        print("Serial tail:", log[-1800:].decode("ascii", "replace"), file=sys.stderr, flush=True)
        return 1
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if proc.stdout:
            log.extend(proc.stdout.read(32768))
        OUT.write_bytes(log)
        print(f"Saved QEMU serial transcript to {OUT}", flush=True)

if __name__ == "__main__":
    sys.exit(run())
