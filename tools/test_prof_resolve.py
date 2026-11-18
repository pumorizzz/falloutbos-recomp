"""Self-check of tools/prof_resolve.py. Run: py -3 tools/test_prof_resolve.py

FBOS_PROFILE lines end in module+RVA of the function, and prof_resolve.py names them on a PC
from fobos.pdb: the Steam Deck's profile (Wine) had `sub_*` unnamed and `common_getenv_nolock`
and `memcmp` only by luck of dbghelp. This builds a profile block from the RVAs of known
symbols of bin\\fobos.exe (SymFromName: sub_000DED51, recomp_unimpl, nv2a_pb_exec_method)
with the exe's own header line, and checks that

  - the names come back (and the guest address of a `sub_*`), a wait in ntdll is left out,
    a foreign module row stays as the host named it, a thread's start function is named;
  - the header of another build (another time stamp; another CodeView GUID) is exit 2, from
    the function and from the command line.

SKIP (exit 0) without bin\\fobos.exe and bin\\fobos.pdb. Windows only (dbghelp). Prints
`prof_resolve: OK|N FAILED`.
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import prof_resolve as pr  # noqa: E402

EXE = os.path.join(ROOT, "bin", "fobos.exe")
failures = 0


def check(ok, what):
    global failures
    if not ok:
        print("FAIL: " + what)
        failures += 1


def main():
    if os.name != "nt" or not os.path.isfile(EXE) or not os.path.isfile(EXE[:-4] + ".pdb"):
        print("prof_resolve: SKIP (no bin\\fobos.exe and fobos.pdb)")
        return 0
    stamp, size, pdb = pr.pe_info(EXE)
    sym = pr.Pdb(EXE)
    names = ["sub_000DED51", "recomp_unimpl", "nv2a_pb_exec_method"]
    rvas = [sym.rva_of(n) for n in names]
    check(all(r is not None for r in rvas), "the pdb has %s" % names)
    if failures:
        return 1
    image = "[PROF] image fobos.exe base 0x140000000 size 0x%X time 0x%X pdb %s" % (size, stamp, pdb)

    def block(image_line):
        lines = ["[PROF] sampling for 20s", image_line,
                 "[PROF] 1000 samples, top functions (idle waits left out):"]
        # the pdb's own symbol start + a few bytes: the profiler writes the function's start
        for k, (n, r) in enumerate(zip((300, 200, 100), rvas)):
            lines.append("[PROF] %5.1f%%  %6d  %5d %s @ fobos.exe+0x%X" % (n / 10.0, n, 100 + k, "<host name>", r))
        lines.append("[PROF]   5.0%%      50    200 ntdll.dll!NtWaitForSingleObject+0x14 @ ntdll.dll+0x%X" % 0x9D4C0)
        lines.append("[PROF]   4.0%%      40    201 <d3d11.dll> @ d3d11.dll+0x%X" % 0x1234)
        lines.append("[PROF]   3.0%%      30    102 ?? @ fobos.exe+0x~%X" % (rvas[0] + 0x10))
        lines.append("[PROF] thread 100: 300 samples, 280 busy (93%%), start fobos.exe+0x%X" % rvas[2])
        lines.append("[PROF] thread 200: 50 samples, 0 busy (0%), start ntdll.dll+0x2000")
        lines.append("[PROF] thread 300: 20 samples, 5 busy (25%), start ?")
        return "\n".join(lines) + "\n"

    code, text = pr.resolve(block(image), EXE)
    check(code == 0, "a log of this build resolves (exit %d: %s)" % (code, text[:200]))
    for n in names:
        check(n in text, "%s named" % n)
    check("(guest 0x000DED51)" in text, "the guest address of sub_000DED51")
    check("NtWaitForSingleObject" not in text, "the wait is left out")
    check("<d3d11.dll> @ d3d11.dll+0x1234" in text, "a foreign module row stays as the host named it")
    check("no unwind entry" in text, "a ~ row is marked")
    check("start nv2a_pb_exec_method" in text, "a thread's start function is named")
    check("tid   300" in text and "start ? (the thread had ended)" in text,
          "a thread with `start ?` is kept")
    # one function of a foreign module is one row, whatever the sample's offset in it
    code, text = pr.resolve(block(image).replace(
        "[PROF] thread 100", "[PROF]   2.0%      20    202 ntdll.dll!NtDoSomething @ ntdll.dll+0x5000\n"
        "[PROF]   2.0%      20    202 ntdll.dll!NtDoSomething @ ntdll.dll+0x5000\n[PROF] thread 100"), EXE)
    check(text.count("ntdll.dll!NtDoSomething @ ntdll.dll+0x5000") == 1
          and "  4.0%       40  ntdll.dll!NtDoSomething" in text,
          "the samples of one foreign function are one row")

    # another build: the time stamp, then the CodeView GUID
    code, text = pr.resolve(block(image.replace("time 0x%X" % stamp, "time 0x%X" % (stamp ^ 0x10))), EXE)
    check(code == 2 and "another build" in text, "another time stamp is exit 2 (got %d)" % code)
    guid = pdb[1:9]
    other = pdb.replace(guid, "%08X" % (int(guid, 16) ^ 1), 1)
    code, text = pr.resolve(block(image.replace(pdb, other)), EXE)
    check(code == 2 and "CodeView" in text, "another CodeView GUID is exit 2 (got %d)" % code)

    with tempfile.TemporaryDirectory() as td:
        good, bad = os.path.join(td, "good.log"), os.path.join(td, "bad.log")
        with open(good, "w") as f:
            f.write(block(image))
        with open(bad, "w") as f:
            f.write(block(image.replace(pdb, other)))
        script = os.path.join(ROOT, "tools", "prof_resolve.py")
        r = subprocess.run([sys.executable, "-I", script, good, "--exe", EXE], capture_output=True, text=True)
        check(r.returncode == 0 and "recomp_unimpl" in r.stdout, "the command line, a log of this build")
        r = subprocess.run([sys.executable, "-I", script, bad, "--exe", EXE], capture_output=True, text=True)
        check(r.returncode == 2, "the command line, another build: exit 2 (got %d)" % r.returncode)

    print("prof_resolve: %s" % ("OK" if not failures else "%d FAILED" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
