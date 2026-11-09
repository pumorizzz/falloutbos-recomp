"""Boot conformance: run the recompiled game headless and count how far it gets.

    py -3 tools/boot_check.py [path/to/fobos.exe] [--update-baseline]

The ground truth is the retail game's own boot sequence: Interplay logo, intro,
main menu, character and difficulty select, chapter 1's intro, the first level
(Carbon). A scripted pad (RECOMP_PAD_SCRIPT) presses through the menus exactly
as a player would, and each milestone is recognised in the log by the file the
title opens for it, so the check needs no screenshots and no timing guesses.
Two more checks hold for the whole run: no fault, no unresolved indirect call.

Prints "boot_check: N/M passed" and exits non-zero only on a regression: fewer
passes than config/boot_check_baseline.json records. A machine without game
data prints a SKIP line and exits 0 (REPO_RULES section 10: data-dependent
tests report SKIP, not PASS).

Runs about 4 minutes: the level loads around 3 minutes in.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "config", "boot_check_baseline.json")
TIMEOUT_S = 240

# Start, then A every 5 s: through the menus, the chapter intro and the
# opening dialogue. Same script the README documents.
PAD = ",".join(["25000:start", "35000:a", "50000:a", "65000:a"]
               + ["%d:a" % t for t in range(80000, 200001, 5000)])

# (name, test on the log text)
MILESTONES = [
    ("Interplay logo plays",      lambda s: "resx\\interplay.bik" in s),
    ("intro plays",               lambda s: "resx\\intro.bik" in s),
    ("main menu",                 lambda s: "resx\\Main_Menu.bik" in s),
    ("character select",          lambda s: "resx\\Character_" in s),
    ("chapter 1 intro",           lambda s: "resx\\chap1_" in s),
    ("Carbon loads",              lambda s: "c1\\CRB_1a\\CRB_1a.ddf" in s),
    ("no faults",                 lambda s: "[FAULT]" not in s
                                            and "[EXCEPTION]" not in s),
    ("no unresolved calls",       lambda s: "Failed to resolve VA" not in s),
]


def main(argv):
    update = "--update-baseline" in argv
    args = [a for a in argv if not a.startswith("--")]
    exe = os.path.abspath(args[0]) if args else os.path.join(ROOT, "bin", "fobos.exe")

    if not os.path.isfile(os.path.join(ROOT, "game", "default.xbe")):
        print("boot_check: SKIP (no game data in game/; unpack your own disc)")
        return 0
    if not os.path.isfile(exe):
        print("boot_check: FAIL (no executable at %s)" % exe)
        return 1

    env = dict(os.environ, RECOMP_PAD_SCRIPT=PAD, RECOMP_PB_EXEC="1")
    env.pop("RECOMP_FB_WINDOW", None)              # headless: never a window
    try:
        p = subprocess.run([exe], cwd=ROOT, env=env, capture_output=True,
                           timeout=TIMEOUT_S)
        log = (p.stdout + p.stderr).decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:          # the normal end: it never exits
        log = ((e.stdout or b"") + (e.stderr or b"")).decode("utf-8", "replace")

    passed = 0
    for name, test in MILESTONES:
        ok = test(log)
        passed += ok
        print("  %-26s %s" % (name, "PASS" if ok else "FAIL"))
    print("boot_check: %d/%d passed" % (passed, len(MILESTONES)))

    base = 0
    if os.path.isfile(BASELINE):
        with open(BASELINE) as f:
            base = json.load(f).get("passed", 0)
    if update:
        with open(BASELINE, "w") as f:
            json.dump({"passed": passed, "of": len(MILESTONES)}, f)
            f.write("\n")
        print("boot_check: baseline set to %d" % passed)
        return 0
    if passed < base:
        print("boot_check: REGRESSION (baseline %d)" % base)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
