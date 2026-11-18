#!/usr/bin/env python3
"""Confirm the exact PC boot image follows SYSINIT and does not skip missing services."""
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

root=Path(__file__).resolve().parent
serial=root/"qemu-m70-serial.log"
guest=root/"vms37lab-m70.ima"
disk=root/"portdisk.img"
qemu=shutil.which("qemu-system-i386")
if not qemu:
    raise SystemExit("qemu-system-i386 not installed")
args=[qemu,"-display","none","-monitor","none","-serial","stdio",
      "-m","128","-boot","a","-no-reboot","-accel","tcg",
      "-drive",f"if=floppy,format=raw,file={guest},snapshot=on",
      "-drive",f"if=ide,index=0,media=disk,format=raw,file={disk},snapshot=on"]
marker=b"System initialization stopped: native RMS and F11ACP system disk services are not ready."
data=bytearray()
proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT,bufsize=0)
try:
    until=time.monotonic()+40.0
    while time.monotonic()<until and marker not in data:
        if proc.poll() is not None:break
        ready,_,_=select.select([proc.stdout],[],[],0.25)
        if ready:
            piece=os.read(proc.stdout.fileno(),4096)
            if not piece:break
            data.extend(piece)
    if marker not in data:
        raise RuntimeError("required SYSINIT stop message was absent; output="+
                           data[-1000:].decode("ascii","replace"))
    print("PASS: BIOS boot entered single native SYSINIT startup path",flush=True)
    if b"PORTLAB> " in data or b"Username:" in data:
        raise RuntimeError("guest reached development monitor or LOGIN before SYSINIT completed")
    proc.stdin.write(b"LOGIN\r")
    proc.stdin.flush()
    until=time.monotonic()+1.2
    while time.monotonic()<until:
        ready,_,_=select.select([proc.stdout],[],[],0.2)
        if ready:
            piece=os.read(proc.stdout.fileno(),4096)
            if not piece:break
            data.extend(piece)
    if b"PORTLAB> " in data or b"Username:" in data:
        raise RuntimeError("unsupported bypass accepted LOGIN after SYSINIT stop")
    print("PASS: no monitor, no separate QEMU boot path, and no premature LOGIN",flush=True)
    print("PASS: M70 SYSBOOT console printed the real missing-service failure",flush=True)
except Exception as err:
    print("FAIL:",err,file=sys.stderr,flush=True)
    sys.exit(1)
finally:
    proc.terminate()
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    if proc.stdout:
        data.extend(proc.stdout.read(32768))
    serial.write_bytes(data)
    print("Serial:",data.decode("ascii","replace")[-800:],flush=True)
