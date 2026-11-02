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
  `RECOMP_FPS_LIMIT=200`: software path 17.5 fps, GPU path 71-77 fps; readback
  stall 0.07 s per 10 s (was 1.8 s). By Ruby and the bar the GPU path runs at
  43-45 fps, CPU-bound. Compare differs only in the "camera wedge" frames,
  where the software rasteriser's float edge functions lose triangles that
  reach millions of pixels past the near plane. Not done: a scripted run
  that opens and closes Ruby's dialog (the "talk" prompt depends on where the
  run stops), the thin dark line that GPU frames sometimes draw from the
  player across the screen. Next: the vertex programs on the GPU.
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
