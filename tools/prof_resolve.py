"""Name the functions of a FBOS_PROFILE log on a PC, against fobos.pdb and fobos.map.

    py -3 -I tools/prof_resolve.py <fobos.log> --exe <path to fobos.exe> [--map <fobos.map>]
    (the pdb and, by default, fobos.map beside the exe)

FBOS_PROFILE=<start>,<secs> samples every thread's RIP and prints the top functions.
Each line ends in module+RVA of the function (the unwind table's start; `~` = no unwind
entry, the RVA rounded down to 16). On the machine that ran the game dbghelp names
only some of them -- under Wine/Proton not even the `sub_*` of the lifted game, and
nothing of the system DLLs -- but the RVA of fobos.exe is the same on every machine for the
same build, so here the pdb of that build names them all.

The log's `[PROF] image` line (time stamp, size, CodeView GUID and age of the exe that ran)
is checked against --exe and the pdb dbghelp loads for it; a different build is an error
(exit 2) rather than wrong names. The summary: functions over all threads, threads (with
the function each started in, and for every thread at least 5% busy its top 20 functions
as a share of its busy samples), other modules apart; waits left out as the profiler
does. For `sub_XXXXXXXX` the guest address is the hex part. Windows only (dbghelp).

The names of fobos.exe's functions come from the linker map (`fobos.map`, beside the exe or
--map; packaged with package.ps1 -Pdb): dbghelp's pdb has only the public symbols, so a
static function of the toolkit (`xf_to_backend`, `vsh_worker`, `hash_bytes`) came out
under the nearest public name before it. The map's `Timestamp is` must equal the exe's and
the log's, else exit 2 (`the map is from another build`). Every sample is placed in the map
symbol that contains its RVA, so the fragments of one function (chained .pdata entries) are
one row; `[obj]` is the object file. Without a map the pdb names are used and a warning says so.
"""
import bisect
import ctypes
import os
import re
import struct
import sys
import uuid
from ctypes import wintypes

WAITS = ("WaitFor", "DelayExecution", "RemoveIoCompletion")


# ---- the exe's identity --------------------------------------------------------------

