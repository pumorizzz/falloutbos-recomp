#!/usr/bin/env python3
"""Russian for Fallout: Brotherhood of Steel (Xbox, USA): text and fonts in game/resx.

    py -3 tools/russian.py [apply|revert|status] [path/to/game/resx]
    py -3 tools/russian.py export [outdir]      English strings, one TSV per .sdb

The text is in game/resx/*.sdb, already UTF-16: a header (0x5DB, offset of the
hash table, string count), the strings, then a power-of-two hash table of
(hash, file offset) pairs. The game looks a string up by hash only, so a new
.sdb keeps every slot and hash and only gets new offsets.

The fonts (gamefonta/gamefontmed/gamefontsmall.fnt) are inside sfx.clp. The
renderer of the wide strings looks a glyph up by its Unicode code point in the
font's glyph table (0x71150), so Cyrillic needs no change to the game: each
font gets 71 more glyphs (U+0410..U+044F, Ё, ё, « » – — №) drawn from PT Sans
in the font's own style (white, 1 px dark outline) on rows added under its
atlas.  The text keeps the game's own button icons: { | } ~ and U+0080..U+008F
(written \\u0082 and so on in the TSV files).
The new fonts go at the end of sfx.clp; only their three entries in the
clump's table of contents and its CRC32 change.

The text is written in cp1251 code points, not U+04xx (see CP1251): several
of the game's paths keep only a byte. The fonts draw those code points with
the Cyrillic glyphs. Besides gtext/global/deftexte, each level's own .sdb
(resx/c*/<LEVEL>/<LEVEL>.sdb: object and enemy names) gets the names from
tools/ru/global_names.py, and twelve inventory strings inside the XBE are
rewritten in place (XBE_TEXT).

Translations: tools/ru/<name>.tsv and tools/ru/<name>/*.tsv, lines
"hash<TAB>text" (hash as in the export, \\n for a line break). A string with
no line keeps its English.

One fix in the code: the game's wide sprintf keeps only the low byte of the
format's own characters (see XBE_SITES), so `apply` also patches 4 bytes of
game/default.xbe, checked against the original; regenerate and build after
it (./regen.sh, cmake --build). widescreen.py's revert restores its 4:3 copy
without this patch: run `apply` again after it.

`apply` keeps the originals: <name>.sdb.en, and sfx.clp.en (its size, header
and table of contents); `revert` puts them and the XBE bytes back. It also
leaves the Russian set as <name>.sdb.ru: bin/FalloutLauncher.exe copies the
.en or .ru set over <name>.sdb by its Language choice. The fonts and the XBE
fix suit English as well (Latin glyphs and ASCII are unchanged). Exit status: 0 nothing to
do, 3 files changed, 1 error.
"""
import os
import re
import shutil
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RU = os.path.join(ROOT, 'tools', 'ru')
SDBS = ('gtext.sdb', 'global.sdb', 'deftexte.sdb')
FONTS = ('gamefonta.fnt', 'gamefontmed.fnt', 'gamefontsmall.fnt')
# Cyrillic, and the Russian punctuation the fonts lack: « » – — №
CYRILLIC = [0x401] + list(range(0x410, 0x450)) + [0x451] + [0xAB, 0xBB, 0x2013, 0x2014, 0x2116]

# The text goes into the game as cp1251 code points (А = U+00C0 ... я = U+00FF,
# Ё = U+00A8, ё = U+00B8, – — № = U+0096 U+0097 U+00B9), not as U+04xx.
# Several paths are 8-bit: "%s" in the wide sprintf, the names of items and
# objects ("Pick up %s"), the strings inside the XBE, save names. They keep
# the low byte of a character, which for U+0411 'Б' is 0x11 and for 'е' '5';
# a cp1251 code point survives the trip and comes back as itself. The fonts
# draw those code points with the Cyrillic glyphs (add_cyrillic), in their
# table of glyphs and in their byte map alike.
CP1251 = {c: ord(c.encode('cp1251')) for c in
          [chr(x) for x in [0x401] + list(range(0x410, 0x450)) + [0x451, 0x2013, 0x2014, 0x2116]]}
