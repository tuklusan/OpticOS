#!/usr/bin/env python3
"""Run the repaired M67 image through expanded 20-command real-guest QEMU checks."""
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "qemu-m67-serial.log"
FLOPPY = ROOT / "vms37lab-m67.ima"
DISK = ROOT / "portdisk.img"
CHECKS = (
    ("SHOW CLOCK", b"PIT IRQ0 ticks"),
    ("SHOW CPU", b"CPUID vendor"),
    ("SHOW SERIAL", b"COM1 active="),
    ("SHOW A20", b"A20 enabled and verified."),
    ("SHOW RAM", b"3MiB RAM window alias probe PASS."),
    ("TEST RING3", b"PASS: CPL3 entry, syscall, kernel stack, EXIT."),
    ("TEST DISK", b"PASS: native ATA PIO LBA1/LBA2, signature and checksum."),
    ("TEST USERFAULT", b"PASS: CPL3 write denied, #PF handled, EXIT."),
    ("TEST USERAST", b"PASS: queued AST delivered in ring3 via syscall."),
    ("TEST SCHED", b"PASS: two CPL3 contexts, cooperative switches and exit."),
    ("TEST PREEMPT", b"PASS: PIT preemption, two address spaces, AST IRET trampoline."),
    ("TEST PCB", b"PASS: PCB isolation, private allocated frames, reclaim."),
    ("TEST DEMAND", b"PASS: 4 demand faults, zeroed pages, CR3 isolation, reclaim."),
    ("SHOW VM", b"Demand faults="),
    ("SHOW MEMORY", b"Physical 4K frames free="),
    ("TEST KSTACK", b"PASS: per-PCB TSS.esp0, ring3 traps, guarded kernel stacks."),
    ("TEST EVENT", b"PASS: event AND block/wakeup, OR immediate, 2 CPL3 tasks."),
    ("TEST QIO", b"PASS: QIO 512-byte read, event flag and completion AST."),
    ("TEST USRDESC", b"PASS: CPL3 copy-in QIO descriptor and IDE completion."),
    ("TEST USRTEAR", b"PASS: process exit reclaimed owned QIO and channel."),
    ("TEST ASTDEL", b"PASS: ASTDEL process queue, KAST/IPAST, mode gating, swap/remove, wakeups."),
    ("TEST POSTEF", b"PASS: POSTEF PID/cluster set, AND/OR wake, common sync, backlog."),
    ("TEST MUTEX", b"PASS: MUTEX read/write, pending writers, wait queues, resources, IO mutex, priority."),
    ("TEST MUTEXCPL3", b"PASS: two CPL3 tasks, contested mutex, queued wake, RWAIT/RAVAIL, release."),
    ("TEST HPWD", b"PASS: HPWD CRC and Purdy login hashes, salt, username, match."),
    ("TEST VALIDATE", b"PASS: VALIDATE indexed UAF disk, search, passwords, DEFAULT, privileges."),
    ("TEST LOGINTIME", b"PASS: LIBDAYWK/LIBHOUR VMS epoch and live PC RTC."),
    ("TEST FILEIO", b"PASS: FILEIO real COM1 records, UAF password, process names and close."),
    ("TEST LOGINCMD", b"PASS: LOGINCMD username, DISK, CLI, COMMAND defaults and errors."),
    ("TEST INTERACT", b"PASS: INTERACT real COM1 LOGINOUT prompts, UAF password and welcome."),
    ("TEST SYSTEMLOGIN", b"PASS: SYSTEM authenticated via original VMS UAF record and MANAGER CRC."),
    ("TEST DCLEXIT", b"PASS: DCL EXIT expression, indirect unstack, rundown, batch logout."),
    ("TEST DCLWAIT", b"PASS: DCL WAIT PIT timer, event 31, elapsed guest ticks."),
    ("TEST DCLSTATUS", b"PASS: DCL STATUS severity, symbols, ON ERROR, EXIT guard, YLEVEL."),
    ("TEST DCLIF", b"PASS: DCL IF expression, THEN branch, NOSTAT, invalid syntax."),
    ("TEST DCLINQUIRE", b"PASS: DCL INQUIRE prompt, options, symbol value, AST gating."),
    ("TEST DCLON", b"PASS: DCL ON level, handler, CONTROL Y, status restart."),
    ("TEST DCLIMAGES", b"PASS: 43 original DCL internal image numbers."),
    ("TEST DCLDESCR", b"PASS: DCL descriptor value, offset, flag, term, type and cursor."),
    ("TEST DCLGOTO", b"PASS: DCL GOTO forward label, RFA seek, status and cleanup."),
    ("TEST DCLREAD", b"PASS: DCL READREC IDE command records, skipping, symbols, indirect levels."),
    ("TEST DCLINITIAL", b"PASS: DCL INITIAL live AST, default symbols, RMS blocks and indirect frames."),
)

