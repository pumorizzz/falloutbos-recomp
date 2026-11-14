# Roadmap

## Done
- Power-on to gameplay with no arguments; Tutorial played through, Carbon
  played to the warehouse and back, graphics checked against a PS2
  playthrough frame by frame. Saves are written to `saves\UDATA\49500008`.
- GPU rasterisation (`RECOMP_GPU_RASTER`, toolkit `gpu-rastr`): Direct3D 11,
  presented from a swapchain, the default in `Play.cmd`. RTX 3080 Ti with the
  60 fps cap lifted: Carbon spawn about 146 fps, Ruby's bar about 130 (66
  before the vertex programs ran on several threads); the CPU rasteriser about
  17. What it fixed on the way is in the README, "What this fork fixed".
- The picture: 16:9 (Nemesis2000's patch mapped onto the USA image), 16:10 or
  4:3 picked at start from one exe, a 2560x1440 picture with borderless full
  screen, and an internal resolution with MSAA and SSAA (3x3 + 4x by default).
- Russian translation: dialogue, quests, menus and hints, item and character
  names, the XBE's own strings, Cyrillic in the game's three fonts, movie
  subtitles and the credits; English or Russian picked in the launcher.
- `bin\FalloutLauncher.exe`: aspect, resolution, SSAA, MSAA, picture size,
  full screen, frame-rate limit, language.
- Extras: the four movies on the disc the game never offers (Russian set).
- Loading a save works (a save converted from the PS2 version loaded, Vault
  Lab 4, 2026-11-14).

## Next
- GPU time per pixel: with the internal resolution (3x3 + 4x MSAA by default)
  the register-combiner ubershader runs on about ten times the pixels, and in
  the menu 4x3 + 4x MSAA is down to about 85 fps uncapped. Cheaper pixels --
  shader variants per combiner setup instead of one ubershader with loops and
  an indexed register file, or a smaller scale for the scene the game already
  draws twice as wide -- would make 4x3 hold 60 everywhere.
- Play past Carbon: later chapters have only been reached from a save, not played. Record the pass;
  compare with the PS2 playthrough where one covers the same place.
- Read the Russian dialogue windows line by line in play.
- Merge the toolkit's `gpu-rastr` with upstream xboxrecomp v0.16.0 (98 commits
  ahead; conflicts in `nv2a_pb_exec.c`, `tests/nv2a_vsh`, `tools/recomp/lifter.py`,
  so a regen and a full re-check), then offer the fixes upstream and pin the
  toolkit version; then delete the `sub_000A4E60` override.
- Upstream the image-aliasing claim into xboxrecomp's contiguous allocator.

## Watch for
- A stippled floor, and dotted floor tiles with black holes in Carbon: seen in
  early runs only, not in live play with the current build; cause unproven.
  If either comes back, dump the frame there and try the CPU path
  (`RECOMP_GPU_RASTER=0`) first.
- The main-menu freeze with `intro.bik` looping: two holes in the handle table
  are fixed (handles handed out in turn, `DUPLICATE_CLOSE_SOURCE`), but the
  freeze never reproduced, so the link is not proven. If it comes back, keep
  the process running and dissect it.

## Only if needed
- Vertex programs on the GPU (an HLSL interpreter of the NV2A program): only
  if a later level is slow; profile first, to see whether the title's thread,
  the executor or the GPU is the limit.
- On the CPU rasteriser, the executor waits for the vertex-program helpers by
  spinning; with more threads than cores that could cost a frame (not
  observed). Fallback to a sleep after a while, or fewer helpers there.
- Lines (`BEGIN_END` 2-4) are not drawn; nothing played so far uses them.
- The "camera wedge" (docs/images/known-camera-wedge.png): huge triangles
  after the near-plane clip that the CPU rasteriser computes in float; the
  GPU path is not affected.
- After a GPU device loss one frame shows the previous image.

## Required by REPO_RULES, not done yet
- `--headless --record out.mp4` (section 10): xboxrecomp has no ffmpeg pipe
  yet. Today: `RECOMP_FB_DUMP` frames, which work headless.

## Out of scope
- Distributing game data or generated C, in any form.
- The PS2 version.