# Except 'я': its cp1251 byte is 0xFF, a signed -1 on the 8-bit paths. The
# player's name ("Надя") goes through one, and with 0xFF in it her model fell
# apart into spikes. 0x9F is free (no icon, no English text uses it).
CP1251['я'] = 0x9F


def to_game(text):
    return ''.join(chr(CP1251[c]) if c in CP1251 else c for c in text)


def from_game(text):
    back = {chr(v): k for k, v in CP1251.items()}
    return ''.join(back.get(c, c) for c in text)


# ---- .sdb ---------------------------------------------------------------------

def table_slots(n):
    """The game's hash table size for n entries (0x38BC0, the same for .clp):
    a power of two, 2-4 times n. The bytes after the table are padding, not
    always zero (the level .sdb files carry garbage there)."""
    e = ((n >> 1) + n) >> 1
    bits = 1
    while e:
        e >>= 1
        bits += 1
    return 1 << bits


def sdb_read(d):
    """[(slot, hash, text)] in file order of the strings, and the slot count."""
    magic, tbl, cnt = struct.unpack_from('<III', d, 0)
    if magic != 0x5DB:
        raise ValueError('not an .sdb')
    slots = table_slots(cnt)
    if tbl + slots * 8 > len(d):
        raise ValueError('hash table past the end of the file')
    out = []
    for i in range(slots):
        h, o = struct.unpack_from('<II', d, tbl + i * 8)
        if h or o:
            if o >= tbl:
                raise ValueError('string offset past the strings')
            e = o
            while e < tbl and d[e:e + 2] != b'\0\0':
                e += 2
            out.append((o, i, h, d[o:e].decode('utf-16le')))
    if len(out) != cnt:
        raise ValueError('string count does not match the header')
    out.sort()
    return [(i, h, s) for _, i, h, s in out], slots


def sdb_write(ents, slots, pad):
    pool = bytearray()
    table = bytearray(slots * 8)
    for i, h, s in ents:
        struct.pack_into('<II', table, i * 8, h, 12 + len(pool))
        pool += s.encode('utf-16le') + b'\0\0'
    d = struct.pack('<III', 0x5DB, 12 + len(pool), len(ents)) + pool + table
    if pad:
        d += b'\0' * (-len(d) % pad)
    return d


def tsv_read(path):
    m = {}
    with open(path, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip('\r\n')
            if not line or line.startswith('#'):
                continue
            h, _, text = line.partition('\t')
            # \n is a line break; \uXXXX a code the font draws as a button
            # icon (U+0080..U+008F), invisible in an editor
            text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda c: chr(int(c.group(1), 16)), text)
            m[int(h, 16)] = text.replace('\\n', '\n')
    return m


# ---- .clp ---------------------------------------------------------------------

def name_hash(name):
    v = 0
    for ch in name.encode('latin-1'):
        if ch == 0x5C:
            ch = 0x2F
        c = ch - 256 if ch >= 128 else ch
        v = ((((v * 0x80000025) & 0xFFFFFFFF) ^ (v >> 27)) ^ (c & 0xFFFFFFFF)) & 0xFFFFFFFF
    return v


def clp_toc(f):
    """(header bytes, toc offset, toc bytes, slot count)"""
    f.seek(0)
    hdr = f.read(24)
    magic, _, sec, crc, n, _ = struct.unpack('<6I', hdr)
    if magic != 0x434C4D50:
        raise ValueError('not a clump')
    e = ((n >> 1) + n) >> 1
    bits = 1
    while e:
        e >>= 1
        bits += 1
    slots = 1 << bits
    f.seek(sec << 12)
    toc = f.read(slots * 20)
    if zlib.crc32(toc) != crc:
        raise ValueError('clump table of contents fails its CRC')
    return hdr, sec << 12, toc, slots


