#!/usr/bin/env python3
"""Check the single PC boot mounts ODS-2 then fails the real SYS.EXE lookup."""
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

root=Path(__file__).resolve().parent
serial=root/"qemu-m75-serial.log"
guest=root/"vms37lab-m75.ima"
disk=root/"portdisk.img"
qemu=shutil.which("qemu-system-i386")
if not qemu:
    raise SystemExit("qemu-system-i386 not installed")
args=[qemu,"-display","none","-monitor","none","-serial","stdio",
      "-m","128","-boot","a","-no-reboot","-accel","tcg",
      "-drive",f"if=floppy,format=raw,file={guest},snapshot=on",
      "-drive",f"if=ide,index=0,media=disk,format=raw,file={disk},snapshot=on"]
marker=b"-F-Unable to locate SYS.EXE"
with guest.open("rb") as f:
    boot=f.read(512)
    stage2=f.read(512)
at=boot.find(b"VMSB")
if not (0<at<500 and boot.rfind(b"VMSB")==at):
    raise RuntimeError("BOOTBLOCK disk metadata absent")
blocks=int.from_bytes(boot[at+4:at+6],"little")
start=int.from_bytes(boot[at+6:at+8],"little")
if start!=1 or not 1<=blocks<=251 or stage2[:2]!=bytes((0xfc,0x31)):
    raise RuntimeError("BOOTBLOCK size/LBN/entry mismatch")
if disk.stat().st_size!=8064*512:
    raise RuntimeError("Files-11 disk is shorter than declared volume")
print(f"PASS: BOOTBLOCK reads {blocks} physical sectors from recorded first LBN",flush=True)
# The host prepares a genuine Files-11 volume, not a pretend SYS.EXE.
with disk.open("rb") as f:
    f.seek(12 * 512)
    index_bitmap=f.read(512)
    f.seek(22 * 512)
    sysexe_header=f.read(512)
    f.seek(27 * 512)
    mfd=f.read(512)
    f.seek(30 * 512)
    sysexe_data=f.read(512)
if (index_bitmap[:2] != b"\xff\x03" or
    sysexe_header[8:12] != b"\x0a\x00\x0a\x00" or
    sysexe_header[76:88] != b"SYSEXE.DIR;1" or
    b"SYSEXE.DIR" not in mfd or
    sysexe_data[:2] != b"\xff\xff"):
    raise RuntimeError("SYSBOOT disk lacks the real Files-11 SYSEXE directory")
print("PASS: Files-11 index, MFD, and SYSEXE directory are present",flush=True)
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
        raise RuntimeError("required SYS.EXE lookup failure was absent; output="+
                           data[-1000:].decode("ascii","replace"))
    if b'not a valid Files-11 ODS-2 volume' in data:
        raise RuntimeError('SYSBOOT rejected the initialized Files-11 volume')
    print("PASS: original single PC boot reached genuine SYS.EXE lookup after ODS-2 directory",flush=True)
    if b"PORTLAB> " in data or b"Username:" in data:
        raise RuntimeError("guest reached development monitor or LOGIN before SYSBOOT completed")
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
        raise RuntimeError("unsupported bypass accepted LOGIN after missing SYS.EXE")
    print("PASS: no monitor, no separate QEMU boot path, and no premature LOGIN",flush=True)
    print("PASS: SYSBOOT stopped at absent SYS.EXE, with no INILOA or LOGINOUT",flush=True)
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
