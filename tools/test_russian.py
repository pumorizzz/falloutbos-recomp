#!/usr/bin/env python3
"""Self-check of tools/russian.py (the Russian translation of Fallout: BoS).

Run: py -3 tools/test_russian.py   (from the port root; pytest is not installed)

Background: `apply` used to read the translation files only after it had
written the fonts and the XBE, so a bad line left the game half translated,
and the error did not say which file. A line with no TAB blanked its string
silently; a movie cue past what the port keeps (recomp_manual.c: 48 a movie,
191 bytes, 4 lines) was dropped unsaid. And on a copy of the XBE: a Russian an
earlier apply wrote must still count as this tool's own after the credits'
text changed, and `revert` must not delete the English backup it could not
restore from.

A, B and C need no data, D no data either (a temporary tree), E a copy of
game/default.xbe.en or game/default.xbe (missing: SKIP). F (.sdb.en4, the
language in place, revert) needs no data, G reads the .sdb.en of game/ (without
them SKIP). Nothing here writes into game\\.
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import russian  # noqa: E402

failures = 0


def check(ok, what, detail=''):
    global failures
    if not ok:
        failures += 1
    print(f'  {"PASS" if ok else "FAIL"}  {what}' + (f'  ({detail})' if detail and not ok else ''))


def write(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def raises(fn, *needles):
    """The ValueError's message if fn raises one with all the needles in it."""
    try:
        fn()
    except ValueError as e:
        return str(e) if all(n in str(e) for n in needles) else None
    return None


print('A  tsv_read')
with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, 'ok.tsv')
    write(p, '# comment\n00000001\tАб\\nв\\u0082\n')
    check(russian.tsv_read(p) == {1: 'Аб\nв\x82'}, 'a good line is read')
    for name, body in (('notab', '00000001 text\n'), ('badhash', 'zz\ttext\n'),
                       ('empty', '00000002\t\n')):
        q = os.path.join(t, name + '.tsv')
        write(q, body)
        check(raises(lambda: russian.tsv_read(q), q + ':1') is not None,
              f'{name}: ValueError naming file:line')
    q = os.path.join(t, 'second.tsv')
    write(q, '00000001\tok\n00000002 no tab\n')
    check(raises(lambda: russian.tsv_read(q), q + ':2') is not None, 'the line number is the line')
    q = os.path.join(t, 'latin.tsv')
    with open(q, 'wb') as f:
        f.write(b'00000001\t\xff\xfe\n')
    check(raises(lambda: russian.tsv_read(q), q, 'UTF-8') is not None, 'not UTF-8 names the file')

print('B  movie_subtitles')
saved_movies = russian.MOVIES
try:
    with tempfile.TemporaryDirectory() as t:
        mv = os.path.join(t, 'movies.tsv')
        russian.MOVIES = mv

        def cues(*lines):
            write(mv, ''.join(l + '\n' for l in lines))
            return russian.movie_subtitles()

        check(cues('x\t1.0\t2.0\ttext') == [(russian.name_hash('SUB_x'), '1.00 2.00 text')],
              'a good file gives the key and the cue')
        check(raises(lambda: cues('x\t1.0\t2.0'), mv + ':1') is not None, 'three fields: file:line')
        check(raises(lambda: cues('x\t1.0\t2.0\tt', 'x\tone\t2.0\tt'), mv + ':2') is not None,
              'start not a number: file:line')
        check(raises(lambda: cues(*['x\t%d.0\t%d.5\tt' % (i, i) for i in range(49)]), mv, '49 cues')
              is not None, '49 cues of one movie are refused')
        check(raises(lambda: cues('x\t1.0\t2.0\t' + 'x' * 192), mv + ':1', '192') is not None,
              'a cue of 192 bytes is refused')
        check(raises(lambda: cues('x\t1.0\t2.0\t' + '\\n'.join(['x'] * 5)), mv + ':1', '5 lines')
              is not None, 'a cue of 5 lines is refused')
        ok = cues(*['x\t%d.0\t%d.5\t%s' % (i, i, '\\n'.join(['x' * 47] * 4)) for i in range(48)])
        check(len(ok) == 1 and len(ok[0][1].split('\n')) == 48,
              '48 cues of 191 bytes and 4 lines pass')
finally:
    russian.MOVIES = saved_movies

