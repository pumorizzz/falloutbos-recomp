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
game/default.xbe.en or game/default.xbe (missing: SKIP). Nothing here writes
into game\\.
"""
import os
import shutil
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

        def xbe_patch(xbe, to_new, dry=False):
            calls.append(('xbe_patch', dry))
            return 0

        def fonts_apply(r):
            calls.append(('fonts_apply',))
            return 0

        def xbe_variants(xbe):
            calls.append(('xbe_variants',))

        def sdb_apply(r, pre):
            calls.append(('sdb_apply', pre))
            return 0

        def write_file(path, data):
            calls.append(('write_file', path))

        russian.xbe_patch, russian.fonts_apply, russian.xbe_variants = xbe_patch, fonts_apply, xbe_variants
        russian.sdb_apply, russian.write_file = sdb_apply, write_file

        rc = russian.main(['russian.py', 'apply', resx])
        kinds = [c[0] for c in calls]
        check(rc == 1, 'a bad line: apply returns 1', f'rc {rc}')
        check('fonts_apply' not in kinds and ('xbe_patch', False) not in calls
              and 'xbe_variants' not in kinds and 'write_file' not in kinds,
              'nothing was written before the refusal', str(calls))

        del calls[:]
        write(os.path.join(ru, 'gtext.tsv'), '00000001\tfixed\n')
        rc = russian.main(['russian.py', 'apply', resx])
        kinds = [c[0] for c in calls]
        check(kinds.count('fonts_apply') == 1, 'a good file: the fonts go once', str(calls))
        sd = [c for c in calls if c[0] == 'sdb_apply']
        check(len(sd) == 1 and sd[0][1][0].get('gtext.sdb', (None,))[0] == {1: 'fixed'},
              'sdb_apply gets the translations read before', str(sd))
        check(rc == 0, 'a good file: apply returns 0 (nothing to do here)', f'rc {rc}')
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

                # 1. The credits' text changes: the Russian already in the file
                # is still this tool's own (taken from .ru), not another disc.
                saved_credit = russian.CREDITS_RU[key0]
                russian.CREDITS_RU[key0] = saved_credit + ' (тест)'
                clear_caches()
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

print(f'russian: {"OK" if not failures else f"{failures} FAILED"}')
sys.exit(1 if failures else 0)