def clp_find(toc, slots, name):
    h = name_hash(name)
    for i in range(slots):
        e = struct.unpack_from('<5I', toc, i * 20)
        if e[0] == h:
            return i, e
    raise KeyError(name)


# ---- fonts --------------------------------------------------------------------

class Font:
    def __init__(self, d):
        self.n, self.v, self.nk, g, k, t = struct.unpack_from('<HHIIII', d, 0)
        self.head = d[:0x14]
        self.cmap = bytearray(d[0x14:g])        # u16[256]: byte -> glyph, 8-bit text
        self.glyphs = [list(struct.unpack_from('<Hhhhhhhh', d, g + i * 16)) for i in range(self.n)]
        self.kern = d[k:t]
        self.w, self.h, self.fmt, hs = struct.unpack_from('<HHII', d, t)
        self.texhead = d[t:t + hs]
        self.pal = list(struct.unpack_from('<256I', d, t + hs))
        self.px = bytearray(d[t + hs + 1024:t + hs + 1024 + self.w * self.h])
        if self.fmt != 0xC044 or len(self.px) != self.w * self.h:
            raise ValueError('unexpected font texture')

    def glyph(self, ch):
        for g in self.glyphs:
            if g[0] == ch:
                return g
        raise KeyError(ch)

    def pack(self):
        g = 0x14 + len(self.cmap)
        k = g + 16 * len(self.glyphs)
        t = k + len(self.kern)
        head = struct.pack('<HHIIII', len(self.glyphs), self.v, self.nk, g, k, t)
        th = bytearray(self.texhead)
        struct.pack_into('<HH', th, 0, self.w, self.h)
        return (head + self.cmap + b''.join(struct.pack('<Hhhhhhhh', *x) for x in self.glyphs)
                + self.kern + th + struct.pack('<256I', *self.pal) + self.px)

    def ink(self, g):
        """rows/cols of the white core of a glyph, relative to its box"""
        _, x0, x1, y0, y1 = g[:5]
        rows = [y - y0 for y in range(y0, y1) if any(((self.pal[self.px[y * self.w + x]] >> 8) & 255) > 0x80 for x in range(x0, x1))]
        return rows[0], rows[-1]