def pe_info(path):
    """(time stamp, size of image, pdb text like the log's) of a PE file."""
    with open(path, "rb") as f:
        d = f.read()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    if d[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE file: %s" % path)
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    stamp = struct.unpack_from("<I", d, pe + 8)[0]
    optsz = struct.unpack_from("<H", d, pe + 20)[0]
    opt = pe + 24
    size = struct.unpack_from("<I", d, opt + 56)[0]
    dbg_rva, dbg_sz = struct.unpack_from("<II", d, opt + 112 + 6 * 8)   # PE32+ data directory 6
    secs = opt + optsz

    def off(rva):
        for i in range(nsec):
            va, rs, ro = struct.unpack_from("<III", d, secs + 40 * i + 12)
            if va <= rva < va + max(rs, 1):
                return ro + rva - va
        return None

    pdb = "none"
    o = off(dbg_rva) if dbg_rva else None
    for i in range(dbg_sz // 28 if o is not None else 0):
        typ = struct.unpack_from("<I", d, o + 28 * i + 12)[0]
        raw = struct.unpack_from("<I", d, o + 28 * i + 20)[0]
        if typ == 2 and raw:
            ro = off(raw)
            if ro is not None and d[ro:ro + 4] == b"RSDS":
                g = uuid.UUID(bytes_le=d[ro + 4:ro + 20])
                age = struct.unpack_from("<I", d, ro + 20)[0]
                x = g.hex.upper()
                pdb = "{%s-%s-%s-%s-%s}-%d" % (x[0:8], x[8:12], x[12:16], x[16:20], x[20:32], age)
            break
    return stamp, size, pdb


# ---- dbghelp -------------------------------------------------------------------------

class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wintypes.ULONG), ("TypeIndex", wintypes.ULONG),
                ("Reserved", ctypes.c_uint64 * 2), ("Index", wintypes.ULONG),
                ("Size", wintypes.ULONG), ("ModBase", ctypes.c_uint64),
                ("Flags", wintypes.ULONG), ("Value", ctypes.c_uint64),
                ("Address", ctypes.c_uint64), ("Register", wintypes.ULONG),
                ("Scope", wintypes.ULONG), ("Tag", wintypes.ULONG),
                ("NameLen", wintypes.ULONG), ("MaxNameLen", wintypes.ULONG),
                ("Name", ctypes.c_char * 512)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class IMAGEHLP_MODULE64(ctypes.Structure):
    _fields_ = [("SizeOfStruct", wintypes.DWORD), ("BaseOfImage", ctypes.c_uint64),
                ("ImageSize", wintypes.DWORD), ("TimeDateStamp", wintypes.DWORD),
                ("CheckSum", wintypes.DWORD), ("NumSyms", wintypes.DWORD),
                ("SymType", wintypes.DWORD), ("ModuleName", ctypes.c_char * 32),
                ("ImageName", ctypes.c_char * 256), ("LoadedImageName", ctypes.c_char * 256),
                ("LoadedPdbName", ctypes.c_char * 256), ("CVSig", wintypes.DWORD),
                ("CVData", ctypes.c_char * 780), ("PdbSig", wintypes.DWORD),
                ("PdbSig70", GUID), ("PdbAge", wintypes.DWORD), ("PdbUnmatched", wintypes.BOOL),
                ("DbgUnmatched", wintypes.BOOL), ("LineNumbers", wintypes.BOOL),
                ("GlobalSymbols", wintypes.BOOL), ("TypeInfo", wintypes.BOOL),
                ("SourceIndexed", wintypes.BOOL), ("Publics", wintypes.BOOL),
                ("MachineType", wintypes.DWORD), ("Reserved", wintypes.DWORD)]


class Pdb:
    """fobos.exe loaded into dbghelp at a fixed base; RVA <-> name."""
    BASE = 0x140000000
    _n = 0

    def __init__(self, exe):
        self.dbg = ctypes.WinDLL("dbghelp")
        d = self.dbg
        d.SymInitialize.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.BOOL]
        d.SymSetOptions.argtypes = [wintypes.DWORD]
        d.SymSetSearchPathW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR]
        d.SymLoadModuleExW.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPCWSTR,
                                       wintypes.LPCWSTR, ctypes.c_uint64, wintypes.DWORD,
                                       ctypes.c_void_p, wintypes.DWORD]
        d.SymLoadModuleExW.restype = ctypes.c_uint64
        d.SymFromAddr.argtypes = [wintypes.HANDLE, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64),
                                  ctypes.POINTER(SYMBOL_INFO)]
        d.SymFromName.argtypes = [wintypes.HANDLE, ctypes.c_char_p, ctypes.POINTER(SYMBOL_INFO)]
        d.SymGetModuleInfo64.argtypes = [wintypes.HANDLE, ctypes.c_uint64, ctypes.POINTER(IMAGEHLP_MODULE64)]
        Pdb._n += 1
        self.h = wintypes.HANDLE(0x7A7A + Pdb._n)  # any handle: dbghelp only keys on it, one per instance
        d.SymSetOptions(0x2)                      # SYMOPT_UNDNAME; not deferred: loads now
        d.SymInitialize(self.h, None, False)
        exe = os.path.abspath(exe)
        d.SymSetSearchPathW(self.h, os.path.dirname(exe))
        stamp, img_size, _ = pe_info(exe)
        self.base = d.SymLoadModuleExW(self.h, None, exe, None, self.BASE, img_size, None, 0)
        if not self.base:
            raise OSError("dbghelp could not load %s" % exe)

    def close(self):
        self.dbg.SymCleanup(self.h)

    def module_info(self):
        mi = IMAGEHLP_MODULE64()
        mi.SizeOfStruct = ctypes.sizeof(mi)
        if not self.dbg.SymGetModuleInfo64(self.h, self.base, ctypes.byref(mi)):
            return None
        return mi

    def pdb_text(self):
        """The loaded pdb's GUID and age, as the log writes them (None: no pdb)."""
        mi = self.module_info()
        if mi is None or mi.SymType != 3 or not mi.LoadedPdbName:    # SymPdb
            return None
        g = mi.PdbSig70
        return "{%08X-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X}-%d" % (
            g.Data1, g.Data2, g.Data3, g.Data4[0], g.Data4[1], g.Data4[2], g.Data4[3],
            g.Data4[4], g.Data4[5], g.Data4[6], g.Data4[7], mi.PdbAge)

    def name_at(self, rva):
        si = SYMBOL_INFO()
        si.SizeOfStruct = 88                        # sizeof(SYMBOL_INFO) with Name[1]
        si.MaxNameLen = 511
        disp = ctypes.c_uint64(0)
        if self.dbg.SymFromAddr(self.h, self.base + rva, ctypes.byref(disp), ctypes.byref(si)):
            return si.Name.decode("ascii", "replace"), disp.value
        return None, 0

    def rva_of(self, name):
        si = SYMBOL_INFO()
        si.SizeOfStruct = 88                        # sizeof(SYMBOL_INFO) with Name[1]
        si.MaxNameLen = 511
        if self.dbg.SymFromName(self.h, name.encode(), ctypes.byref(si)):
            return si.Address - self.base
        return None


# ---- the linker map -----------------------------------------------------------------

