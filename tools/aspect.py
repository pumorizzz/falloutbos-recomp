#!/usr/bin/env python3
"""Aspect switch for Fallout: Brotherhood of Steel: 16:9, 16:10 or 4:3 chosen at start.

    py -3 tools/aspect.py neutral <in.xbe> <out.xbe>
    py -3 tools/aspect.py recomp <tools.recomp args...>     (run from the toolkit root)
    py -3 tools/aspect.py table <out.c>

tools/widescreen.py makes the picture 16:9 by rewriting 11 places in the XBE
code (projection height, camera aspect, three matrix diagonals). Those bytes
end up as constants in the generated C, so one exe drew one aspect. This
module takes the 11 places out of the generated C instead:

  * neutral: copies the XBE with the 11 places put back to their 4:3 bytes
    (whichever state the input is in), so a patched and an unpatched
    default.xbe give the same C. regen.sh runs the whole pipeline on that copy.
  * recomp: runs `tools.recomp` with a hook on the lifter: at each of the 13
    places (the 11 of widescreen.py and PORT_SITES) the one instruction that
    carries the aspect-dependent number is lifted as a read of
    g_fbos_aspect_site[i]; at the two port places the x is multiplied by the
    table's value. The toolkit itself is not changed. A place that does not
    hold the 4:3 instruction stops the run.
  * table: writes gen/recomp_fbos_aspect.c, the table, one set per FBOS_ASPECT
    value (4:3, 16:9 -- Nemesis2000's numbers -- and 16:10, worked out by the
    same rule), and fbos_aspect_select() that main.c calls at start-up with
    the choice made by FBOS_ASPECT.

The table has 13 entries: the 11 places of widescreen.py, then 2 places only
the port has (PORT_SITES): the x placement of the inventory's 3D models
(sub_00032A70: the character and the bar behind them; sub_00032DB0: the item
models), scaled by anchor_scale() so they stand where they do at 4:3. This is
where the port differs from Nemesis2000's patch: widescreen.py apply (for an
Xbox) stays as Nemesis made it, and there the models stand left of their 4:3
place.

Exit status: 0 done, 1 failed.
"""
import collections
import os
from fractions import Fraction
import struct
import sys

import widescreen as ws

N_WS = len(ws.SITES)         # 11: widescreen.py's places
RDATA_496 = 0x000E68C4

# FBOS_ASPECT's values, in table order: fbos_aspect_select(i) and main.c's
# k_fbos_aspect use these indices (tools/test_aspect.py checks main.c).
ASPECTS = (('4:3', 4, 3), ('16:9', 16, 9), ('16:10', 16, 10))
DEFAULT = 1                    # 16:9, also when FBOS_ASPECT is unset


def _u32(b):
    return struct.unpack('<I', bytes(b))[0]


CAMERA_43 = _u32(ws.A43)       # 1.33: the game's own camera aspect, not 4/3


def _f32(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]


def _bits(x):
    return _u32(struct.pack('<f', float(x)))


def value_at(kind, v43, n, d):
    """A site's number at aspect n:d. The game draws anamorphically into its
    4:3 buffer and the window stretches it to n:d, so the camera (0x86980:
    the frustum's width is tan * aspect) gets n/d itself, and the x scales --
    the projection's m00 = a1 * a3 at 0x87ED0, the matrices' m00 -- shrink by
    (4/3) / (n/d). Nemesis2000's 16:9 bytes follow this exactly; 4:3 stays
    the game's own (its camera is 1.33, not 4/3)."""
    if kind == 'push' and v43 == CAMERA_43:
        return _bits(Fraction(n, d))
    return _bits(Fraction(_f32(v43)) * Fraction(4, 3) / Fraction(n, d))


def anchor_scale(n, d):
    """k = 320 / the projection's x at aspect n:d = (n/d) / (4/3): 1 at 4:3,
    4/3 at 16:9, 1.2 at 16:10. The inventory's 3D models (the character and
    the bar behind them, the item models) are placed by a translation tx in
    view space, so on screen x = m00' * (tx + dx) / z with m00' the squeezed
    widescreen m00. Scaling tx by k gives
        x = m00' * (k * tx + dx) / z = m00 * tx / z + m00' * dx / z:
    the model stands where it does at 4:3 and keeps the widescreen
    proportions."""
    return _bits(Fraction(n, d) / Fraction(4, 3))


def _role(s):
    if s[1].startswith('anchor_'):
        return 'UI model x placement'
    if s[1] == 'push':
        return 'camera aspect' if s[3] == CAMERA_43 else 'projection x'
    return 'matrix m00'


