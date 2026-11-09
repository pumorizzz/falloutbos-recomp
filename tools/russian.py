#!/usr/bin/env python3
"""Russian for Fallout: Brotherhood of Steel (Xbox, USA): text and fonts in game/resx.

    py -3 tools/russian.py [apply|revert|status] [path/to/game/resx]
    py -3 tools/russian.py export [outdir]      English strings, one TSV per .sdb
    py -3 tools/russian.py code-mark <out.c>    regen.sh: the code fixes the C has

The text is in game/resx/*.sdb, already UTF-16: a header (0x5DB, offset of the
hash table, string count), the strings, then a power-of-two hash table of
(hash, file offset) pairs. The game looks a string up by hash only, so a new
.sdb keeps every slot and hash and only gets new offsets.

The fonts (gamefonta/gamefontmed/gamefontsmall.fnt) are inside sfx.clp. The
wide renderer looks a glyph up by its code (0x71150), the 8-bit one through a
byte map. Each font gets 71 glyphs (А-я, Ё, ё, « » – — №) drawn from PT Sans in
its own style (white, 1 px dark outline) on rows added under its atlas, under
their Unicode codes and again under the codes of CP1251. The new fonts go at
the end of sfx.clp; only three entries of the clump's table of contents and
its CRC32 change. The text keeps the game's button icons: { | } ~ and
U+0080..U+008F (written \\u0082 and so on in the TSV files).

The text is written in cp1251 code points, not U+04xx (see CP1251): several
of the game's paths keep only a byte. Besides gtext/global/deftexte, each
level's own .sdb (resx/c*/<LEVEL>/<LEVEL>.sdb: object and enemy names) gets
the names from tools/ru/global_names.py, and thirteen strings inside the XBE
(the inventory's labels, the loading screen's "Loading...") are rewritten in
place (XBE_TEXT).

Translations: tools/ru/<name>.tsv and tools/ru/<name>/*.tsv, lines
"hash<TAB>text" (hash as in the export, \\n for a line break). A string with
no line keeps its English.

Code fixes (XBE_SITES, ten 4-byte sites of game/default.xbe, each checked
against its original bytes): the wide sprintf kept only the low byte of the
format's own characters, and the game's 8-bit-to-wide copies widened with a
sign. Regenerate and build after them (./regen.sh --disasm, cmake --build).
widescreen.py touches only its own sites, so they survive its apply and
revert.

`apply` keeps the originals: <name>.sdb.en, and sfx.clp.en (its size, header
and table of contents); `revert` puts them and the XBE bytes back. Backups
and rewritten files go through a temporary file and a rename, and a damaged
sfx.clp.en is refused rather than written back. It leaves both languages
installed: every .sdb as .sdb.en and .sdb.ru, default.xbe as default.xbe.en
and .ru (the same code, the XBE strings in English or Russian), and the
Russian set in place. bin/FalloutLauncher.exe copies one .sdb set into place
by its Language choice and sets the bytes in which the two XBEs differ (the
strings) in default.xbe, leaving its code alone; the fonts and the code fixes
suit English as well. Exit status: 0 nothing to do, 3 files changed, 1 error
(nothing written when it is found before the first change).
"""
import os
import re
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