MAPSYM = re.compile(r"^\s*([0-9a-f]{4}):([0-9a-f]{8})\s+(\S+)\s+([0-9a-f]{16})\s+(?:(f)\s+)?(?:(i)\s+)?(\S.*)?$")


class LinkMap:
    """Symbols of .text from the `Publics by Value` and `Static symbols` lists of fobos.map."""

    def __init__(self, path):
        self.stamp = None
        syms = {}
        section = None
        with open(path, encoding="latin-1") as f:
            for line in f:
                if self.stamp is None:
                    m = re.search(r"Timestamp is ([0-9a-fA-F]+)", line)
                    if m:
                        self.stamp = int(m.group(1), 16)
                if "Publics by Value" in line:
                    section = "pub"
                    continue
                if "Static symbols" in line:
                    section = "static"
                    continue
                if section is None:
                    continue
                m = MAPSYM.match(line)
                if not m or m.group(1) != "0001":
                    continue
                rva = int(m.group(4), 16) - Pdb.BASE
                if rva <= 0:
                    continue
                name, obj = m.group(3), (m.group(7) or "").strip()
                prev = syms.get(rva)
                # several names at one RVA: keep the first, but a function-flagged one wins
                if prev is None or (not prev[2] and m.group(5)):
                    syms[rva] = (name, obj, bool(m.group(5)))
        self.syms = syms
        self.rvas = sorted(syms)

    def label(self, rva):
        """`name [object]` of the symbol at or before the RVA; None before the first."""
        k = bisect.bisect_right(self.rvas, rva) - 1
        if k < 0:
            return None
        name, obj, _ = self.syms[self.rvas[k]]
        obj = obj.split(":")[-1]
        if obj.lower().endswith(".obj"):
            obj = obj[:-4]
        return "%s [%s]" % (name, obj) if obj else name


# ---- the log -------------------------------------------------------------------------

IMAGE = re.compile(r"\[PROF\] image (\S+) base 0x([0-9A-Fa-f]+) size 0x([0-9A-Fa-f]+) "
                   r"time 0x([0-9A-Fa-f]+) pdb (\S+)")
ROW = re.compile(r"\[PROF\]\s+([\d.]+)%\s+(\d+)\s+(\d+) (.*) @ (\S+?)\+0x(~?)([0-9A-Fa-f]+)\s*$")
THREAD = re.compile(r"\[PROF\] thread (\d+): (\d+) samples, (\d+) busy \(\d+%\), start (?:(\S+?)\+0x([0-9A-Fa-f]+)|\?)")
TOTAL = re.compile(r"\[PROF\] (\d+) samples, top functions")


def parse(text):
    img = None
    rows, threads, total = [], [], 0
    for line in text.splitlines():
        m = IMAGE.search(line)
        if m:
            img = dict(name=m.group(1), base=int(m.group(2), 16), size=int(m.group(3), 16),
                       time=int(m.group(4), 16), pdb=m.group(5))
            continue
        m = TOTAL.search(line)
        if m:
            total = int(m.group(1))
            continue
        m = ROW.search(line)
        if m:
            rows.append(dict(n=int(m.group(2)), tid=int(m.group(3)), host=m.group(4),
                             mod=m.group(5), approx=bool(m.group(6)), rva=int(m.group(7), 16)))
            continue
        m = THREAD.search(line)
        if m:
            # `start ?`: the thread had ended before the profiler could ask where it began
            threads.append(dict(tid=int(m.group(1)), n=int(m.group(2)), busy=int(m.group(3)),
                                mod=m.group(4), rva=int(m.group(5), 16) if m.group(5) else 0))
    return img, rows, threads, total


def is_wait(name):
    return any(w in name for w in WAITS)


def find_map(exe, map_path=None):
    """The map to use: --map, else <exe without .exe>.map; None if there is none."""
    path = map_path or os.path.splitext(os.path.abspath(exe))[0] + ".map"
    return path if os.path.isfile(path) else None


