#!/usr/bin/env python3
"""16:9 for Fallout: Brotherhood of Steel (Xbox, USA): patch game/default.xbe.

    py -3 tools/widescreen.py [apply|revert|status] [path/to/default.xbe]

Nemesis2000's widescreen patch (Jay's Magic Patcher, "Fallout - Brotherhood
of Steel {Widescreen} (PAL) [Nemesis2000].JMP") made for the USA image. The
game keeps drawing into its 640x480 buffer, as on an Xbox set to widescreen:
the picture is anamorphic, and the framebuffer window shows it 16:9 (the port
reads the patched aspect back at start-up).

The PAL patch is a list of find/replace byte strings. Mapped by meaning onto
the USA build:

  * D-I: six `push 320.0` -- the second, height-side argument of the
    projection set-up at 0x87ED0 -- become `push 240.0`. The PAL build pushes
    three of them next to `push ecx`, two next to `push edx`, one next to
    `push eax`; the USA build happens to use ecx four times.
  * J-K: the aspect ratio 4:3 (1.3333) the camera set-up at 0x86980 is given
    becomes 16:9 (1.7778).
  * A-C: three 4x4 matrices whose diagonal is 496.0 get 372.0 in m00 only
    (x squeezed by 3/4). The PAL build stores the immediates; the USA build
    loads 496.0 from .rdata into xmm1 and stores it to m00 and m11, so the
    load and the two stores are rewritten as two immediate stores (xmm1 is
    reloaded by the next instruction in all three places).

Each site is checked against its original bytes before anything is written,
so another revision of the disc is refused rather than damaged. `apply` keeps
a copy of the file as it was as default.xbe.4x3 (for safekeeping; nothing
reads it); `revert` writes the original bytes back into these sites only, so
other patches (tools/russian.py) stay. The generated C has
to be redone afterwards (`./regen.sh --disasm`, then build): the patch is in
the code. Exit status: 0 nothing to do, 3 the file changed, 1 not this image.
"""
import os
import shutil
import struct
import sys

F320, F240 = struct.pack('<f', 320.0), struct.pack('<f', 240.0)
A43, A169 = bytes.fromhex('713DAA3F'), bytes.fromhex('398EE33F')   # 4/3, 16/9
F372, F496 = struct.pack('<f', 372.0), struct.pack('<f', 496.0)
NOP4 = b'\x90' * 4


def store(disp, imm):
    """mov dword ptr [esp+disp8], imm32"""
    return bytes([0xC7, 0x44, 0x24, disp]) + imm


def movss_load_496():
    return bytes.fromhex('F30F100DC4680E00')       # movss xmm1, [0x000E68C4]


def movss_store(disp):
    return bytes([0xF3, 0x0F, 0x11, 0x4C, 0x24, disp])   # movss [esp+disp8], xmm1


# (VA, original bytes, patched bytes, what)
SITES = []
for va, reg in ((0x0003292A, 0x51), (0x00032980, 0x51), (0x000329BF, 0x51),
                (0x0007C61D, 0x52), (0x000904A2, 0x51), (0x000904D0, 0x52)):
    SITES.append((va, b'\x68' + F320 + bytes([reg]), b'\x68' + F240 + bytes([reg]),
                  'projection: push 320.0 -> 240.0'))
for va in (0x00089454, 0x0008CC6D):
    SITES.append((va, b'\x68' + A43, b'\x68' + A169, 'camera aspect 4:3 -> 16:9'))
for va, m00, m11 in ((0x0008CE17, 0x50, 0x64), (0x0008CF95, 0x68, 0x7C)):
    SITES.append((va, movss_load_496() + movss_store(m00) + movss_store(m11),
                  store(m00, F372) + store(m11, F496) + NOP4,
                  'matrix m00 496.0 -> 372.0'))
MOV_EDI = bytes.fromhex('8B3D30C41C00')            # mov edi, [0x001CC430]
SITES.append((0x0008CEC3, movss_load_496() + MOV_EDI + movss_store(0x5C) + movss_store(0x70),
              MOV_EDI + store(0x5C, F372) + store(0x70, F496) + NOP4,
              'matrix m00 496.0 -> 372.0'))
for va, orig, new, _ in SITES:
    assert len(orig) == len(new), hex(va)


def sections(d):
    base = struct.unpack_from('<I', d, 0x104)[0]
    n, at = struct.unpack_from('<II', d, 0x11C)
    for i in range(n):
        _, va, _, raw, size, _ = struct.unpack_from('<IIIIII', d, at - base + i * 56)
        yield va, raw, size


def file_offset(d, va):
    for sva, raw, size in sections(d):
        if sva <= va < sva + size:
            return raw + va - sva
    return None


def state(d):
    """'4x3', '16x9', or None when the bytes are neither."""
    seen = set()
    for va, orig, new, _ in SITES:
        off = file_offset(d, va)
        if off is None:
            return None
        here = d[off:off + len(orig)]
        seen.add('4x3' if here == orig else '16x9' if here == new else None)
    return seen.pop() if len(seen) == 1 else None


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'status'
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xbe = argv[2] if len(argv) > 2 else os.path.join(root, 'game', 'default.xbe')
    backup = xbe + '.4x3'
    if cmd not in ('apply', 'revert', 'status'):
        print(__doc__)
        return 1
    with open(xbe, 'rb') as f:
        d = bytearray(f.read())
    st = state(d)
    if st is None:
        print(f'widescreen: {xbe} is not the USA image this patch is for; left as it is')
        return 1
    if cmd == 'status':
        print(f'widescreen: {xbe} is {"16:9" if st == "16x9" else "4:3"}')
        return 0
    if cmd == 'apply':
        if st == '16x9':
            print('widescreen: already 16:9')
            return 0
        if not os.path.exists(backup):
            shutil.copyfile(xbe, backup)
        for va, orig, new, what in SITES:
            off = file_offset(d, va)
            d[off:off + len(new)] = new
            print(f'  {va:#010x}  {what}')
        with open(xbe, 'wb') as f:
            f.write(d)
        print(f'widescreen: {xbe} patched to 16:9 ({len(SITES)} sites); original kept as {backup}')
        return 3
    if st == '4x3':
        print('widescreen: already 4:3')
        return 0
    for va, orig, new, _ in SITES:
        off = file_offset(d, va)
        d[off:off + len(orig)] = orig
    with open(xbe, 'wb') as f:
        f.write(d)
    print(f'widescreen: {xbe} back to 4:3')
    return 3


if __name__ == '__main__':
    sys.exit(main(sys.argv))