def add_cyrillic(font, ttf):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    H = font.glyph(ord('H'))
    top, bot = font.ink(H)
    cap = bot - top + 1                       # cap height in pixels
    baseline = H[5] + bot + 1                  # from the top of the line
    soft = any(0x10 < (font.pal[font.px[y * font.w + x]] >> 24) < 0xF0
               for y in range(H[3], H[4]) for x in range(H[1], H[2]))
    xt, xb = font.ink(font.glyph(ord('x')))
    xh = xb - xt + 1                           # x-height in pixels

    def fit(letter, want):                     # PT Sans size whose `letter` is `want` px tall
        def miss(s):
            b = ImageFont.truetype(ttf, s).getbbox(letter)
            return abs(b[3] - b[1] - want)
        return min(range(want, want * 2), key=lambda s: (miss(s), s))

    # PT Sans has a smaller x-height than the game's font (0.7 of the caps
    # against 0.77): capitals and small letters are sized apart
    size = fit('H', cap)
    pf_caps = ImageFont.truetype(ttf, size)
    pf_small = ImageFont.truetype(ttf, fit('x', xh))

    # (alpha, grey) of every palette entry, for the nearest match
    pal = [((c >> 24) & 255, (c >> 8) & 255) for c in font.pal]
    cache = {}

    def nearest(a, gr):
        key = (a, gr)
        if key not in cache:
            cache[key] = min(range(256), key=lambda i: (pal[i][0] - a) ** 2 * 2 + (pal[i][1] - gr) ** 2)
        return cache[key]

    tiles = []
    for ch in CYRILLIC:
        s = chr(ch)
        pf = pf_small if s.islower() else pf_caps
        l, t_, r, b = pf.getbbox(s)
        if r <= l:
            continue
        w, h = r - l + 2, b - t_ + 2
        im = Image.new('L', (w, h), 0)
        ImageDraw.Draw(im).text((1 - l, 1 - t_), s, font=pf, fill=255)
        # ink top over the baseline, which is where 'x'/'H' ends in this size
        rise = pf.getbbox('x' if pf is pf_small else 'H')[3] - t_
        if not soft:                           # the small font has hard edges
            im = im.point(lambda v: 254 if v > 110 else 0)
        # drop faint side columns: the original glyphs are inked edge to edge,
        # with only the 1 px border around them
        cols = [i for i in range(w) if max(im.getpixel((i, j)) for j in range(h)) >= 96]
        im = im.crop((cols[0] - 1, 0, cols[-1] + 2, h))
        w = im.width
        halo = im.filter(ImageFilter.MaxFilter(3))
        if not soft:
            halo = halo.point(lambda v: 254 if v > 40 else 0)
        tiles.append((ch, im, halo, w, h, rise))
    # shelf packing under the old atlas
    x = y = 0
    row_h = 0
    y0 = font.h + 1
    placed = []
    for ch, im, halo, w, h, rise in tiles:
        if x + w > font.w:
            x, y, row_h = 0, y + row_h + 1, 0
        placed.append((ch, im, halo, x, y0 + y, w, h, rise))
        x += w + 1
        row_h = max(row_h, h)
    new_h = y0 + y + row_h + 1
    font.px += bytes(font.w * (new_h - font.h))
    zero = nearest(0, 0)
    for i in range(font.w * font.h, len(font.px)):
        font.px[i] = zero
    font.h = new_h
    for ch, im, halo, x, y, w, h, rise in placed:
        core, edge = im.load(), halo.load()
        for j in range(h):
            for i in range(w):
                a = max(core[i, j], edge[i, j])
                font.px[(y + j) * font.w + x + i] = nearest(min(a, 254), min(core[i, j], 254))
        # box top from the line top; the box has a 1 px border above the ink
        yoff = baseline - rise - 1
        font.glyphs.append([ch, x, x + w, y, y + h, yoff, w, -1])
    # The cp1251 code points (see CP1251) name the same glyphs. The Latin-1
    # letters that held those codes (À..ÿ, ¨ ¸ ¹) move to U+E000 + code:
    # the game looks a glyph up by the first match.
    codes = set(CP1251.values())
    for g in font.glyphs:
        if g[0] in codes:
            g[0] = 0xE000 + g[0]
    index = {g[0]: i for i, g in enumerate(font.glyphs)}
    for c, cp in CP1251.items():
        if ord(c) not in index:
            continue
        g = list(font.glyphs[index[ord(c)]])
        g[0] = cp
        font.glyphs.append(g)
        struct.pack_into('<H', font.cmap, cp * 2, len(font.glyphs) - 1)
    return size


def font_ttf():
    return os.path.join(RU, 'fonts', 'PT_Sans-Web-Bold.ttf')


# ---- commands -----------------------------------------------------------------

def export(outdir):
    os.makedirs(outdir, exist_ok=True)
    resx = os.path.join(ROOT, 'game', 'resx')
    for name in SDBS:
        src = os.path.join(resx, name)
        if os.path.exists(src + '.en'):
            src += '.en'
        ents, _ = sdb_read(open(src, 'rb').read())
        out = os.path.join(outdir, name[:-4] + '.tsv')
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            for _, h, s in ents:
                s = re.sub('[\x80-\x9f]', lambda c: '\\u%04x' % ord(c.group()), s.replace('\n', '\\n'))
                f.write('%08x\t%s\n' % (h, s))
        print(f'russian: {len(ents)} strings -> {out}')
    return 0