def _site(va, orig, new):
    if orig[0] == 0x68:                                   # push imm32
        return (va, 'push', None, _u32(orig[1:5]), _u32(new[1:5]))
    # movss xmm1,[0xE68C4]; [mov edi,..]; movss [esp+m00],xmm1; movss [esp+m11],xmm1
    assert orig[:4] == bytes.fromhex('F30F100D') and _u32(orig[4:8]) == RDATA_496
    at = orig.index(bytes.fromhex('F30F114C24'))          # first store = m00
    disp = orig[at + 5]
    k = new.index(bytes([0xC7, 0x44, 0x24, disp]))
    return (va + at, 'movss', disp, _u32(ws.F496), _u32(new[k + 4:k + 8]))


# (hook_va, kind, disp, v4x3, v16x9, v16x10), in widescreen.SITES order:
# column 3 + i is ASPECTS[i]; 16:9 is Nemesis2000's bytes, 16:10 value_at()
SITES = [s + (value_at(s[1], s[3], 16, 10),)
         for s in (_site(va, o, n) for va, o, n, _ in ws.SITES)]

# Port-only places (not in widescreen.py, so not on an Xbox): the x of the
# translation that places a UI model, multiplied by anchor_scale().
# (hook_va, kind, disp) + one value per ASPECTS entry.
PORT_SITES = [
    # sub_00032A70, the inventory's right panel: the character and the bar's
    # mesh; movss [esp+0x14],xmm0 stores x before call 0x6F390 (out, x, y, z)
    (0x00032AC1, 'anchor_movss', 0x14),
    # sub_00032DB0, the item models in the list: mov eax,[esp+0x34] loads x
    # before call 0x6F390
    (0x00032EC0, 'anchor_mov', 0x34),
]
SITES += [s + tuple(anchor_scale(n, d) for _, n, d in ASPECTS) for s in PORT_SITES]
N = len(SITES)               # 13: 0..10 widescreen.py, 11 character, 12 items


def neutral_bytes(d):
    """The XBE image with every widescreen site at its 4:3 bytes."""
    st = ws.state(d)
    if st is None:
        raise ValueError("the image is neither the 4:3 nor the 16:9 USA image; "
                         "the aspect switch is generated for that image only")
    out = bytearray(d)
    for va, orig, new, _ in ws.SITES:
        off = ws.file_offset(out, va)
        out[off:off + len(orig)] = orig
    return bytes(out)


def _write_if_changed(path, data):
    try:
        with open(path, 'rb') as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)
    return True


def neutral(src, dst):
    with open(src, 'rb') as f:
        d = f.read()
    try:
        out = neutral_bytes(d)
    except ValueError as e:
        print(f'aspect: {src}: {e}')
        return 1
    was = '16:9' if ws.state(d) == '16x9' else '4:3'
    _write_if_changed(dst, out)
    print(f'aspect: generating from the {was} image, its {N_WS} sites at 4:3 ({dst})')
    return 0


def install(lifter_cls, fmt_mem):
    """Hook lifter_cls.lift_instruction; returns a Counter of sites lifted."""
    by_va = {s[0]: (i,) + s[1:4] for i, s in enumerate(SITES)}
    orig_lift = lifter_cls.lift_instruction
    hits = collections.Counter()

    def lift_instruction(self, insn):
        site = by_va.get(insn.address)
        if site is None:
            return orig_lift(self, insn)
        i, kind, disp, v43 = site
        ops = insn.operands
        if kind == 'push':
            ok = (insn.mnemonic == 'push' and len(ops) == 1 and ops[0].type == 'imm'
                  and (ops[0].imm & 0xFFFFFFFF) == v43 and insn.size == 5)
        elif kind == 'anchor_movss':
            ok = (insn.mnemonic == 'movss' and len(ops) == 2 and ops[0].type == 'mem'
                  and ops[0].mem_base == 'esp' and not ops[0].mem_index
                  and ops[0].mem_disp == disp and ops[1].type == 'reg'
                  and ops[1].reg == 'xmm0')
        elif kind == 'anchor_mov':
            ok = (insn.mnemonic == 'mov' and len(ops) == 2 and ops[0].type == 'reg'
                  and ops[0].reg == 'eax' and ops[1].type == 'mem'
                  and ops[1].mem_base == 'esp' and not ops[1].mem_index
                  and ops[1].mem_disp == disp)
        else:
            ok = (insn.mnemonic == 'movss' and len(ops) == 2 and ops[0].type == 'mem'
                  and ops[0].mem_base == 'esp' and not ops[0].mem_index
                  and ops[0].mem_disp == disp and ops[1].type == 'reg'
                  and ops[1].reg == 'xmm1')
        if not ok:
            raise SystemExit(
                f"aspect: 0x{insn.address:08X} is '{insn.mnemonic} {insn.op_str}', not the "
                f"4:3 instruction tools/aspect.py replaces; was the XBE normalised "
                f"(aspect.py neutral)?")
        hits[i] += 1
        ext = (f"extern uint32_t g_fbos_aspect_site[{N}]; "
               f"/* tools/aspect.py: FBOS_ASPECT picks the value */")
        if kind == 'push':
            return [ext, f"PUSH32(esp, g_fbos_aspect_site[{i}]); "
                         f"/* push 0x{v43:08X} at 4:3 */"]
        if kind == 'anchor_movss':
            return [ext, f"MEMF({fmt_mem(ops[0])}) = xmm0.f[0] * "
                         f"XMM_SCALAR_BITS(g_fbos_aspect_site[{i}]).f[0]; "
                         f"/* movss: UI model x placement x 320/projection x */"]
        if kind == 'anchor_mov':
            return [ext, f"{{ RecompXmm _fbos_x = XMM_SCALAR_BITS(MEM32({fmt_mem(ops[1])})); "
                         f"_fbos_x.f[0] *= XMM_SCALAR_BITS(g_fbos_aspect_site[{i}]).f[0]; "
                         f"eax = _fbos_x.u[0]; }} "
                         f"/* mov: UI model x placement x 320/projection x */"]
        return [ext, f"MEM32({fmt_mem(ops[0])}) = g_fbos_aspect_site[{i}]; "
                     f"/* movss m00, 0x{v43:08X} at 4:3 */"]

    lifter_cls.lift_instruction = lift_instruction
    return hits