print('C  the real translations')
try:
    pre = russian.translations()
    check(True, 'translations() reads and checks every TSV')
    check(len(pre[0]) >= 1, 'some .sdb has a translation', str(list(pre[0])))
except ValueError as e:
    check(False, 'translations() reads and checks every TSV', str(e))
try:
    russian.movie_subtitles()
    check(True, 'tools/ru/movies.tsv is within what the port draws')
except ValueError as e:
    check(False, 'tools/ru/movies.tsv is within what the port draws', str(e))

print('D  apply checks the translations before its first write')
names = ('RU', 'MOVIES', 'xbe_patch', 'fonts_apply', 'xbe_variants', 'sdb_apply', 'write_file')
saved = {n: getattr(russian, n) for n in names}
calls = []
try:
    with tempfile.TemporaryDirectory() as t:
        ru = os.path.join(t, 'ru')
        os.mkdir(ru)
        write(os.path.join(ru, 'global_names.py'), 'NAMES = {}\n')
        write(os.path.join(ru, 'gtext.tsv'), '00000001 no tab here\n')
        resx = os.path.join(t, 'resx')
        os.mkdir(resx)
        with open(os.path.join(t, 'default.xbe'), 'wb') as f:
            f.write(b'XBEH' + bytes(60))
        russian.RU = ru
        russian.MOVIES = os.path.join(t, 'no-movies.tsv')

        def xbe_patch(xbe, to_new, dry=False, text_new=None):
            calls.append(('xbe_patch', dry, text_new))
            return 0

        def fonts_apply(r):
            calls.append(('fonts_apply',))
            return 0

        def xbe_variants(xbe):
            calls.append(('xbe_variants',))
            return 0

        def sdb_apply(r, pre, lang='ru'):
            calls.append(('sdb_apply', pre))
            return 0

        def write_file(path, data):
            calls.append(('write_file', path))

        russian.xbe_patch, russian.fonts_apply, russian.xbe_variants = xbe_patch, fonts_apply, xbe_variants
        russian.sdb_apply, russian.write_file = sdb_apply, write_file

        rc = russian.main(['russian.py', 'apply', resx])
        kinds = [c[0] for c in calls]
        check(rc == 1, 'a bad line: apply returns 1', f'rc {rc}')
        check('fonts_apply' not in kinds and not any(c[0] == 'xbe_patch' and not c[1] for c in calls)
              and 'xbe_variants' not in kinds and 'write_file' not in kinds,
              'nothing was written before the refusal', str(calls))

        del calls[:]
        rc = russian.main(['russian.py', 'apply', resx, 'xx'])
        check(rc == 1 and not calls, 'an unknown language: apply returns 1 and does nothing',
              f'rc {rc} {calls}')

        del calls[:]
        write(os.path.join(ru, 'gtext.tsv'), '00000001\tfixed\n')
        rc = russian.main(['russian.py', 'apply', resx])
        kinds = [c[0] for c in calls]
        check(kinds.count('fonts_apply') == 1, 'a good file: the fonts go once', str(calls))
        sd = [c for c in calls if c[0] == 'sdb_apply']
        check(len(sd) == 1 and sd[0][1][0].get('gtext.sdb', (None,))[0] == {1: 'fixed'},
              'sdb_apply gets the translations read before', str(sd))
        check(rc == 0, 'a good file: apply returns 0 (nothing to do here)', f'rc {rc}')

        russian.xbe_variants = lambda xbe: 1
        rc = russian.main(['russian.py', 'apply', resx])
        check(rc == 3, 'a written default.xbe.en/.ru counts: apply returns 3', f'rc {rc}')
finally:
    for n, v in saved.items():
        setattr(russian, n, v)

print('E  a copy of the XBE: earlier Russian, revert')
game = os.path.join(ROOT, 'game')
src = next((p for p in (os.path.join(game, 'default.xbe.en'), os.path.join(game, 'default.xbe'))
            if os.path.isfile(p)), None)


def clear_caches():
    russian._credits_cache.clear()
    russian._earlier_cache.clear()


if src is None:
    print('  SKIP  no game/default.xbe.en or game/default.xbe')