# M67 stress the already-verified M67 kernel image without weakening any checks.
# Each demand test must reclaim all 512 physical frames before the next cycle.
STRESS_CHECKS = (
    ((("TEST DEMAND", b"PASS: 4 demand faults, zeroed pages, CR3 isolation, reclaim."),
      ("SHOW MEMORY", b"Physical 4K frames free=0x00000200")) * 12)
    + (("TEST PREEMPT", b"PASS: PIT preemption, two address spaces, AST IRET trampoline."),) * 4
    + (("TEST QIO", b"PASS: QIO 512-byte read, event flag and completion AST."),) * 4
    + (("TEST USRTEAR", b"PASS: process exit reclaimed owned QIO and channel."),) * 4
    + (("TEST EVENT", b"PASS: event AND block/wakeup, OR immediate, 2 CPL3 tasks."),) * 4
    + (("TEST SCHED", b"PASS: two CPL3 contexts, cooperative switches and exit."),) * 4
    + (("TEST ASTDEL", b"PASS: ASTDEL process queue, KAST/IPAST, mode gating, swap/remove, wakeups."),) * 12
    + (("TEST POSTEF", b"PASS: POSTEF PID/cluster set, AND/OR wake, common sync, backlog."),) * 12
    + (("TEST MUTEX", b"PASS: MUTEX read/write, pending writers, wait queues, resources, IO mutex, priority."),) * 4
    + (("TEST MUTEXCPL3", b"PASS: two CPL3 tasks, contested mutex, queued wake, RWAIT/RAVAIL, release."),) * 4
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
    deadline = time.monotonic() + 240.0
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
        print("PASS: M67 protected-mode kernel booted to serial prompt", flush=True)
        failures = []
        for command, expected in CHECKS + STRESS_CHECKS:
            offset = len(log)
            for char in (command + "\r").encode("ascii"):
                proc.stdin.write(bytes((char,)))
                proc.stdin.flush()
                time.sleep(0.02)
            if command == "TEST FILEIO":
                for prompt, answer in ((b"FILEIO INPUT> ", b"labuser\r"),
                                       (b"FILEIO PASSWORD> ", b"password\r")):
                    if not wait_for(prompt, 15.0, offset):
                        raise RuntimeError(f"{command}: missing {prompt!r}")
                    for char in answer:
                        proc.stdin.write(bytes((char,)))
                        proc.stdin.flush()
                        time.sleep(0.02)
            if command == "TEST INTERACT":
                for prompt, answer in ((b"Username: ", b"labuser\r"),
                                       (b"Password: ", b"password\r")):
                    if not wait_for(prompt, 15.0, offset):
                        raise RuntimeError(f"{command}: missing {prompt!r}")
                    for char in answer:
                        proc.stdin.write(bytes((char,)))
                        proc.stdin.flush()
                        time.sleep(0.02)
            if command == "TEST SYSTEMLOGIN":
                for prompt, answer in ((b"Username: ", b"SYSTEM\r"),
                                       (b"Password: ", b"MANAGER\r")):
                    if not wait_for(prompt, 15.0, offset):
                        raise RuntimeError(f"{command}: missing {prompt!r}")
                    for char in answer:
                        proc.stdin.write(bytes((char,)))
                        proc.stdin.flush()
                        time.sleep(0.02)
            if not wait_for(b"PORTLAB> ", 20.0, offset):
                raise RuntimeError(f"{command} never returned to guest prompt (QEMU exit {proc.poll()})")
            if expected not in log[offset:]:
                failures.append(command)
                print(f"FAIL: {command}: wanted {expected!r}", flush=True)
                print("Guest output:", log[offset:].decode("ascii", "replace")[-1200:], flush=True)
            else:
                print(f"PASS: {command}", flush=True)
        if failures:
            raise RuntimeError(f"{len(failures)} failed guest checks: {', '.join(failures)}")
        # Real LOGINOUT authentication followed by live DCL command input/output.
        def transmit(line):
            for ch in (line + chr(13)).encode("ascii"):
                proc.stdin.write(bytes((ch,)))
                proc.stdin.flush()
                time.sleep(0.02)
        def expect(text, after, timeout=20.0):
            if not wait_for(text, timeout, after):
                raise RuntimeError("live LOGIN/DCL missing %r; tail %r" %
                                   (text, log[after:].decode("ascii", "replace")[-500:]))
        start = len(log)
        transmit("LOGIN")
        expect(b"Username: ", start)
        start = len(log)
        transmit("SYSTEM")
        expect(b"Password: ", start)
        start = len(log)
        transmit("MANAGER")
        expect(b"DCL source commands active:", start)
        expect(b"$ ", start)
        print("PASS: real SYSTEM/MANAGER login reached DCL command prompt", flush=True)
        start = len(log)
        transmit("SHOW SYMBOL $STATUS")
        expect(b'$STATUS = "1"', start)
        expect(b"$ ", start)
        print("PASS: live DCL INITIAL reserved status symbol", flush=True)
        start = len(log)
        transmit('INQUIRE/GLOBAL DEST "Which place"')
        expect(b"Which place: ", start)
        start = len(log)
        transmit("Mars")
        expect(b"$ ", start)
        start = len(log)
        transmit("SHOW SYMBOL DEST")
        expect(b'DEST = "Mars"', start)
        expect(b"$ ", start)
        print("PASS: live DCL INQUIRE stored and read back global string", flush=True)
        start = len(log)
        transmit("@LAB.COM")
        expect(b'DEST = "Mars"', start)
        next_record = log.find(b'DEST = "Mars"', start) + len(b'DEST = "Mars"')
        expect(b'DEST = "Mars"', next_record)
        expect(b"$ ", next_record)
        print("PASS: DCL @LAB.COM read two genuine IDE procedure records, returned to parent level", flush=True)
        start = len(log)
        transmit("ON ERROR THEN EXIT")
        expect(b"%DCL-E-ONLEVL", start)
        expect(b"$ ", start)
        print("PASS: direct DCL ON correctly rejects level-zero handler setup", flush=True)
        start = len(log)
        transmit("SET HOST 0")
        expect(b"DECnet remote terminal service not implemented", start)
        expect(b"$ ", start)
        start = len(log)
        transmit("LOGOUT")
        expect(b"Process logged out", start)
        expect(b"PORTLAB> ", start)
        print("PASS: live DCL LOGOUT returned to parent monitor", flush=True)
        print(f"PASS: actual QEMU boot + {len(CHECKS)} baseline and {len(STRESS_CHECKS)} stress guest commands plus authenticated DCL session", flush=True)
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
