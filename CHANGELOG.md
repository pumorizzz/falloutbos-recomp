# Changelog

All notable changes to this project are documented here. Format: [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [Unreleased]

### Added
- Project from the xboxrecomp new-game template and the Half-Life 2 port's
  layout: `regen.sh`, CMake, `main.c`, netlab recipe `falloutbos-recomp`.
- Boots to the main menu with no arguments: Interplay logo, intro FMV, menu
  over `Main_Menu.bik`. 0 faults, 0 unresolved indirect calls in 150 s.
- GPU fence mirror for the D3D device at `0x000B5E58`.
- `RECOMP_AC97_READY` on by default, so DirectSound initialises.
- Deferred file I/O APCs turned on (needs xboxrecomp `fix/io-apc-delivery`).
- Native override of Bink's MMX probe `sub_000A4E60` (until xboxrecomp #186).

### Fixed
- Bink video block artifacts (scattered white and coloured blocks in the menu
  background and the intro). The lifter turned `movsx ebp, bp` into a
  zero-extension; Bink's inverse DCT (`0x000CD7BC`) then read every negative
  row-6 coefficient as a large positive one. Fixed in xboxrecomp's lifter
  (`gpu-rastr`); the build re-runs `./regen.sh` by itself to pick it up.
- Seeds: `0x00095408` (main thread entry), `0x000D845C` (XPP table entry).
- `docs/boot.md`: each wall on the way to the menu and how it was found.
- Controller: `RECOMP_USB` on by default, and the window pages that alias the
  image are claimed so the OHCI model resolves the driver's descriptors. The
  pad enumerates; scripted presses reach the first level, Carbon.
- Seed `0x0002F110` (a virtual method reached in Carbon).
- `FBOS_PROFILE=<start>,<secs>`: a sampling profiler in `main.c`, per thread.
  It found the 5 fps: the pushbuffer executor rasterised every small triangle
  itself while the worker pool slept (fixed in xboxrecomp #228, 15 fps).
- Carbon at ~17 fps on the toolkit branch `work/falloutbos`, which now also
  carries xboxrecomp #230 (no per-kick trace line) and #231 (rasteriser
  pipelined behind the executor).
- README: `RECOMP_RASTER_THREADS` and what it does on a 12-thread CPU.

- Quick start: `Setup.cmd` (prerequisites, asks before installing, disc,
  regen, build) and `Play.cmd` (window, pad or keyboard).
- `tools/boot_check.py`: boot conformance, 8 milestones logo-to-Carbon, against
  a baseline; netlab QA step.
- Dialogue text confirmed drawing in Carbon (the empty box earlier was a
  capture mid fade-in).

### Changed
- The profiler samples about 35 times faster (raw addresses, named at the
  end; thread list refreshed once a second).

### Fixed
- `regen.sh` resolves `TRACE_FUNCS` to an absolute path; the toolkit runs from
  its own directory and could not find a relative one.
