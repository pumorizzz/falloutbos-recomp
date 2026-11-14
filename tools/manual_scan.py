"""What the generator takes from src/game/recomp/recomp_manual.c, as text.

    py -3 tools/manual_scan.py [<toolkit>]

regen.sh writes it to src/game/recomp/gen/.manual_scan; src/game/CMakeLists.txt
prints it again at configure time and regenerates when the two differ. The
generator skips the functions the manual file defines, calls its _enter hooks
and keeps the sub_ names it mentions, so a pulled recomp_manual.c with a new
replacement or hook needs new C (or the link fails with LNK2005/LNK2001), while
an edit inside a function body does not. The toolkit's own manual_scan decides
what counts, as it does for the generator. <toolkit> defaults to deps/xboxrecomp.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL = os.path.join(ROOT, 'src', 'game', 'recomp', 'recomp_manual.c')


def main(argv):
    toolkit = argv[1] if len(argv) > 1 else os.path.join(ROOT, 'deps', 'xboxrecomp')
    sys.path.insert(0, os.path.abspath(toolkit))
    from tools.recomp.manual_scan import scan, entry_hooks
    skip, wrap, referenced = scan(MANUAL)
    for name, s in (('skip', skip), ('wrap', wrap), ('enter', entry_hooks(MANUAL)),
                    ('referenced', referenced)):
        print(name + ' ' + ' '.join(f'{va:08X}' for va in sorted(s)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
