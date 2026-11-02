#!/usr/bin/env bash
# Regenerate the recompiled C from game/default.xbe.
#
#   xbe_parser    section layout -> build/fbos_analysis.json
#   disasm        rewrites functions.json from scratch. ~2.5 min for the
#                 600 KB .text. Only re-run when the toolkit's disasm or the
#                 seeds change. config/seed_functions.json holds entry points
#                 only a run can find (thread routines passed by pointer,
#                 Bink's blitters picked at runtime); it is committed because
#                 it cannot be re-derived without running the game.
#   func_id       library-function identification (CRT, XDK).
#   abi_analysis  calling convention / params / return type. Without it every
#                 function lifts as cdecl / 0 params and nothing says so.
#   recomp        emits the C into src/game/recomp/gen (gitignored).
#
# No RTTI step: tools.rtti finds none in this image, so there are no vtable
# seeds to feed disasm.
#
# Usage: ./regen.sh [--disasm]
#        RECOMP=/path/to/xboxrecomp ./regen.sh

set -uo pipefail

FBOS="$(cd "$(dirname "$0")" && pwd)"
# Setup.cmd puts the toolkit in deps/xboxrecomp; a side-by-side checkout works too.
if [[ -z "${RECOMP:-}" ]]; then
    if [[ -d "$FBOS/deps/xboxrecomp" ]]; then RECOMP="$FBOS/deps/xboxrecomp"; else RECOMP="$FBOS/../xboxrecomp"; fi
fi
XBE="$FBOS/game/default.xbe"
PY="${PY:-py -3}"

if [[ ! -f "$XBE" ]]; then
    echo "missing $XBE"
    echo "unpack your own disc image first:"
    echo "  (cd $RECOMP && $PY -m tools.xiso unpack '<your Fallout BoS iso>' -o '$FBOS/game')"
    exit 1
fi

mkdir -p "$FBOS/build"

if [[ "${1:-}" == "--disasm" || ! -f "$FBOS/build/disasm/functions.json" ]]; then
    echo "==> xbe_parser"
    (cd "$RECOMP" && $PY -m tools.xbe_parser "$XBE" \
        --json "$FBOS/build/fbos_analysis.json" --quiet) || exit 1

    echo "==> disasm"
    (cd "$RECOMP" && $PY -m tools.disasm "$XBE" \
        --analysis-json "$FBOS/build/fbos_analysis.json" \
        --seed-functions "$FBOS/config/seed_functions.json" \
        -o "$FBOS/build/disasm" -v > "$FBOS/build/disasm.log" 2>&1) \
        || { tail -20 "$FBOS/build/disasm.log"; exit 1; }
    grep -aE '"total_functions"|"total_instructions"' "$FBOS/build/disasm/summary.json"
fi

echo "==> func_id"
(cd "$RECOMP" && $PY -m tools.func_id "$XBE" \
    --functions "$FBOS/build/disasm/functions.json" \
    --strings   "$FBOS/build/disasm/strings.json" \
    --xrefs     "$FBOS/build/disasm/xrefs.json" \
    -o "$FBOS/build/func_id" | tail -1) || exit 1

echo "==> abi_analysis"
(cd "$RECOMP" && $PY -m tools.abi_analysis "$XBE" \
    --functions  "$FBOS/build/disasm/functions.json" \
    --identified "$FBOS/build/func_id/identified_functions.json" \
    --output-dir "$FBOS/build/abi" | tail -1) || exit 1

# Entry tracing for bring-up:
#   TRACE_FUNCS=config/trace_functions.json ./regen.sh
#   The toolkit runs from its own directory, so make the path absolute first.
if [[ -n "${TRACE_FUNCS:-}" ]]; then
    TRACE_FUNCS="$(cd "$(dirname "$TRACE_FUNCS")" && pwd)/$(basename "$TRACE_FUNCS")"
fi
echo "==> recomp"
# Capture the status: a failed recomp that leaves the previous gen/ in place
# and reports success is the worst failure this script can have.
(cd "$RECOMP" && $PY -m tools.recomp "$XBE" --all --split 500 \
    --disasm-dir  "$FBOS/build/disasm" \
    --func-id-dir "$FBOS/build/func_id" \
    --abi-dir     "$FBOS/build/abi" \
    --exclude-manual "$FBOS/src/game/recomp/recomp_manual.c" \
    ${TRACE_FUNCS:+--trace-functions "$TRACE_FUNCS"} \
    --gen-dir     "$FBOS/src/game/recomp/gen" \
    -o "$FBOS/build/recomp"
) > "$FBOS/build/recomp.log" 2>&1
status=$?
grep -aE "unresolved|functions \(|Complete" "$FBOS/build/recomp.log" || true
if [ $status -ne 0 ]; then
    echo "!! recomp failed (status $status) -- gen/ is now STALE" >&2
    tail -25 "$FBOS/build/recomp.log" >&2
    exit $status
fi
# recomp leaves unchanged files alone, so their times say nothing; this one
# marks when gen/ last matched the toolkit (src/game/CMakeLists.txt).
touch "$FBOS/src/game/recomp/gen/.regen_stamp"

echo "==> done. Now: cmake -S . -B build-msvc -A x64 -DXBOXRECOMP_DIR=$RECOMP"
echo "             cmake --build build-msvc --config Release"
