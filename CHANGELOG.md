# Changelog

All notable changes to this project are documented here. Format: [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [Unreleased]

### Added (GPU rendering and play, 2026-10-30 to 2026-11-09)
- Direct3D 11 render back end (`RECOMP_GPU_RASTER`, toolkit `gpu-rastr`):
  depth, stencil, the register combiners in one ubershader, presented from a
  swapchain; `compare` mode; device loss falls back to the CPU rasteriser.
  `Play.cmd` draws on the GPU by default.
- 60 fps cap at the flip (`RECOMP_FPS_LIMIT`, `0` turns it off).
- F9/F10 in the window: record the pad into `saves\pad_path.txt`, play it back.
- Vertex programs of large batches on several threads (`RECOMP_VSH_THREADS`),
  bit for bit as on one: by Ruby's bar, uncapped, 66 -> 130 fps.
- README: what the fork fixed, the checks, and screenshots of the Tutorial and
  Carbon.
- 16:9: `tools/widescreen.py` maps Nemesis2000's PAL widescreen patch onto the
  USA image (11 sites, each checked; `revert` restores 4:3); `Setup.cmd`
  applies it and regenerates. The window shows the frame at 16:9 by itself.
- The picture opens at 2560x1440 (`RECOMP_FB_SIZE`, fitted to the screen),
  filtered into the display aspect with bars (`RECOMP_FB_ASPECT`); F11 for
  borderless full screen.
- Internal resolution and MSAA on the GPU path (`RECOMP_GPU_RASTER_SCALE`,
  `RECOMP_GPU_RASTER_MSAA`): targets and depth drawn N times larger with
  multisampling, read back to guest RAM averaged; `Play.cmd` uses 3x3 + 4x.
- `bin\FalloutLauncher.exe` (`tools/launcher`): render resolution, picture
  size, full screen, MSAA and the frame-rate limit (30, 60 or 120), then the game; remembered in `bin\launcher.ini`.

### Fixed (GPU rendering and play)
- Hitches of 60-80 ms on the GPU path when new textures came into view (the
  first streets of Carbon): textures decode ~18x faster and DXT goes to the
  GPU as BC; the same frames now stay at 16-19 ms.
- A hitch every ten seconds when started from `FalloutLauncher.exe`: the
  runtime's periodic report took 20-40 ms to print into the console window. The
  launcher now sends the game's output to `fbos.log` without a console (2-3 ms).
- Particles were not drawn at all (point sprites): steam, laser glow,
  radiation pools, smoke, the shadow atlas.
- Red, oversaturated crates and target robots: 0 x inf is 0 in `MUL`/`MAD`, as
  on NV2A.
- The radioactive pit drawn opaque black: an input with no array reads its
  last `SET_VERTEX_DATA*` value.
- Character shadows: the swizzled shadow target is read as swizzled.
- Flickering explosion decals: polygon offset applied.
- Needles, slabs and black floor stripes near the camera: near-plane clip at
  `SET_CLIP_MIN`, per-pixel `SET_CLIP_MIN/MAX`, depth beyond `zmax` rejected on
  the GPU.
- A stale render target written over memory the title had reused (likely the
  orange "splinters" in grenade explosions).
- Lost pushbuffer commands at the ring's wrap: the port walks the ring as DMA
  does (`RECOMP_PB_WALK=dma`).
- Hang loading the Tutorial: the executor owns the D3D fence and kicks a lost
  kick-off.
- Out of contiguous memory after ten minutes in the Tutorial: freed memory is
  reclaimed by default (`RECOMP_HEAP_RECLAIM=1`).
- Main-menu freeze with `intro.bik` looping: Fallout closes its `.clp` handles
  twice; handle tokens are now handed out in turn, and
  `DUPLICATE_CLOSE_SOURCE` releases the source token and its async-I/O mark.
- A stutter every 10 seconds: the executor's report no longer reads render
  targets back.
- `Setup.cmd` without network keeps the toolkit already there and gives git's
  own reason.

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
