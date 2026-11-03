# Roadmap

## Next
- Speed in the level: ~17 fps with #231; the executor is 25% busy and the
  raster workers about 60%. Left on the table:
  - Workers stall at every scan end (drain before DMA_GET). A drain only at
    fences and reports would need the 0x400B10 latch modelled in the default
    segment scan: removing KickOff's flush wait (tried, reverted) let the
    title run ahead into `sub_000AB760`, which waits on that latch for ever.
  - The pixel loop itself (combiners per pixel, no SIMD).
  - On a busy host the NV2A polling thread's `Sleep(0)` loses its core, and
    every kickoff waits a time slice; fps then halves.
- GPU rasterisation (`RECOMP_GPU_RASTER`, toolkit branch `gpu-rastr`): the
  executor's triangles drawn on D3D11 and presented from the GPU into the
  framebuffer window (no readback per flip). Carbon, RTX 3080 Ti, with
  `RECOMP_FPS_LIMIT=200`, same session A/B: Carbon spawn 77 -> 146 fps, by
  Ruby and the bar 43 -> 98 fps (60 with the default cap), after the vertex
  program interpreter stopped re-decoding every instruction per vertex and an
  index list's repeated vertices stopped being transformed again. Pixels
  outside SET_CLIP_MIN/MAX are no longer drawn on either path, which takes
  off the needles and slabs that near-plane-clipped triangles fanned across
  the screen by the bar. Compare differs only in the "camera wedge" frames.
  Not done: an fps reading right after leaving Ruby's dialog with this build
  (the scripted walk to Ruby is timed in flips and misses her once the game
  runs faster; townspeople also block it). The stippled floor tiles were
  batches whose first vertex was NaN: they left no dirty rectangle, so what
  they drew never reached guest RAM. Next:
  the vertex programs on the GPU.
- A camera fault seen once in Carbon (docs/images/known-camera-wedge.png): a
  giant wedge fills the screen while the minimap is unchanged. Not reproduced
  since; catch it with a frame trace.
- Upstream the image-aliasing claim into xboxrecomp's contiguous allocator.
- Get the three toolkit changes merged and pin the toolkit version; then delete
  the `sub_000A4E60` override.

## Required by REPO_RULES, not done yet
- `--headless --record out.mp4` (section 10): xboxrecomp has no ffmpeg pipe
  yet. Today: `RECOMP_FB_DUMP` frames, which work headless.

## Later
- Start New Game: load the first level.
- Save games on the HDD partition (`UDATA\49500008`).

## Out of scope
- Distributing game data or generated C, in any form.
- The PS2 version.