else:
    saved_credit = None
    key0 = next(iter(russian.CREDITS_RU))
    try:
        with tempfile.TemporaryDirectory() as t:
            x = os.path.join(t, 'default.xbe')
            resx = os.path.join(t, 'resx')
            os.mkdir(resx)
            shutil.copyfile(src, x)
            clear_caches()
            if russian.xbe_patch(x, True, dry=True) < 0:
                print('  SKIP  not the image these fixes are for')
            else:
                check(russian.xbe_patch(x, True) >= 0, 'first apply on the copy')
                russian.xbe_variants(x)
                check(os.path.exists(x + '.en') and os.path.exists(x + '.ru'), '.en and .ru written')

                # 0. English strings with the code fixes (apply with English in place)
                strs = russian.xbe_string_sites(x)
                rc = russian.xbe_patch(x, True, text_new=False)
                check(rc == 1, 'text_new=False: strings go back to English, rc 1', f'rc {rc}')
                d = russian.read_file(x)

                def at(va, n):
                    return d[russian.xbe_offset(d, va):][:n]
                check(all(at(va, len(o)) == o for va, o, _ in strs),
                      'text_new=False: every string and credits site is the original')
                check(all(at(va, len(n)) == n for va, _, n in russian.XBE_SITES),
                      'text_new=False: every code site is still the patch')
                rc = russian.xbe_patch(x, True, text_new=False)
                check(rc == 0, 'text_new=False again: rc 0', f'rc {rc}')
                clear_caches()
                check(russian.xbe_patch(x, True) == 1, 'and Russian strings back (text_new=None)')

                # 1. The credits' text changes: the Russian already in the file
                # is still this tool's own (taken from .ru), not another disc.
                saved_credit = russian.CREDITS_RU[key0]
                russian.CREDITS_RU[key0] = saved_credit + ' (тест)'
                clear_caches()
                check(russian.xbe_patch(x, True, dry=True, text_new=False) == 1,
                      'after a CREDITS_RU edit English apply takes the earlier Russian as its own (dry, 1 not -1)')
                check(russian.xbe_patch(x, True, dry=True) == 1,
                      'after a CREDITS_RU edit apply sees its own earlier Russian (dry)')
                check(russian.xbe_patch(x, True) == 1, 'and rewrites it')
                russian.xbe_variants(x)
                russian.CREDITS_RU[key0] = saved_credit
                saved_credit = None
                clear_caches()

                # 2. A site that is neither: revert refuses and keeps .en and .ru.
                d = bytearray(russian.read_file(x))
                o = russian.xbe_offset(d, russian.XBE_TEXT[0][0])
                d[o:o + 4] = b'ZZZZ'
                russian.write_file(x, bytes(d))
                clear_caches()
                rc = russian.main(['russian.py', 'revert', resx])
                check(rc == 1, 'revert on an image it does not know returns 1', f'rc {rc}')
                check(os.path.exists(x + '.en') and os.path.exists(x + '.ru'),
                      'and keeps default.xbe.en and .ru')

                # 3. The Russian file back in place: revert restores and removes them.
                shutil.copyfile(x + '.ru', x)
                clear_caches()
                rc = russian.main(['russian.py', 'revert', resx])
                check(rc == 3, 'revert of the Russian XBE returns 3', f'rc {rc}')
                check(not os.path.exists(x + '.en') and not os.path.exists(x + '.ru'),
                      '.en and .ru are gone')
                clear_caches()
                check(russian.xbe_patch(x, False, dry=True) == 0, 'the XBE is the original again')
    finally:
        if saved_credit is not None:
            russian.CREDITS_RU[key0] = saved_credit
        clear_caches()

print('F  the aligned English set: .en4, the language in place, revert')


def unaligned(ents, slots):
    """An .sdb like the disc's: strings back to back, no alignment, padded to 2048."""
    pool = bytearray()
    table = bytearray(slots * 8)
    for i, h, s in ents:
        struct.pack_into('<II', table, i * 8, h, 12 + len(pool))
        pool += s.encode('utf-16le') + b'\0\0'
    d = struct.pack('<III', 0x5DB, 12 + len(pool), len(ents)) + pool + bytes(table)
    return d + bytes(-len(d) % 2048)