def resolve(text, exe, map_path=None):
    """(exit code, report text). map_path: --map; None = beside the exe; "" = pdb names only."""
    img, rows, threads, total = parse(text)
    if img is None:
        return 2, "no `[PROF] image` line in the log: it is from a build without module+RVA\n"
    if not os.path.isfile(exe):
        return 2, "no exe at %s\n" % exe
    stamp, size, pdb = pe_info(exe)
    bad = []
    if stamp != img["time"]:
        bad.append("time stamp: log 0x%X, exe 0x%X" % (img["time"], stamp))
    if size != img["size"]:
        bad.append("size of image: log 0x%X, exe 0x%X" % (img["size"], size))
    if pdb != img["pdb"]:
        bad.append("CodeView: log %s, exe %s" % (img["pdb"], pdb))
    if bad:
        return 2, ("the log is from another build than %s:\n  %s\n" % (exe, "\n  ".join(bad)))
    lmap, note = None, ""
    if map_path != "":
        mp = find_map(exe, map_path)
        if mp is None:
            if map_path:
                return 2, "no map at %s\n" % map_path
            note = ("no fobos.map beside the exe: the toolkit's static functions come out "
                    "under the nearest public name\n")
        else:
            lmap = LinkMap(mp)
            if lmap.stamp != stamp or lmap.stamp != img["time"]:
                return 2, ("the map is from another build than %s: time stamp: map %s, exe 0x%X, "
                           "log 0x%X\n" % (exe, "none" if lmap.stamp is None else "0x%X" % lmap.stamp,
                                           stamp, img["time"]))
    sym = Pdb(exe)
    try:
        code, out = _resolve(sym, img, rows, threads, total, exe, lmap)
        return code, (note + out if code == 0 else out)
    finally:
        sym.close()


def _resolve(sym, img, rows, threads, total, exe, lmap=None):
    loaded = sym.pdb_text()
    if loaded is None:
        return 2, "no fobos.pdb found beside %s\n" % exe
    if loaded != img["pdb"]:
        return 2, "the pdb beside the exe is %s, the log's build %s\n" % (loaded, img["pdb"])

    exe_name = img["name"].lower()
    funcs, foreign, fnames = {}, {}, {}

    def name_of(rva):
        if lmap is not None:
            nm = lmap.label(rva)
            if nm:
                return nm
        return sym.name_at(rva)[0]

    for r in rows:
        if r["mod"].lower() == exe_name:
            nm = name_of(r["rva"]) or "?"
            # with the map the fragments of one function are one row; the rva of a `~` row is
            # only rounded down, which the symbol containing it absorbs
            if r["approx"] and lmap is None:
                nm += " (~, no unwind entry)"
            key = nm
            tgt = funcs
        else:
            key = "%s @ %s+0x%X" % (r["host"], r["mod"], r["rva"])
            tgt = foreign
        if is_wait(r["host"]) or is_wait(key):
            continue
        tgt[key] = tgt.get(key, 0) + r["n"]
        fnames.setdefault(r["tid"], {})[key] = fnames.get(r["tid"], {}).get(key, 0) + r["n"]
    out = []
    t = total or sum(r["n"] for r in rows) or 1
    out.append("build: %s time 0x%X pdb %s; %d samples in the log\n" % (img["name"], img["time"], img["pdb"], t))

    def table(title, d, limit):
        out.append("\n%s\n" % title)
        for k, n in sorted(d.items(), key=lambda kv: -kv[1])[:limit]:
            m = re.match(r"sub_([0-9A-Fa-f]{8})", k)
            out.append("  %5.1f%%  %7d  %s%s\n" % (100.0 * n / t, n, k, "  (guest 0x%s)" % m.group(1) if m else ""))

    table("functions of fobos.exe, all threads (waits left out):", funcs, 40)
    table("other modules:", foreign, 25)
    out.append("\nthreads:\n")
    for th in sorted(threads, key=lambda x: -x["busy"]):
        if th["mod"] is None:
            start = "? (the thread had ended)"
        elif th["mod"].lower() == exe_name:
            start = name_of(th["rva"]) or "fobos.exe+0x%X" % th["rva"]
        else:
            start = "%s+0x%X" % (th["mod"], th["rva"])
        pct = 100 * th["busy"] // max(th["n"], 1)
        # a thread at least 5% busy: its top 20 functions as a share of ITS busy samples
        top = sorted(fnames.get(th["tid"], {}).items(), key=lambda kv: -kv[1])[:20 if pct >= 5 else 3]
        out.append("  tid %5d  %7d samples  %7d busy (%3d%%)  start %s\n" % (
            th["tid"], th["n"], th["busy"], pct, start))
        for k, n in top:
            m = re.match(r"sub_([0-9A-Fa-f]{8})", k)
            out.append("              %5.1f%% of busy  %6d  %s%s\n" % (
                100.0 * n / max(th["busy"], 1), n, k, "  (guest 0x%s)" % m.group(1) if m else ""))
    return 0, "".join(out)


def main(argv):
    exe = None
    map_path = None
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == "--exe" and i + 1 < len(argv):
            exe = argv[i + 1]
            i += 2
        elif argv[i] == "--map" and i + 1 < len(argv):
            map_path = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    if len(args) != 1 or not exe:
        print(__doc__)
        return 1
    with open(args[0], encoding="utf-8", errors="replace") as f:
        code, text = resolve(f.read(), exe, map_path)
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