def level_sdbs(resx):
    """Each level's own strings, the names of its objects and characters:
    resx/c1/TUTOR/TUTOR.sdb and the like (61 files)."""
    out = []
    for c in sorted(os.listdir(resx)):
        cdir = os.path.join(resx, c)
        if not (os.path.isdir(cdir) and re.fullmatch(r'c\d', c)):
            continue
        for lvl in sorted(os.listdir(cdir)):
            p = os.path.join(cdir, lvl, lvl + '.sdb')
            if os.path.exists(p):
                out.append(p)
    return out


def names():
    """Display names by English text, from tools/ru/global_names.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('global_names', os.path.join(RU, 'global_names.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.NAMES


def sdb_one(path, tr, by_text=False):
    """Rebuild <path> from <path>.en with tr (hash -> Russian, or English text
    -> Russian when by_text), written in cp1251 code points. Keeps the
    Russian set as <path>.ru too: the launcher copies the .en or the .ru set
    over the .sdb before each start. (changed, translated, total)"""
    orig = path + '.en'
    if not os.path.exists(orig):
        shutil.copyfile(path, orig)
    d = open(orig, 'rb').read()
    ents, slots = sdb_read(d)
    if not by_text:
        known = {h for _, h, _ in ents}
        stray = [h for h in tr if h not in known]
        if stray:
            print(f'  {os.path.basename(path)}: {len(stray)} hashes not in the game, e.g. {stray[0]:08x}')
    key = (lambda h, s: s) if by_text else (lambda h, s: h)
    done = sum(1 for _, h, s in ents if key(h, s) in tr)
    ents = [(i, h, to_game(tr[key(h, s)]) if key(h, s) in tr else s) for i, h, s in ents]
    out = sdb_write(ents, slots, 2048 if len(d) % 2048 == 0 else 0)
    changed = open(path, 'rb').read() != out
    if changed:
        open(path, 'wb').write(out)
    if not os.path.exists(path + '.ru') or open(path + '.ru', 'rb').read() != out:
        open(path + '.ru', 'wb').write(out)
    return int(changed), done, len(ents)


def sdb_apply(resx):
    changed = 0
    for name in SDBS:
        base = os.path.join(RU, name[:-4])
        tsvs = [base + '.tsv'] if os.path.exists(base + '.tsv') else []
        if os.path.isdir(base):
            tsvs += [os.path.join(base, f) for f in sorted(os.listdir(base)) if f.endswith('.tsv')]
        if not tsvs:
            continue
        tr = {}
        for t in tsvs:
            tr.update(tsv_read(t))
        c, done, total = sdb_one(os.path.join(resx, name), tr)
        changed += c
        print(f'  {name}: {done} of {total} strings in Russian')
    nm = names()
    done = total = 0
    levels = level_sdbs(resx)
    for p in levels:
        c, dn, tt = sdb_one(p, nm, by_text=True)
        changed += c
        done += dn
        total += tt
    print(f'  {len(levels)} level .sdb: {done} of {total} strings in Russian (names)')
    return changed


def fonts_revert(resx):
    clp = os.path.join(resx, 'sfx.clp')
    bak = clp + '.en'
    if not os.path.exists(bak):
        return 0
    b = open(bak, 'rb').read()
    size, = struct.unpack_from('<Q', b, 0)
    hdr, toc = b[8:32], b[32:]
    with open(clp, 'r+b') as f:
        f.write(hdr)
        sec = struct.unpack_from('<6I', hdr)[2]
        f.seek(sec << 12)
        f.write(toc)
        f.truncate(size)
    os.remove(bak)
    return 1


def fonts_apply(resx):
    bold = font_ttf()
    if not os.path.exists(bold):
        print(f'russian: no {bold}; fonts left as they are')
        return 0
    fonts_revert(resx)
    clp = os.path.join(resx, 'sfx.clp')
    with open(clp, 'r+b') as f:
        hdr, toc_at, toc, slots = clp_toc(f)
        f.seek(0, 2)
        size = f.tell()
        open(clp + '.en', 'wb').write(struct.pack('<Q', size) + hdr + toc)
        toc = bytearray(toc)
        end = size + (-size % 4096)
        for name in FONTS:
            i, (h, sec, a, n, b) = clp_find(toc, slots, name)
            f.seek(sec << 12)
            font = Font(f.read(n))
            px = add_cyrillic(font, bold)
            data = font.pack()
            f.seek(end)
            f.write(data + b'\0' * (-len(data) % 4096))
            struct.pack_into('<5I', toc, i * 20, h, end >> 12, a, len(data), b)
            print(f'  {name}: +{len(CYRILLIC)} glyphs (PT Sans {px}px), atlas {font.w}x{font.h}')
            end += len(data) + (-len(data) % 4096)
        hdr = bytearray(hdr)
        struct.pack_into('<I', hdr, 12, zlib.crc32(toc))
        f.seek(0)
        f.write(hdr)
        f.seek(toc_at)
        f.write(toc)
    return 1


# ---- default.xbe ----------------------------------------------------------------
# The game's wide sprintf (0x72D20: "%u", "%d", "%c"... into a UTF-16 buffer)
# copies each plain character of the format with `movzx ax, byte ptr [ebx]`,
# the low byte only. English never notices; Cyrillic in a format string such
# as "%cВыбрать %u  %cНазад" comes out as "K1@0BL" (ы = U+044B -> 'K').
# `mov ax, word ptr [ebx]` + nop copies the whole character. The code changes,
# so the generated C has to be redone afterwards (./regen.sh, then build).
XBE_SITES = [(0x00072D46, bytes.fromhex('660FB603'), bytes.fromhex('668B0390'))]

# 8-bit text widened to UTF-16 with a sign: `movsx r16, r8`. A byte >= 0x80
# (the Cyrillic of CP1251) became 0xFFxx, which the renderer takes for a
# direct glyph index (c & 0xF800 == 0xF800): "Pick up %s" (0x729A0, its %s)
# measured hundreds of pixels wide and was cut to "...". `movzx` keeps the
# code point. The other eight are the game's other 8-bit-to-wide copies;
# for ASCII nothing changes.
for _va, _modrm in ((0x00014C32, 'C9'), (0x00030560, 'D2'), (0x000306D0, 'D2'),
                    (0x0003B192, 'D1'), (0x0003B3A1, 'D1'), (0x0003B4A0, 'D1'),
                    (0x0003B501, 'D1'), (0x0004F320, 'D2'), (0x00072AF4, 'C0')):
    XBE_SITES.append((_va, bytes.fromhex('660FBE' + _modrm), bytes.fromhex('660FB6' + _modrm)))

# The inventory's own 8-bit strings in .rdata, rewritten in place in cp1251
# (they come out as code points and the fonts map them, see CP1251): VA, the
# room (the string, its NUL and the zeros up to the next one), English,
# Russian. Data, not code: the runtime maps .rdata from the XBE at start-up,
# so these need no regeneration.
XBE_TEXT = [
    (0x000E402C, 20, 'Required Level: %d', 'Нужен уровень: %d'),
    (0x000E4040, 12, 'Cost: %d', 'Цена: %d'),
    (0x000E4104, 12, 'Next Level:', 'До уровня:'),
    (0x000E4140, 8, 'Caps:', 'Крышки:'),
    (0x000E4148, 8, 'Armor:', 'Броня:'),
    (0x000E4158, 8, 'Health:', 'Жизнь:'),
    (0x000E4160, 16, 'Skill Points:', 'Очки навыков:'),
    (0x000E4170, 12, 'Experience:', 'Опыт:'),
    (0x000E41AC, 12, 'No Quests', 'Нет заданий'),
    (0x000E4208, 12, 'No Weapons', 'Нет оружия'),
    (0x000E4214, 12, 'No Armor', 'Нет брони'),
    (0x000E4220, 12, 'No Items', 'Нет вещей'),
]


def xbe_text_sites():
    out = []
    for va, room, en, ru in XBE_TEXT:
        a, b = en.encode('ascii'), to_game(ru).encode('latin-1')
        assert len(a) < room and len(b) < room, en
        out.append((va, a + bytes(room - len(a)), b + bytes(room - len(b))))
    return out


def xbe_offset(d, va):
    base = struct.unpack_from('<I', d, 0x104)[0]
    n, at = struct.unpack_from('<II', d, 0x11C)
    for i in range(n):
        _, sva, _, raw, size, _ = struct.unpack_from('<IIIIII', d, at - base + i * 56)
        if sva <= va < sva + size:
            return raw + va - sva
    return None


def xbe_patch(xbe, to_new):
    """1 if the file changed, 0 if it already was so, -1 if not this image"""
    d = bytearray(open(xbe, 'rb').read())
    code = text = False
    sites = [(s, True) for s in XBE_SITES] + [(s, False) for s in xbe_text_sites()]
    for (va, orig, new), is_code in sites:
        o = xbe_offset(d, va)
        here = bytes(d[o:o + len(orig)]) if o is not None else b''
        want, other = (new, orig) if to_new else (orig, new)
        if here == want:
            continue
        if here != other:
            print(f'russian: {xbe} at {va:#010x} is neither the original nor the patch; left as it is')
            return -1
    for (va, orig, new), is_code in sites:
        o = xbe_offset(d, va)
        want = new if to_new else orig
        if d[o:o + len(want)] != want:
            d[o:o + len(want)] = want
            code |= is_code
            text |= not is_code
    if code or text:
        open(xbe, 'wb').write(d)
    state = 'patched' if to_new else 'original'
    if text:
        print(f'  default.xbe: {len(XBE_TEXT)} inventory strings ({state})')
    if code:
        print(f'  default.xbe: wide sprintf copies whole characters ({state}); '
              'regenerate and build (./regen.sh, cmake --build)')
    return 1 if code or text else 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'status'
    if cmd == 'export':
        return export(argv[2] if len(argv) > 2 else os.path.join(ROOT, 'scratch', 'ru', 'en'))
    resx = argv[2] if len(argv) > 2 else os.path.join(ROOT, 'game', 'resx')
    xbe = os.path.join(os.path.dirname(resx), 'default.xbe')
    if cmd == 'status':
        def same(a, b):
            return os.path.exists(b) and open(a, 'rb').read() == open(b, 'rb').read()
        # the launcher may have copied either set into place
        sdb = [n for n in SDBS if same(os.path.join(resx, n), os.path.join(resx, n + '.ru'))]
        fnt = os.path.exists(os.path.join(resx, 'sfx.clp.en'))
        d = open(xbe, 'rb').read()
        o = xbe_offset(d, XBE_SITES[0][0])
        fix = d[o:o + 4] == XBE_SITES[0][2]
        print(f'russian: text {"in Russian: " + ", ".join(sdb) if sdb else "English"}; '
              f'fonts {"with Cyrillic" if fnt else "original"}; '
              f'default.xbe {"patched" if fix else "original"}')
        return 0
    if cmd == 'apply':
        x = xbe_patch(xbe, True)
        if x < 0:
            return 1
        n = sdb_apply(resx) + fonts_apply(resx) + x
        print('russian: applied' if n else 'russian: nothing to do')
        return 3 if n else 0
    if cmd == 'revert':
        x = xbe_patch(xbe, False)
        n = fonts_revert(resx) + max(x, 0)
        for p in [os.path.join(resx, name) for name in SDBS] + level_sdbs(resx):
            if os.path.exists(p + '.en'):
                shutil.copyfile(p + '.en', p)
                os.remove(p + '.en')
                n += 1
            if os.path.exists(p + '.ru'):
                os.remove(p + '.ru')
        print('russian: back to English' if n else 'russian: already English')
        return 3 if n else 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