def write_file(path, data):
    """Through <path>.tmp and a rename: a crash leaves the old file or the
    new one, never half of either (a cut-off .en backup was the original
    lost for good)."""
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_file(path):
    with open(path, 'rb') as f:
        return f.read()



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
    resx/c1/TUTOR/TUTOR.sdb and the like (53 on the USA disc)."""
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
    try:
        if not os.path.exists(orig):
            sdb_read(read_file(path))          # a whole .sdb, not a cut-off one
            write_file(orig, read_file(path))
        d = read_file(orig)
        ents, slots = sdb_read(d)
    except ValueError as e:
        raise ValueError(f'{orig if os.path.exists(orig) else path}: {e}; '
                         'restore the .sdb from the disc and delete its .en') from None
    if not by_text:
        known = {h for _, h, _ in ents}
        stray = [h for h in tr if h not in known]
        if stray:
            print(f'  {os.path.basename(path)}: {len(stray)} hashes not in the game, e.g. {stray[0]:08x}')
    key = (lambda h, s: s) if by_text else (lambda h, s: h)
    done = sum(1 for _, h, s in ents if key(h, s) in tr)
    ents = [(i, h, to_game(tr[key(h, s)]) if key(h, s) in tr else s) for i, h, s in ents]
    out = sdb_write(ents, slots, 2048 if len(d) % 2048 == 0 else 0)
    changed = read_file(path) != out
    if changed:
        write_file(path, out)
    if not os.path.exists(path + '.ru') or read_file(path + '.ru') != out:
        write_file(path + '.ru', out)
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


def clp_backup(bak):
    """(original size, header, table of contents) from sfx.clp.en, checked:
    a cut-off backup written back would leave a clump the game refuses."""
    b = read_file(bak)
    if len(b) < 32:
        raise ValueError(f'{bak} is damaged; restore sfx.clp from the disc and delete it')
    size, = struct.unpack_from('<Q', b, 0)
    hdr, toc = b[8:32], b[32:]
    magic, _, _, crc, n, _ = struct.unpack('<6I', hdr)
    if magic != 0x434C4D50 or len(toc) != table_slots(n) * 20 or zlib.crc32(toc) != crc:
        raise ValueError(f'{bak} is damaged; restore sfx.clp from the disc and delete it')
    return size, hdr, toc


def fonts_revert(resx):
    clp = os.path.join(resx, 'sfx.clp')
    bak = clp + '.en'
    if not os.path.exists(bak):
        return 0
    size, hdr, toc = clp_backup(bak)
    with open(clp, 'r+b') as f:
        f.write(hdr)
        sec = struct.unpack_from('<6I', hdr)[2]
        f.seek(sec << 12)
        f.write(toc)
        f.truncate(size)
        f.flush()
        os.fsync(f.fileno())
    os.remove(bak)
    return 1


def fonts_apply(resx):
    """1 if sfx.clp changed, 0 if its fonts already were these, -1 (nothing
    written) when it cannot be done."""
    bold = font_ttf()
    if not os.path.exists(bold):
        print(f'russian: no {bold}; fonts left as they are')
        return 0
    try:
        import PIL.Image  # noqa: F401  -- before anything is written
    except ImportError:
        print('russian: Pillow is missing (py -3 -m pip install pillow); nothing written')
        return -1
    clp = os.path.join(resx, 'sfx.clp')
    bak = clp + '.en'
    with open(clp, 'r+b') as f:
        if os.path.exists(bak):
            # Everything from the backup: an apply cut short between the
            # header and the table of contents leaves a CRC that fails, and
            # this apply writes both again.
            size, hdr, toc = clp_backup(bak)
            toc_at = struct.unpack_from('<6I', hdr)[2] << 12
            slots = len(toc) // 20
            try:
                cur_toc = clp_toc(f)[2]
            except ValueError:
                cur_toc = None
        else:
            try:
                _, toc_at, cur_toc, slots = clp_toc(f)
            except ValueError as e:
                raise ValueError(f'{clp}: {e}; restore it from the disc') from None
            f.seek(0, 2)
            size = f.tell()
            f.seek(0)
            hdr, toc = f.read(24), cur_toc
            # Without sfx.clp.en the fonts must be the original ones: drawing
            # Cyrillic into fonts that have it already would stack a second set.
            for name in FONTS:
                _, (_, sec, _, n, _) = clp_find(toc, slots, name)
                f.seek(sec << 12)
                if any(g[0] == 0x410 for g in Font(f.read(n)).glyphs):
                    print(f'russian: {name} in sfx.clp has Cyrillic already but sfx.clp.en is gone; '
                          'restore the original sfx.clp from the disc first; nothing written')
                    return -1
        backup = struct.pack('<Q', size) + bytes(hdr) + bytes(toc)
        # The new fonts, drawn from the originals (apply only ever appends,
        # so their sectors are untouched), and where they go: after the
        # original end of the file.
        toc = bytearray(toc)
        end = size + (-size % 4096)
        blob = bytearray()
        for name in FONTS:
            i, (h, sec, a, n, b) = clp_find(toc, slots, name)
            f.seek(sec << 12)
            font = Font(f.read(n))
            px = add_cyrillic(font, bold)
            data = font.pack()
            struct.pack_into('<5I', toc, i * 20, h, (end + len(blob)) >> 12, a, len(data), b)
            print(f'  {name}: +{len(CYRILLIC)} glyphs (PT Sans {px}px), atlas {font.w}x{font.h}')
            blob += data + b'\0' * (-len(data) % 4096)
        hdr = bytearray(hdr)
        struct.pack_into('<I', hdr, 12, zlib.crc32(toc))
        f.seek(0, 2)
        if f.tell() == end + len(blob) and cur_toc is not None and bytes(cur_toc) == bytes(toc):
            f.seek(end)
            if f.read(len(blob)) == blob:
                return 0                       # already these fonts
        if not os.path.exists(bak):
            write_file(bak, backup)
        f.truncate(end)
        f.seek(end)
        f.write(blob)
        f.seek(0)
        f.write(hdr)
        f.seek(toc_at)
        f.write(toc)
        f.flush()
        os.fsync(f.fileno())
    return 1


# ---- default.xbe ----------------------------------------------------------------
# The game's wide sprintf (0x72D20: "%u", "%d", "%c"... into a UTF-16 buffer)
# copies each plain character of the format with `movzx ax, byte ptr [ebx]`,
# the low byte only. English never notices; Cyrillic in a format string such
# as "%cВыбрать %u  %cНазад" comes out as "K1@0BL" (ы = U+044B -> 'K').
# `mov ax, word ptr [ebx]` + nop copies the whole character. The code changes,
# so the generated C has to be redone afterwards (./regen.sh, then build).
# The launcher checks these ten VAs too (k_code_va): keep the lists alike.
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

# The game's own 8-bit strings in .rdata (the inventory's labels, the loading
# screen's caption), rewritten in place in cp1251 (they come out as code
# points and the fonts map them, see CP1251): VA, the room (the string, its
# NUL and the zeros up to the next one), English, Russian. Data, not code:
# the runtime maps .rdata from the XBE at start-up, so these need no
# regeneration.
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
    # the loading screen's caption (0x90444: gamefonta, 8-bit, at 280,396)
    (0x000E69DC, 12, 'Loading...', 'Загрузка...'),
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


def xbe_patch(xbe, to_new, dry=False):
    """1 if the file changed (or would, when dry), 0 if it already was so,
    -1 if not this image"""
    d = bytearray(read_file(xbe))
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
    if dry:
        return 1 if code or text else 0
    if code or text:
        write_file(xbe, d)
    state = 'patched' if to_new else 'original'
    if text:
        print(f'  default.xbe: {len(XBE_TEXT)} strings: inventory, loading screen ({state})')
    if code:
        print(f'  default.xbe: wide sprintf copies whole characters ({state}); '
              'regenerate and build (./regen.sh, cmake --build)')
    return 1 if code or text else 0


def xbe_variants(xbe):
    """default.xbe.en and .ru: the same code (all XBE_SITES applied), the
    XBE_TEXT strings in English or Russian. They differ only in those
    strings in .rdata, which the runtime maps at start-up; the launcher sets
    just the differing bytes in default.xbe by its Language choice, so a
    later widescreen.py apply/revert there stays, and nothing needs
    regenerating."""
    d = bytearray(read_file(xbe))
    for lang in ('en', 'ru'):
        for va, orig, new in xbe_text_sites():
            o = xbe_offset(d, va)
            d[o:o + len(orig)] = new if lang == 'ru' else orig
        out = xbe + '.' + lang
        if not os.path.exists(out) or read_file(out) != d:
            write_file(out, d)


def code_mark(xbe, out):
    """regen.sh, after generating the C: write <out>, a C file whose string
    says how many of XBE_SITES the XBE had. It is built into bin/fobos.exe,
    and the launcher reads it there: the code that runs is the generated C,
    so the XBE on disk alone cannot say whether the game has the fixes."""
    d = read_file(xbe)
    n = 0
    for va, _, new in XBE_SITES:
        o = xbe_offset(d, va)
        n += o is not None and d[o:o + len(new)] == new
    src = ('/* tools/russian.py code-mark (regen.sh): of its code fixes, the ones\n'
           ' * default.xbe had when this C was generated. FalloutLauncher.exe\n'
           ' * reads the string from bin/fobos.exe. */\n'
           '#ifdef _MSC_VER\n'
           '#pragma comment(linker, "/INCLUDE:fbos_ru_code_fixes")\n'
           '#define FBOS_USED\n'
           '#else\n'
           '#define FBOS_USED __attribute__((used))\n'
           '#endif\n'
           f'FBOS_USED const char fbos_ru_code_fixes[] = "FBOS-RU-CODE-FIXES {n}/{len(XBE_SITES)}";\n')
    if not os.path.exists(out) or read_file(out) != src.encode('ascii'):
        write_file(out, src.encode('ascii'))
    print(f'russian: generated C has {n}/{len(XBE_SITES)} of the code fixes')
    return 0


def main(argv):
    try:
        return run(argv)
    except ValueError as e:                    # a damaged file: said, not a traceback
        print(f'russian: {e}')
        return 1


def run(argv):
    cmd = argv[1] if len(argv) > 1 else 'status'
    if cmd == 'export':
        return export(argv[2] if len(argv) > 2 else os.path.join(ROOT, 'scratch', 'ru', 'en'))
    if cmd == 'code-mark':
        if len(argv) < 3:
            print(__doc__)
            return 1
        xbe = os.path.join(ROOT, 'game', 'default.xbe')
        if not os.path.isfile(xbe):
            print(f'russian: no {xbe}; unpack the game first')
            return 1
        return code_mark(xbe, argv[2])
    resx = argv[2] if len(argv) > 2 else os.path.join(ROOT, 'game', 'resx')
    xbe = os.path.join(os.path.dirname(resx), 'default.xbe')
    if cmd in ('status', 'apply', 'revert') and not os.path.isfile(xbe):
        print(f'russian: no {xbe}; give the resx folder of the unpacked game '
              '(default.xbe beside it)')
        return 1
    if cmd == 'status':
        def same(a, b):
            return os.path.exists(b) and open(a, 'rb').read() == open(b, 'rb').read()
        # the launcher may have copied either set into place
        sdb = [n for n in SDBS if same(os.path.join(resx, n), os.path.join(resx, n + '.ru'))]
        fnt = os.path.exists(os.path.join(resx, 'sfx.clp.en'))
        d = open(xbe, 'rb').read()
        for va, orig, new in XBE_SITES + xbe_text_sites():
            o = xbe_offset(d, va)
            if o is None or d[o:o + len(orig)] not in (orig, new):
                print(f'russian: {xbe} at {va:#010x} is neither the original nor the patch; '
                      'not the image these fixes are for')
                return 1

        def patched(sites):
            return sum(1 for va, _, new in sites if d[xbe_offset(d, va):xbe_offset(d, va) + len(new)] == new)
        print(f'russian: text {"in Russian: " + ", ".join(sdb) if sdb else "English"}; '
              f'fonts {"with Cyrillic" if fnt else "original"}; '
              f'default.xbe code fixes {patched(XBE_SITES)}/{len(XBE_SITES)}, '
              f'XBE strings {"Russian" if patched(xbe_text_sites()) else "English"}')
        return 0
    if cmd == 'apply':
        # Everything that can refuse does so before the first write: the
        # XBE (another disc), then the fonts (no Pillow, damaged backup).
        if xbe_patch(xbe, True, dry=True) < 0:
            return 1
        f = fonts_apply(resx)
        if f < 0:
            return 1
        x = xbe_patch(xbe, True)
        xbe_variants(xbe)
        n = sdb_apply(resx) + f + x
        print('russian: applied' if n else 'russian: nothing to do')
        return 3 if n else 0
    if cmd == 'revert':
        n = fonts_revert(resx)                 # first: it refuses a damaged backup
        x = xbe_patch(xbe, False)
        for s in ('.en', '.ru'):
            if os.path.exists(xbe + s):
                os.remove(xbe + s)
        n += max(x, 0)
        damaged = []
        for p in [os.path.join(resx, name) for name in SDBS] + level_sdbs(resx):
            if os.path.exists(p + '.en'):
                try:
                    sdb_read(read_file(p + '.en'))  # a cut-off backup is refused, not copied
                except ValueError as e:
                    # left as it is, .en and .ru included; the rest still go back
                    damaged.append(f'{p}.en ({e})')
                    continue
                write_file(p, read_file(p + '.en'))
                os.remove(p + '.en')
                n += 1
            if os.path.exists(p + '.ru'):
                os.remove(p + '.ru')
        if damaged:
            print('russian: these backups are damaged and their .sdb left as they are; '
                  'restore each .sdb from the disc and delete its .en:')
            for d in damaged:
                print('  ' + d)
            return 1
        print('russian: back to English' if n else 'russian: already English')
        return 3 if n else 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