JESSE, RICHARD = 'Jesse, Wasteland Trader', 'Richard, Wasteland Mayor'
JESSE_H = 0x22
names = ('RU', 'MOVIES', 'xbe_patch', 'fonts_apply', 'xbe_variants')
saved = {n: getattr(russian, n) for n in names}
try:
    with tempfile.TemporaryDirectory() as t:
        ru = os.path.join(t, 'ru')
        os.mkdir(ru)
        write(os.path.join(ru, 'global_names.py'),
              'NAMES = {%r: "Джесси, Торговец Пустоши"}\n' % JESSE)
        write(os.path.join(ru, 'gtext.tsv'), '%08x\tДжесси, Торговец Пустоши\n' % JESSE_H)
        resx = os.path.join(t, 'resx')
        lvl = os.path.join(resx, 'c1', 'CRB_1a')
        os.makedirs(lvl)
        with open(os.path.join(t, 'default.xbe'), 'wb') as f:
            f.write(b'XBEH' + bytes(60))
        # 'AB' first: Jesse starts 2 bytes past a multiple of 4, as on the disc
        orig = unaligned([(0, 0x11, 'AB'), (1, JESSE_H, JESSE), (2, 0x33, RICHARD)], russian.table_slots(3))
        gt, lv = os.path.join(resx, 'gtext.sdb'), os.path.join(lvl, 'CRB_1a.sdb')
        for p in (gt, lv):
            with open(p, 'wb') as f:
                f.write(orig)
        russian.RU = ru
        russian.MOVIES = os.path.join(t, 'no-movies.tsv')
        strings_to = []

        def xbe_patch(xbe, to_new, dry=False, text_new=None):
            if not dry:
                strings_to.append(text_new)
            return 0

        russian.xbe_patch, russian.fonts_apply = xbe_patch, lambda r: 0
        russian.xbe_variants = lambda x: 0

        def apply(*lang):
            del strings_to[:]
            return russian.main(['russian.py', 'apply', resx] + list(lang))

        def snap():
            out = {}
            for p in (gt, lv):
                for s in ('', '.en', '.en4', '.ru'):
                    if os.path.exists(p + s):
                        out[p + s] = (russian.read_file(p + s), os.stat(p + s).st_mtime_ns)
            return out

        def body(p):
            return russian.read_file(p)

        check(not russian.sdb_aligned(orig), 'the disc-like test file is not aligned')
        check(russian.sdb_aligned(russian.sdb_write(*russian.sdb_read(orig), 2048)), 'sdb_write output is aligned')
        check(not russian.sdb_aligned(b'junk') and not russian.sdb_aligned(orig[:20]),
              'sdb_aligned: junk and a cut-off file are False, no exception')

        # F1: first apply
        rc = apply()
        check(rc == 3, 'F1 first apply returns 3', f'rc {rc}')
        for p in (gt, lv):
            en, en4 = body(p + '.en'), body(p + '.en4')
            check(en == orig, 'F1 .en is the original bytes')
            check(russian.sdb_aligned(en4), 'F1 .en4 is aligned')
            check(russian.sdb_read(en4) == russian.sdb_read(en), 'F1 .en4 has the same text, slots and hashes as .en')
            check(body(p) == body(p + '.ru') and body(p) != en4, 'F1 the Russian set is in place')
        check(strings_to == [True], 'F1 XBE strings go to Russian', str(strings_to))
        d4 = body(gt + '.en4')
        j = JESSE.encode('utf-16le')
        check(d4.find(j) % 4 == 0 and d4.find(RICHARD.encode('utf-16le')) % 4 == 0,
              'F1 Jesse and Richard start on 4 bytes in .en4')

        # F2: nothing to do
        before = snap()
        rc = apply()
        check(rc == 0, 'F2 second apply returns 0', f'rc {rc}')
        check(snap() == before, 'F2 bytes and mtimes of every file are unchanged')

        # F3: English in place stays English
        for p in (gt, lv):
            shutil.copyfile(p + '.en', p)
        before = snap()
        rc = apply()
        check(rc == 3, 'F3 apply with the disc English in place returns 3', f'rc {rc}')
        check(all(body(p) == body(p + '.en4') for p in (gt, lv)), 'F3 the .en4 set is in place')
        check(all(body(p + '.en') == orig and snap()[p + '.en'] == before[p + '.en'] for p in (gt, lv)),
              'F3 .en is untouched')
        check(strings_to == [False], 'F3 XBE strings stay English', str(strings_to))
        rc = apply()
        check(rc == 0, 'F3 once more returns 0', f'rc {rc}')

        # F4: a translation edit with English in place
        ru_before = body(gt + '.ru')
        write(os.path.join(ru, 'gtext.tsv'), '%08x\tДжесси\n' % JESSE_H)
        rc = apply()
        check(rc == 3, 'F4 a translation edit returns 3', f'rc {rc}')
        check(body(gt + '.ru') != ru_before, 'F4 .ru changed')
        check(body(gt) == body(gt + '.en4'), 'F4 English stays in place')

        # F5: explicit language
        rc = apply('ru')
        check(rc == 3 and all(body(p) == body(p + '.ru') for p in (gt, lv)) and strings_to == [True],
              'F5 apply ... ru puts Russian', f'rc {rc}')
        rc = apply('en')
        check(rc == 3 and all(body(p) == body(p + '.en4') for p in (gt, lv)) and strings_to == [False],
              'F5 apply ... en puts the .en4 set', f'rc {rc}')

        # F6: status counts
        apply('ru')
        ru_names, al, tot = russian.sdb_status(resx)
        check(tot == 2 and al == 2 and ru_names == ['gtext.sdb'], 'F6 Russian in place: aligned == total',
              f'{ru_names} {al}/{tot}')

        # F7: revert
        rc = russian.main(['russian.py', 'revert', resx])
        check(rc == 3, 'F7 revert returns 3', f'rc {rc}')
        check(all(body(p) == orig for p in (gt, lv)), 'F7 the original bytes are back')
        check(not any(os.path.exists(p + s) for p in (gt, lv) for s in ('.en', '.ru', '.en4')),
              'F7 no .en, .ru, .en4 left')
        _, al, tot = russian.sdb_status(resx)
        check(tot == 2 and al < tot, 'F6 after revert: aligned < total', f'{al}/{tot}')

        # F8: a cut-off .en: revert leaves that file's whole set, the rest goes back
        apply()
        with open(lv + '.en', 'r+b') as f:
            f.truncate(20)
        rc = russian.main(['russian.py', 'revert', resx])
        check(rc == 1, 'F8 revert with a cut-off .en returns 1', f'rc {rc}')
        check(all(os.path.exists(lv + s) for s in ('.en', '.ru', '.en4')),
              'F8 the damaged file keeps .en, .ru and .en4')
        check(body(gt) == orig and not any(os.path.exists(gt + s) for s in ('.en', '.ru', '.en4')),
              'F8 the other file is back to the original, its set gone')
