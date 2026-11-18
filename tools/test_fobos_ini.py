#!/usr/bin/env python3
"""Self-check of fobos.exe running on its own: where it finds the data and what
fobos.ini sets (src/game/main.c, fbos_find_data_dir / fbos_load_ini).

Run: py -3 tools/test_fobos_ini.py [path\\to\\fobos.exe]   (default bin\\fobos.exe;
from the port root; pytest is not installed)

Background: the Steam Deck kit (tools/package.ps1) is a folder with fobos.exe,
fobos.ini and game\\; Steam starts a non-Steam game in a directory of its own
choosing, with no launcher and no variables. What can go wrong silently: the
data not found from the exe's directory (or its parent: bin\\fobos.exe of a
checkout), fobos.ini overriding a variable set in the environment (Steam's
launch options, Play.cmd, the launcher), a ';' line read as a setting, log=
taking stderr away from a launcher that redirects it.

Copies the exe into a temporary tree with an empty game\\default.xbe and runs
it with FBOS_INI_CHECK, which prints the directory and the variables and
exits before anything loads. No exe: SKIP.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

failures = 0


def check(ok, what, detail=''):
    global failures
    if not ok:
        failures += 1
    print(f'  {"PASS" if ok else "FAIL"}  {what}' + (f'  ({detail})' if detail and not ok else ''))


def run(exe, cwd, names, env_extra=None, stderr=subprocess.PIPE):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('RECOMP_') and not k.startswith('FBOS_')}
    env['FBOS_INI_CHECK'] = ','.join(names)
    env.update(env_extra or {})
    p = subprocess.run([exe], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=stderr,
                       timeout=60)
    out = {}
    for line in p.stdout.decode('utf-8', 'replace').splitlines():
        k, _, v = line.partition('=')
        out[k] = v
    return p.returncode, out


def same_dir(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def make_data(d):
    os.makedirs(os.path.join(d, 'game'), exist_ok=True)
    open(os.path.join(d, 'game', 'default.xbe'), 'wb').close()


def main(argv):
    exe = argv[1] if len(argv) > 1 else os.path.join(ROOT, 'bin', 'fobos.exe')
    if not os.path.isfile(exe):
        print(f'fobos_ini: SKIP (no {exe}; build first)')
        return 0
    tmp = tempfile.mkdtemp(prefix='fobos_ini_')
    try:
        kit = os.path.join(tmp, 'kit')           # the Deck kit: exe beside game\
        tree = os.path.join(tmp, 'tree')         # a checkout: bin\fobos.exe, game\ above
        other = os.path.join(tmp, 'elsewhere')   # where Steam starts it
        bare = os.path.join(tmp, 'bare')         # an exe with no data anywhere near
        for d in (kit, os.path.join(tree, 'bin'), other, bare):
            os.makedirs(d)
        make_data(kit)
        make_data(tree)
        make_data(other)
        kexe = os.path.join(kit, 'fobos.exe')
        texe = os.path.join(tree, 'bin', 'fobos.exe')
        bexe = os.path.join(bare, 'fobos.exe')
        for d in (kexe, texe, bexe):
            shutil.copyfile(exe, d)
        empty = os.path.join(tmp, 'empty')
        os.makedirs(empty)

        print('A. the data directory')
        rc, o = run(kexe, empty, [])
        check(rc == 0 and same_dir(o.get('cwd', ''), kit), 'no game\\ here: the exe\'s directory',
              o.get('cwd'))
        rc, o = run(texe, empty, [])
        check(rc == 0 and same_dir(o.get('cwd', ''), tree), 'nor beside the exe: its parent',
              o.get('cwd'))
        rc, o = run(kexe, other, [])
        check(same_dir(o.get('cwd', ''), other), 'game\\ in the current directory: it stays',
              o.get('cwd'))
        rc, o = run(bexe, empty, [])
        check(same_dir(o.get('cwd', ''), empty), 'no data anywhere: the directory is left alone',
              o.get('cwd'))

        print('B. fobos.ini beside the exe')
        with open(os.path.join(kit, 'fobos.ini'), 'w', newline='\r\n') as f:
            f.write('; the Steam Deck settings\n'
                    'RECOMP_PB_EXEC=1\n'
                    '  RECOMP_FPS_LIMIT = 45 \n'
                    ';RECOMP_GPU_RASTER=1\n'
                    'RECOMP_FB_SIZE=1280x800\n'
                    'FBOS_ASPECT=16:10\n'
                    'not a setting\n')
        names = ['RECOMP_PB_EXEC', 'RECOMP_FPS_LIMIT', 'RECOMP_GPU_RASTER', 'RECOMP_FB_SIZE',
                 'FBOS_ASPECT']
        rc, o = run(kexe, empty, names)
        check(o.get('RECOMP_PB_EXEC') == '1', 'NAME=VALUE is set', o.get('RECOMP_PB_EXEC'))
        check(o.get('RECOMP_FPS_LIMIT') == '45', 'spaces around name and value dropped',
              o.get('RECOMP_FPS_LIMIT'))
        check(o.get('RECOMP_GPU_RASTER') == '<unset>', "a ';' line is a comment",
              o.get('RECOMP_GPU_RASTER'))
        check(o.get('FBOS_ASPECT') == '16:10', 'the value keeps its colon', o.get('FBOS_ASPECT'))
        rc, o = run(kexe, empty, names, {'RECOMP_FPS_LIMIT': '30', 'RECOMP_FB_SIZE': '1920x1080'})
        check(o.get('RECOMP_FPS_LIMIT') == '30' and o.get('RECOMP_FB_SIZE') == '1920x1080',
              'the environment wins over fobos.ini', f'{o.get("RECOMP_FPS_LIMIT")} {o.get("RECOMP_FB_SIZE")}')
        check(o.get('RECOMP_PB_EXEC') == '1', 'the rest of fobos.ini still applies',
              o.get('RECOMP_PB_EXEC'))

        print('C. fobos.ini in the data directory, none beside the exe')
        with open(os.path.join(tree, 'fobos.ini'), 'w') as f:
            f.write('RECOMP_GPU_RASTER=1\n')
        rc, o = run(texe, empty, ['RECOMP_GPU_RASTER'])
        check(o.get('RECOMP_GPU_RASTER') == '1', 'read from the data directory',
              o.get('RECOMP_GPU_RASTER'))
        rc, o = run(bexe, empty, ['RECOMP_GPU_RASTER'])
        check(o.get('RECOMP_GPU_RASTER') == '<unset>', 'no fobos.ini: nothing set',
              o.get('RECOMP_GPU_RASTER'))

        print('D. log=')
        with open(os.path.join(kit, 'fobos.ini'), 'a') as f:
            f.write('log=fobos.log\n')
        log = os.path.join(kit, 'fobos.log')
        prev = os.path.join(kit, 'fobos.prev.log')
        rc, o = run(kexe, empty, [], stderr=subprocess.DEVNULL)   # NUL: nobody reads it
        text = open(log, encoding='utf-8', errors='replace').read() if os.path.exists(log) else ''
        check('ini-check cwd=' in text, 'stderr into the data directory\'s fobos.log', repr(text[:80]))
        rc, o = run(kexe, empty, [], stderr=subprocess.DEVNULL)
        check(os.path.exists(prev), 'the previous log kept as fobos.prev.log')
        os.remove(log)
        rc, o = run(kexe, empty, [], stderr=subprocess.PIPE)      # a launcher's redirection
        check(not os.path.exists(log), 'stderr caught by someone (a pipe): left alone')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print('fobos_ini: OK' if not failures else f'fobos_ini: {failures} FAILED')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