def recomp(args):
    root = os.getcwd()
    if not os.path.isfile(os.path.join(root, 'tools', 'recomp', '__main__.py')):
        print('aspect: run from the toolkit root (tools/recomp/__main__.py not found)')
        return 1
    sys.path.insert(0, root)
    import tools.recomp.lifter as L
    import tools.recomp.__main__ as M
    hits = install(L.Lifter, L._fmt_mem)
    sys.argv = ['tools.recomp'] + list(args)
    M.main()
    missing = [i for i in range(N) if not hits[i]]
    if missing:
        print('aspect: sites never lifted: ' +
              ', '.join(f'[{i}] 0x{SITES[i][0]:08X}' for i in missing))
        return 1
    print(f'aspect: {N}/{N} sites read g_fbos_aspect_site (tools/aspect.py)')
    return 0


def table_c():
    lines = [
        '/* Generated by tools/aspect.py table (regen.sh). Do not edit.',
        ' * The 11 aspect-dependent numbers of tools/widescreen.py + 2 port-only',
        ' * sites (the x placement of UI models, sub_00032A70/sub_00032DB0), one',
        ' * set per FBOS_ASPECT value, read by the generated C as g_fbos_aspect_site[i];',
        ' * main.c picks the set at start-up through fbos_aspect_select(). */',
        '#include <stdint.h>',
        '',
    ]
    names = ['k_' + a[0].replace(':', 'x') for a in ASPECTS]
    for i, name in enumerate(names):
        lines.append(f'static const uint32_t {name}[{N}] = {{')
        for s in SITES:
            v = s[3 + i]
            lines.append(f'    0x{v:08X}, /* 0x{s[0]:08X} {s[1]}, {_role(s)}: '
                         f'{_f32(v):.6g} */')
        lines.append('};')
        lines.append('')
    idx = ', '.join(f'{i} {a[0]}' for i, a in enumerate(ASPECTS))
    lines.append(f'/* index = FBOS_ASPECT: {idx} (main.c k_fbos_aspect) */')
    lines.append(f'static const uint32_t *const k_sets[{len(ASPECTS)}] = '
                 f'{{ {", ".join(names)} }};')
    lines.append('')
    init = ', '.join(f'0x{s[3 + DEFAULT]:08X}' for s in SITES)
    lines.append(f'uint32_t g_fbos_aspect_site[{N}] = {{ {init} }};')
    lines.append('')
    lines.append('void fbos_aspect_select(int aspect)')
    lines.append('{')
    lines.append(f'    const uint32_t *v = k_sets[aspect >= 0 && aspect < {len(ASPECTS)} '
                 f'? aspect : {DEFAULT}];')
    lines.append('    int i;')
    lines.append(f'    for (i = 0; i < {N}; i++)')
    lines.append('        g_fbos_aspect_site[i] = v[i];')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def table(out):
    _write_if_changed(out, table_c().encode('ascii'))
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd == 'neutral' and len(argv) == 4:
        return neutral(argv[2], argv[3])
    if cmd == 'recomp' and len(argv) > 2:
        return recomp(argv[2:])
    if cmd == 'table' and len(argv) == 3:
        return table(argv[2])
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
