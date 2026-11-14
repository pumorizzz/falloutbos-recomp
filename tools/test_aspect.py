#!/usr/bin/env python3
"""Self-check of tools/aspect.py (the 16:9 / 4:3 switch of Fallout: BoS).

Run: py -3 tools/test_aspect.py   (from the port root; pytest is not installed)

Background: tools/widescreen.py rewrote 11 places of the XBE code, so the
generated C held 16:9 as constants and one exe drew one aspect. aspect.py
generates the C from an XBE with those places at 4:3 and lifts the one
instruction at each place as a read of g_fbos_aspect_site[i]. What can go
wrong silently: a renamed lifter hook (the sites stay literals), a wrong hook
address (a neighbouring instruction is replaced), a normalised XBE that is
not the same for a patched and an unpatched image.

A and B need no data, C the toolkit (deps/xboxrecomp), D game/default.xbe,
E the generated C in src/game/recomp/gen. Missing data prints SKIP.
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TK = os.environ.get('RECOMP') or os.path.join(ROOT, 'deps', 'xboxrecomp')
sys.path.insert(0, HERE)
sys.path.insert(0, TK)

import aspect          # noqa: E402
import widescreen as ws  # noqa: E402

failures = 0


def check(ok, what, detail=''):
    global failures
    if not ok:
        failures += 1
    print(f'  {"PASS" if ok else "FAIL"}  {what}' + (f'  ({detail})' if detail and not ok else ''))


# (hook VA, 4:3 value, 16:9 value), literals on purpose: not derived from widescreen.SITES
EXPECT = [
    (0x0003292A, 0x43A00000, 0x43700000), (0x00032980, 0x43A00000, 0x43700000),
    (0x000329BF, 0x43A00000, 0x43700000), (0x0007C61D, 0x43A00000, 0x43700000),
    (0x000904A2, 0x43A00000, 0x43700000), (0x000904D0, 0x43A00000, 0x43700000),
    (0x00089454, 0x3FAA3D71, 0x3FE38E39), (0x0008CC6D, 0x3FAA3D71, 0x3FE38E39),
    (0x0008CE1F, 0x43F80000, 0x43BA0000), (0x0008CF9D, 0x43F80000, 0x43BA0000),
    (0x0008CED1, 0x43F80000, 0x43BA0000),
]


def f32(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]


print('A: site table')
got = [(s[0], s[3], s[4]) for s in aspect.SITES]
check(got == EXPECT, 'hook VAs and both value sets', f'{[(hex(a), hex(b), hex(c)) for a, b, c in got]}')
check(abs(f32(0x43700000) / f32(0x43A00000) - 0.75) < 1e-9, 'projection 240/320 = 3/4')
check(abs(f32(0x43BA0000) / f32(0x43F80000) - 0.75) < 1e-9, 'matrix 372/496 = 3/4')
check(abs(f32(0x3FE38E39) - 16 / 9) < 1e-6, 'camera at 16:9 is 16/9', str(f32(0x3FE38E39)))
check(abs(f32(0x3FAA3D71) - 1.33) < 0.01, 'camera at 4:3 is about 1.33', str(f32(0x3FAA3D71)))

print('B: generated table')
c = aspect.table_c()


def arr(name):
    m = re.search(r'%s\[\d+\] = \{(.*?)\};' % name, c, re.S)
    return [int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{8}),', m.group(1))] if m else None


m = re.search(r'g_fbos_aspect_site\[\d+\] = \{([^}]*)\}', c)
init = [int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{8})', m.group(1))] if m else None
check(arr('k_4x3') == [e[1] for e in EXPECT], 'k_4x3')
check(arr('k_16x9') == [e[2] for e in EXPECT], 'k_16x9')
check(init == [e[2] for e in EXPECT], 'initialiser is 16:9 (unset FBOS_ASPECT)')
check('void fbos_aspect_select(int widescreen)' in c, 'fbos_aspect_select present')

print('C: lifter hook')
try:
    import tools.recomp.lifter as lifter
    from tools.recomp.disasm import Disassembler
except ImportError as e:
    print(f'  SKIP  toolkit not found at {TK} ({e})')
    lifter = None

if lifter:
    class Hooked(lifter.Lifter):
        pass

    hits = aspect.install(Hooked, lifter._fmt_mem)

    def decode(raw, va):
        return Disassembler().disassemble_function(raw, va, va + len(raw))[0]

    def lift(cls, raw, va):
        return cls().lift_instruction(decode(raw, va))

    raw = bytes.fromhex('680000A043')
    want = ['extern uint32_t g_fbos_aspect_site[11]; '
            '/* tools/aspect.py: FBOS_ASPECT picks the value */',
            'PUSH32(esp, g_fbos_aspect_site[0]); /* push 0x43A00000 at 4:3 */']
    check(lift(Hooked, raw, 0x3292A) == want, 'push at 0x3292A reads the table',
          str(lift(Hooked, raw, 0x3292A)))
    check(lift(lifter.Lifter, raw, 0x3292A) == ['PUSH32(esp, 0x43A00000);'],
          'the plain lifter keeps the literal (the test sees the hook)',
          str(lift(lifter.Lifter, raw, 0x3292A)))
    r = lift(Hooked, bytes.fromhex('F30F114C2450'), 0x8CE1F)
    check(len(r) == 2 and r[1].startswith('MEM32(esp + 0x50) = g_fbos_aspect_site[8];'),
          'movss m00 at 0x8CE1F reads the table', str(r))
    for braw, va, what in ((bytes.fromhex('6800007043'), 0x3292A, 'push of another value'),
                           (bytes.fromhex('C74424700000F843'), 0x8CED1, 'mov instead of movss')):
        try:
            lift(Hooked, braw, va)
            check(False, f'refused: {what}')
        except SystemExit:
            check(True, f'refused: {what}')
    check(lift(Hooked, raw, 0x32900) == lift(lifter.Lifter, raw, 0x32900),
          'an address outside the table lifts as before')
    check(hits[0] > 0 and hits[8] > 0, 'hits counted', str(dict(hits)))

print('D: neutral XBE')
xbe = os.path.join(ROOT, 'game', 'default.xbe')
if not os.path.isfile(xbe):
    print('  SKIP  no game/default.xbe')
else:
    with open(xbe, 'rb') as f:
        d = bytearray(f.read())
    d43, d169 = bytearray(d), bytearray(d)
    for va, orig, new, _ in ws.SITES:
        off = ws.file_offset(d, va)
        d43[off:off + len(orig)] = orig
        d169[off:off + len(new)] = new
    n43, n169 = aspect.neutral_bytes(bytes(d43)), aspect.neutral_bytes(bytes(d169))
    check(n43 == n169 == bytes(d43), 'patched and unpatched give the same bytes, at 4:3')
    check(ws.state(n169) == '4x3', 'state of the neutral image is 4:3')
    bad = bytearray(d169)
    bad[ws.file_offset(bad, 0x89455)] ^= 0xFF
    try:
        aspect.neutral_bytes(bytes(bad))
        check(False, 'a damaged site is refused')
    except ValueError:
        check(True, 'a damaged site is refused')
    if lifter:
        for i, s in enumerate(aspect.SITES):
            off = ws.file_offset(n169, s[0])
            try:
                r = lift(Hooked, n169[off:off + 16], s[0])
                check(any(f'g_fbos_aspect_site[{i}]' in x for x in r), f'site {i} 0x{s[0]:08X} hooked',
                      str(r))
            except SystemExit as e:
                check(False, f'site {i} 0x{s[0]:08X} hooked', str(e))

print('E: generated C')
gen = os.path.join(ROOT, 'src', 'game', 'recomp', 'gen')
tab = os.path.join(gen, 'recomp_fbos_aspect.c')
if not os.path.isfile(tab):
    print('  SKIP  no generated C')
else:
    with open(tab, 'rb') as f:
        check(f.read().decode('ascii') == aspect.table_c(), 'recomp_fbos_aspect.c is the table')
    funcs = {'sub_00032860': (0, 1, 2), 'sub_0007C580': (3,), 'sub_000903B0': (4, 5),
             'sub_00089440': (6,), 'sub_0008CC60': (7,), 'sub_0008CC90': (8, 9, 10)}
    bodies = {}
    for fn in sorted(os.listdir(gen)):
        if re.match(r'recomp_\d+\.c$', fn):
            with open(os.path.join(gen, fn), encoding='latin-1') as f:
                txt = f.read()
            for name in funcs:
                m = re.search(r'void %s\(void\)\n\{(.*?)\n\}\n' % name, txt, re.S)
                if m:
                    bodies[name] = m.group(1)
    for name, idx in funcs.items():
        b = bodies.get(name)
        if b is None:
            check(False, f'{name} found in gen/')
            continue
        check(all(f'g_fbos_aspect_site[{i}]' in b for i in idx), f'{name} reads sites {list(idx)}')
        code = re.sub(r'/\*.*?\*/', '', b, flags=re.S)       # the hook's comment names the 4:3 value
        lit = [x for x in ('0x43700000', '0x3FE38E39', '0x3FAA3D71', '0x43BA0000') if x in code]
        check(not lit, f'{name} has no 16:9 / camera literals', str(lit))

print('aspect: OK' if not failures else f'aspect: {failures} FAILED')
sys.exit(1 if failures else 0)