finally:
    for n, v in saved.items():
        setattr(russian, n, v)

print('G  the disc\'s .sdb.en made aligned')
gtext_en = os.path.join(game, 'resx', 'gtext.sdb.en')
if not os.path.isfile(gtext_en):
    print('  SKIP  no game/resx/gtext.sdb.en')
else:
    gresx = os.path.join(game, 'resx')
    paths = [p for p in [os.path.join(gresx, n) for n in russian.SDBS] + russian.level_sdbs(gresx)
             if os.path.exists(p + '.en')]
    bad = []
    for p in paths:
        d = russian.read_file(p + '.en')
        ents, slots = russian.sdb_read(d)
        en4 = russian.sdb_write(ents, slots, 2048 if len(d) % 2048 == 0 else 0)
        if not russian.sdb_aligned(en4) or russian.sdb_read(en4) != (ents, slots):
            bad.append(os.path.relpath(p, gresx))
    check(len(paths) > 0 and not bad, f'G {len(paths)} .sdb.en: aligned, same text', str(bad))
    crb = os.path.join(gresx, 'c1', 'CRB_1a', 'CRB_1a.sdb.en')
    if os.path.exists(crb):
        d = russian.read_file(crb)
        d4 = russian.sdb_write(*russian.sdb_read(d), 2048 if len(d) % 2048 == 0 else 0)
        for s in (JESSE, RICHARD):
            e = s.encode('utf-16le')
            pos = [i for i in range(0, len(d4) - len(e), 2) if d4[i:i + len(e)] == e]
            check(pos and all(i % 4 == 0 for i in pos), f'G CRB_1a: {s} starts on 4 bytes in .en4', str(pos))
    else:
        print('  SKIP  no CRB_1a.sdb.en')

print(f'russian: {"OK" if not failures else f"{failures} FAILED"}')
sys.exit(1 if failures else 0)
