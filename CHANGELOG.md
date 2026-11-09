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
- Russian: `tools/russian.py apply` translates `gtext.sdb` (dialogue, quests,
  menus, hints), the names in `global.sdb`/`deftexte.sdb` and in each level's own
  `.sdb`, and the inventory labels and the loading screen's `Loading...` inside
  the XBE, and adds Cyrillic drawn from PT Sans to the three fonts in `sfx.clp`;
  `revert` restores English. The text goes in as cp1251 code points, since
  several of the game's paths keep a byte (`я` on 0x9F: 0xFF in Nadia's name
  broke her model). Ten 4-byte code fixes in `default.xbe`: the wide `sprintf`
  kept only the low byte of a format's own characters ("Выбрать" read
  "K1@0BL"), and the 8-bit-to-wide copies widened with a sign ("Pick up %s" was
  cut to "...").
- Launcher: Language, English (original) or Russian; before the start it
  copies the chosen set of `game\resx\*.sdb` (`.en`/`.ru`) into place and sets
  the XBE's strings in `game\default.xbe` from `default.xbe.en`/`.ru`, leaving
  its code alone.
- README rewritten around the current build, with new 16:9 screenshots; the old
  4:3 screenshots and the GIF are gone.
- `bin\FalloutLauncher.exe` (`tools/launcher`): render resolution, picture
  size, full screen, MSAA and the frame-rate limit (30, 60 or 120), then the game; remembered in `bin\launcher.ini`.

### Fixed (GPU rendering and play)
- Hitches of 60-80 ms on the GPU path when new textures came into view (the
  first streets of Carbon): textures decode ~18x faster and DXT goes to the
  GPU as BC; the same frames now stay at 16-19 ms.
- A hitch every ten seconds when started from `FalloutLauncher.exe`: the
  runtime's periodic report took 20-40 ms to print into the console window. The
  launcher now sends the game's output to `fobos.log` without a console (2-3 ms).
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
- `Setup.cmd` closed without a word when the Python package `capstone` was
  missing, instead of offering to install it (and on any traceback from
  `widescreen.py`): Windows PowerShell turned the redirected stderr into an
  error under `Stop`.
- The launcher copied the whole `default.xbe.en`/`.ru` over `default.xbe`,
  putting back the XBE of the last `russian.py apply` and undoing a later
  `widescreen.py apply` or `revert`; it now sets only the strings.
- `[EXCEPTION]` lines for harmless first-chance exceptions (a driver naming a
  thread) read as a crash, used up the reports a real one needs, and failed
  `boot_check`'s "no faults".
- `russian.py`: backups and rewritten files go through a temporary file and a
  rename; a cut-off `sfx.clp.en` or `.sdb.en` is refused instead of written
  back; `apply` refuses (no Pillow, another disc, fonts drawn already without
  a backup) before writing anything, with exit status 1, and exits 0 when
  nothing changes instead of redrawing the fonts every time. An `apply` cut
  short (a CRC that fails in `sfx.clp`) is finished by the next `apply` from
  `sfx.clp.en`; a damaged `.sdb` or its backup is named, and `revert` puts
  every other file back and lists the ones it had to leave.
- `FBOS_PROFILE` sampled at most 64 threads and dropped the rest unsaid; now
  256, and any past them are reported.
- `russian.py status` on an XBE of another revision stopped with a traceback;
  it now says it is not this image and exits 1. `revert` no longer claims the
  `.sdb` beside a damaged backup is Russian (the launcher may have put the
  English set there). Given a `resx` with no `default.xbe` beside it, `status`,
  `apply` and `revert` say so and exit 1 instead of a `FileNotFoundError`.
- Three Russian lines (a ghoul's compliment, two Shop-Tec adverts) had a
  double space where the English has its ellipsis (byte 0x85); now "...".
  "Français"/"Español" (a language menu the USA game does not show) are
  translated, since the Russian fonts draw ç and ñ as "з" and "с".
- The launcher set the Russian XBE strings into a `default.xbe` without
  `russian.py`'s code fixes (the disc unpacked again, the `.en`/`.ru` set left),
  and the inventory's labels came out cut to "..."; it now refuses and asks for
  `py -3 tools\russian.py apply`. English still starts. It also keeps a
  `RECOMP_GPU_RASTER` set beforehand, as `Play.cmd` does.
- That check looked at `default.xbe`, but the code that runs is `bin\fobos.exe`,
  built from the generated C: it refused a game built before the disc was
  unpacked again, and passed one not rebuilt after `apply`. `regen.sh` now
  builds into the C a mark of the code fixes the XBE had
  (`russian.py code-mark`, `gen/recomp_fbos_mark.c`), and the launcher reads it
  from `bin\fobos.exe`; an exe from before the mark still gets the XBE check.
- A fresh clone with no `src/game/recomp/gen/` built nothing and failed at the
  link: CMake now runs `regen.sh` when `game/default.xbe` is there, and stops
  with a plain message when it is not.

### Added (boot to Carbon, 2026-10-17 to 2026-10-18)
- Project from the xboxrecomp new-game template and the Half-Life 2 port's
  layout: `regen.sh`, CMake, `main.c`, netlab recipe `falloutbos-recomp`.
- Boots to the main menu with no arguments: Interplay logo, intro FMV, menu
  over `Main_Menu.bik`. 0 faults, 0 unresolved indirect calls in 150 s.
- GPU fence mirror for the D3D device at `0x000B5E58`.
- `RECOMP_AC97_READY` on by default, so DirectSound initialises.
- Deferred file I/O APCs turned on (needs xboxrecomp `fix/io-apc-delivery`).
- Native override of Bink's MMX probe `sub_000A4E60` (until xboxrecomp #186).

### Fixed (boot to Carbon)
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
- `regen.sh` resolves `TRACE_FUNCS` to an absolute path; the toolkit runs from
  its own directory and could not find a relative one.

### Changed (boot to Carbon)
- The profiler samples about 35 times faster (raw addresses, named at the
  end; thread list refreshed once a second).
