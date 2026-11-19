#!/usr/bin/env python3
"""
smoke_test.py — Headless SimCoupé smoke test for a ZAMUX .mgt image.
Boots the image, waits 10 seconds, screenshots the SimCoupé window,
checks that the SAM display is non-black (mean pixel value > 10/255).
"""

import sys
import os
import subprocess
import time
import tempfile
import shutil

SIMCOUPE  = "/home/user/tools/simcoupe/build/simcoupe"
RESPATH   = "/home/user/tools/simcoupe/Resource"
XVFB_RES  = "1600x1200x24"   # large enough for SimCoupé window (1062x804)

def find_simcoupe_window(display, env, timeout=5.0):
    """Poll until xdotool finds at least one visible window."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "."],
            capture_output=True, text=True, env=env)
        ids = r.stdout.strip().split()
        if ids:
            return ids[0]
        time.sleep(0.2)
    return None

def pixel_mean(png_path):
    """Return the mean pixel brightness 0-255 from identify -verbose output."""
    r = subprocess.run(
        ["identify", "-verbose", png_path],
        capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "mean" in line.lower():
            # first "Mean: <value>" line; value may be "0.xxx" or "228.xxx"
            try:
                val = float(line.split(":")[1].strip().split()[0])
                return val
            except (IndexError, ValueError):
                pass
    return 0.0

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <image.mgt>")
        sys.exit(1)

    mgt = os.path.abspath(sys.argv[1])
    if not os.path.exists(mgt):
        print(f"ERROR: {mgt} not found")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        display = ":99"
        xvfb = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", XVFB_RES],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            time.sleep(0.5)
            env = os.environ.copy()
            env["DISPLAY"] = display
            env["SDL_AUDIODRIVER"] = "dummy"

            # Pass disk as bare positional arg so drive_arg > 1 → QueueAutoBoot
            sim = subprocess.Popen(
                [SIMCOUPE, "-respath", RESPATH, mgt],
                env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            # Wait for SimCoupé window to appear, then wait for SAMDOS + stage1
            wid = find_simcoupe_window(display, env, timeout=10.0)
            if not wid:
                print("FAIL: SimCoupé window never appeared")
                sim.terminate(); sim.wait()
                sys.exit(1)

            # Allow autoboot + SAMDOS load + stage1 execution
            time.sleep(10)

            shot = os.path.join(tmp, "screen.png")
            subprocess.run(
                ["import", "-window", wid, "-display", display, shot],
                check=True, env=env
            )
            sim.terminate()
            sim.wait()

            mean = pixel_mean(shot)
            print(f"Screenshot mean brightness: {mean:.1f}/255")

            if mean < 10.0:
                print("FAIL: screen appears blank (mean < 10)")
                sys.exit(1)

            print(f"PASS: screen has content (mean={mean:.1f})")
            final = mgt.replace(".mgt", "_smoke.png")
            shutil.copy(shot, final)
            print(f"Screenshot: {final}")

        finally:
            xvfb.terminate()
            xvfb.wait()

if __name__ == '__main__':
    main()
