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
  executor's triangles drawn on D3D11, written back to guest RAM at every
  sync. Carbon, RTX 3080 Ti: software path 17.7 fps, GPU path 45-46 fps.
  The writeback is the cost now: per 10 s about 6,170 writebacks (3.6 GB)
  and 1.8 s stalled on readback. Next: a surface cache that skips the writeback of surfaces
  nothing reads back (lazy readback, render-to-texture on the GPU), then the
  vertex programs on the GPU.
- A camera fault seen once in Carbon (docs/images/known-camera-wedge.png): a
  giant wedge fills the screen while the minimap is unchanged. Not reproduced
  since; catch it with a frame trace.
- Upstream the image-aliasing claim into xboxrecomp's contiguous allocator.
- Bink block artifacts. Ruled out: threading (same with RECOMP_GUEST_LOCK=1)
  and the MMX helpers (tests/mmx_integer passes). Next: decode one .bik frame
  with ffmpeg as the reference and diff the decoder's output buffer.
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
