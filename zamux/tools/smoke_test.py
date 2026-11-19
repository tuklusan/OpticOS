#!/usr/bin/env python3
"""
smoke_test.py — Headless SimCoupé smoke test for a ZAMUX .mgt image.
Boots the image, waits 3 seconds, screenshots the display, checks for
pixel activity (non-black screen → banner was printed).
"""

import sys
import os
import subprocess
import time
import tempfile

SIMCOUPE = "/home/user/tools/simcoupe/build/simcoupe"
XVFB_RES = "800x600x16"

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

            sim = subprocess.Popen(
                [SIMCOUPE, "-disk1", mgt, "-autoboot"],
                env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(3)

            shot = os.path.join(tmp, "screen.png")
            subprocess.run(
                ["import", "-window", "root", "-display", display, shot],
                check=True, env=env
            )
            sim.terminate()
            sim.wait()

            # Check screenshot is not all-black
            result = subprocess.run(
                ["identify", "-verbose", shot],
                capture_output=True, text=True
            )
            if "mean: 0" in result.stdout.lower():
                print("FAIL: screen appears blank")
                sys.exit(1)

            print(f"PASS: screen has content — screenshot saved to {shot}")
            # Copy screenshot out of tmp
            final = mgt.replace(".mgt", "_smoke.png")
            import shutil
            shutil.copy(shot, final)
            print(f"Screenshot: {final}")

        finally:
            xvfb.terminate()
            xvfb.wait()

if __name__ == '__main__':
    main()
