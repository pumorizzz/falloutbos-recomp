#!/usr/bin/env python3
"""Self-check of tools/aspect.py (the 16:9 / 16:10 / 4:3 switch of Fallout: BoS).

Run: py -3 tools/test_aspect.py   (from the port root; pytest is not installed)

Background: tools/widescreen.py rewrote 11 places of the XBE code, so the
generated C held 16:9 as constants and one exe drew one aspect. aspect.py
generates the C from an XBE with those places at 4:3 and lifts the one
instruction at each place as a read of g_fbos_aspect_site[i]. What can go
wrong silently: a renamed lifter hook (the sites stay literals), a wrong hook
address (a neighbouring instruction is replaced), a normalised XBE that is
not the same for a patched and an unpatched image.

The table holds those 11 places + 2 places only the port has (aspect.PORT_SITES):
the x placement of the inventory's 3D models (0x32AC1 the character and the
bar, 0x32EC0 the item models), scaled by 320 / the projection's x so they
stand as at 4:3 (indices 11 and 12).

A and B need no data, C the toolkit (deps/xboxrecomp), D game/default.xbe,
E the generated C in src/game/recomp/gen. Missing data prints SKIP.
F needs no data: main.c and the launcher name the same aspects as aspect.ASPECTS.
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


# (hook VA, 4:3, 16:9, 16:10 value), literals on purpose: not derived from widescreen.SITES
P = (0x43A00000, 0x43700000, 0x43855555)    # projection x
K = (0x3FAA3D71, 0x3FE38E39, 0x3FCCCCCD)    # camera aspect
M = (0x43F80000, 0x43BA0000, 0x43CEAAAB)    # matrix m00
EXPECT = [
    (0x0003292A,) + P, (0x00032980,) + P, (0x000329BF,) + P,
    (0x0007C61D,) + P, (0x000904A2,) + P, (0x000904D0,) + P,
    (0x00089454,) + K, (0x0008CC6D,) + K,
    (0x0008CE1F,) + M, (0x0008CF9D,) + M, (0x0008CED1,) + M,
    (0x00032AC1, 0x3F800000, 0x3FAAAAAB, 0x3F99999A),   # port only: character, bar
    (0x00032EC0, 0x3F800000, 0x3FAAAAAB, 0x3F99999A),   # port only: item models
]


# What the hook gives at the two port sites, literally (C and E compare whole lines)
MOVSS_11 = ('MEMF(esp + 0x14) = xmm0.f[0] * XMM_SCALAR_BITS(g_fbos_aspect_site[11]).f[0]; '
            '/* movss: UI model x placement x 320/projection x */')
MOV_12 = ('{ RecompXmm _fbos_x = XMM_SCALAR_BITS(MEM32(esp + 0x34)); '
          '_fbos_x.f[0] *= XMM_SCALAR_BITS(g_fbos_aspect_site[12]).f[0]; eax = _fbos_x.u[0]; } '
          '/* mov: UI model x placement x 320/projection x */')


def f32(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]


print('A: site table')
got = [(s[0], s[3], s[4], s[5]) for s in aspect.SITES]
check(got == EXPECT, 'hook VAs and the three value sets',
      f'{[tuple(hex(x) for x in g) for g in got]}')
check(abs(f32(0x43855555) / 320 - 5 / 6) < 1e-7, 'projection at 16:10 is 5/6 of 320')
check(abs(f32(0x43CEAAAB) / 496 - 5 / 6) < 1e-7, 'matrix at 16:10 is 5/6 of 496')
check(abs(f32(0x3FCCCCCD) - 1.6) < 1e-6, 'camera at 16:10 is 1.6')
check([aspect.value_at(s[1], s[3], 16, 9) for s in aspect.SITES[:11]] == [e[2] for e in EXPECT[:11]],
      "the rule gives Nemesis2000's 16:9 bytes")
for i, a in enumerate(aspect.ASPECTS):
    for j in (11, 12):
        k_p = f32(aspect.SITES[j][3 + i]) * f32(aspect.SITES[0][3 + i])
        check(abs(k_p - 320) < 1e-3, f'site {j} at {a[0]}: k x projection x = 320', str(k_p))
check(aspect.SITES[11][3] == aspect.SITES[12][3] == 0x3F800000, 'k at 4:3 is exactly 1.0')
check(len(ws.SITES) == 11 and not {0x32AC1, 0x32EC0} & {s[0] for s in ws.SITES},
      'widescreen.py keeps its 11 places, the port sites are not among them')
check(aspect.N == 13 and aspect.N_WS == 11, 'N = 13, N_WS = 11', f'{aspect.N}, {aspect.N_WS}')
check([a[0] for a in aspect.ASPECTS] == ['4:3', '16:9', '16:10'], 'ASPECTS order')
check(aspect.ASPECTS[aspect.DEFAULT][0] == '16:9', 'the default aspect is 16:9')
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
check(arr('k_16x10') == [e[3] for e in EXPECT], 'k_16x10')
check(re.search(r'k_sets\[3\] = \{ k_4x3, k_16x9, k_16x10 \}', c) is not None,
      'k_sets lists the three sets in ASPECTS order')
check(init == [e[2] for e in EXPECT], 'initialiser is 16:9 (unset FBOS_ASPECT)')
check('void fbos_aspect_select(int aspect)' in c, 'fbos_aspect_select present')
check('aspect < 3 ? aspect : 1]' in c, 'fbos_aspect_select falls back to 16:9')

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
    want = ['extern uint32_t g_fbos_aspect_site[13]; '
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
    r = lift(Hooked, bytes.fromhex('F30F11442414'), 0x32AC1)
    check(r == [want[0], MOVSS_11], 'movss x at 0x32AC1 is scaled by site 11', str(r))
    r = lift(Hooked, bytes.fromhex('8B442434'), 0x32EC0)
    check(r == [want[0], MOV_12], 'mov x at 0x32EC0 is scaled by site 12', str(r))
    for braw, va in ((bytes.fromhex('F30F11442414'), 0x32AC1), (bytes.fromhex('8B442434'), 0x32EC0)):
        r = lift(lifter.Lifter, braw, va)
        check(not any('g_fbos_aspect_site' in x for x in r),
              f'the plain lifter at 0x{va:X} has no table read', str(r))
    for braw, va, what in ((bytes.fromhex('6800007043'), 0x3292A, 'push of another value'),
                           (bytes.fromhex('C74424700000F843'), 0x8CED1, 'mov instead of movss'),
                           (bytes.fromhex('F30F114C2414'), 0x32AC1, 'movss of xmm1 at 0x32AC1'),
                           (bytes.fromhex('8B4C2434'), 0x32EC0, 'mov to ecx at 0x32EC0')):
        try:
            lift(Hooked, braw, va)
            check(False, f'refused: {what}')
        except SystemExit:
            check(True, f'refused: {what}')
    check(lift(Hooked, raw, 0x32900) == lift(lifter.Lifter, raw, 0x32900),
          'an address outside the table lifts as before')
    check(hits[0] > 0 and hits[8] > 0 and hits[11] > 0 and hits[12] > 0, 'hits counted',
          str(dict(hits)))

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
    for va, want_b in ((0x32AC1, 'F30F11442414'), (0x32EC0, '8B442434')):
        off = ws.file_offset(n169, va)
        got_b = n169[off:off + len(want_b) // 2].hex().upper()
        check(got_b == want_b, f'neutral image at 0x{va:X} holds {want_b}', got_b)
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
             'sub_00089440': (6,), 'sub_0008CC60': (7,), 'sub_0008CC90': (8, 9, 10),
             'sub_00032A70': (11,), 'sub_00032DB0': (12,)}
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
        lit = [x for x in ('0x43700000', '0x3FE38E39', '0x3FAA3D71', '0x43BA0000',
                           '0x43855555', '0x3FCCCCCD', '0x43CEAAAB') if x in code]
        check(not lit, f'{name} has no 16:9 / 16:10 / camera literals', str(lit))
    for name, line in (('sub_00032A70', MOVSS_11), ('sub_00032DB0', MOV_12)):
        b = bodies.get(name) or ''
        check(line in [x.strip() for x in b.split('\n')],
              f'{name} scales the model x by the table (the whole line)', line)
        code = re.sub(r'/\*.*?\*/', '', b, flags=re.S)
        lit = [x for x in ('0x3FAAAAAB', '0x3F99999A') if x in code]
        check(not lit, f'{name} has no k literals', str(lit))

print('F: main.c and the launcher name the same aspects as aspect.ASPECTS')
mainc = os.path.join(ROOT, 'src', 'game', 'main.c')
launc = os.path.join(ROOT, 'tools', 'launcher', 'launcher.c')
if not (os.path.isfile(mainc) and os.path.isfile(launc)):
    print('  SKIP  no main.c or launcher.c')
else:
    with open(mainc, encoding='utf-8', errors='replace') as f:
        msrc = f.read()
    with open(launc, encoding='utf-8', errors='replace') as f:
        lsrc = f.read()
    m = re.search(r'k_fbos_aspect\[\] = \{(.*?)\};', msrc, re.S)
    got = re.findall(r'\{ "([^"]+)", (\d+), (\d+) \}', m.group(1)) if m else None
    check(got == [(nm, str(n), str(d)) for nm, n, d in aspect.ASPECTS],
          'main.c k_fbos_aspect is aspect.ASPECTS', str(got))
    m = re.search(r'#define FBOS_ASPECT_DEFAULT (\d+)', msrc)
    check(m is not None and int(m.group(1)) == aspect.DEFAULT,
          'main.c FBOS_ASPECT_DEFAULT is aspect.DEFAULT')
    names = {a[0] for a in aspect.ASPECTS}
    m = re.search(r'k_render_aspect\[\] = \{(.*?)\};', lsrc, re.S)
    ra = re.findall(r'"([^"]+)"', m.group(1)) if m else None
    check(bool(ra) and set(ra) <= names, 'launcher k_render_aspect names are aspects', str(ra))
    sc = re.findall(r'strcmp\(asp, "([^"]+)"\)', lsrc)
    check(bool(sc) and set(sc) <= names, 'launcher strcmp(asp, ...) literals are aspects', str(sc))
    m = re.search(r'k_aspect\[\] = \{(.*?)\};', lsrc, re.S)
    vals = re.findall(r'\{ "[^"]*", "([^"]+)" \}', m.group(1)) if m else None
    check(vals is not None and sorted(vals) == sorted(a[0] for a in aspect.ASPECTS),
          'launcher k_aspect names the same aspects', str(vals))

print('aspect: OK' if not failures else f'aspect: {failures} FAILED')
sys.exit(1 if failures else 0)
