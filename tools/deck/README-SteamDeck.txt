Fallout: Brotherhood of Steel -- recompiled, on the Steam Deck
==============================================================

This folder is a personal copy for your own device: the game files in game\
come from your own disc, unpacked on your PC. Nothing here is sent anywhere,
and the folder is not meant to be shared.

What is inside
  fobos.exe            the game (Windows, runs under Proton)
  fobos.ini            its settings (see below)
  game\                your game files
  saves\               saves (an empty folder, or your saves and settings:
                       saves\UDATA\49500008); the game adds the rest itself
  fobos.pdb, fobos.map only with package.ps1 -Pdb: symbols for FBOS_PROFILE

Install
  1. Copy the whole folder to the Deck, e.g. to ~/Games/fbos-deck/
     (a USB stick, a network share or Warpinator; in Desktop Mode).
  2. Steam (Desktop Mode) -> Games -> Add a Non-Steam Game to My Library ->
     Browse -> ~/Games/fbos-deck/fobos.exe -> Add Selected Programs.
  3. In the library: the game -> Properties -> Compatibility -> tick
     "Force the use of a specific Steam Play compatibility tool" ->
     Proton Experimental (or 9.x).
  4. Back to Gaming Mode and start it there. Nothing else is needed: no
     launcher, no variables. The pad works at once (Steam Input gives the game
     an Xbox pad); if the buttons are off, pick the "Gamepad" template in the
     controller settings.

Frame rate
  The game always runs its logic at 60 frames a second: the Tutorial charge
  and the rest of the timing need that. A limit (Quick Access -> Performance:
  Framerate Limit 45, 40, 30 ..., or the panel at 40-90 Hz) only drops frames
  from the screen -- the game does not slow down. If the Deck cannot keep up
  even then, the game itself goes below 60 and runs slower; fobos.log says so.
  The picture may lag one frame more when the GPU is busy (the swap chain
  holds two frames); RECOMP_GPU_RASTER_FRAME_LATENCY=1 %command% holds one,
  at the price of frames skipped when a frame takes long.

The log
  fobos.log in this folder, written anew at every start (the previous one is
  kept as fobos.prev.log). Useful lines: "[GPU] ... fps (... flips, shown ...)",
  "[GPU] executor: ... ms work a flip" (what the CPU thread that runs the
  game's graphics costs; under 16 ms is what 60 needs), "[GPURAST] ... frame
  skip: ...", "FAULT". If the game does not start at all:
  Launch Options  PROTON_LOG=1 %command%  writes ~/steam-<appid>.log.

Changing a setting
  Either edit fobos.ini, or override a line in Steam: Properties -> Launch
  Options, NAME=VALUE before %command%, e.g.
    RECOMP_GPU_RASTER_SCALE=2 %command%      sharper (1280x960 drawn per frame;
                                             costs GPU time -- try it, keep it
                                             if the game stays at 60)
    RECOMP_GPU_RASTER_MSAA=4 %command%       smoother edges, more GPU time
    FBOS_PROFILE=60,20 %command%             a CPU profile into fobos.log
                                             (needs fobos.pdb and fobos.map:
                                             package.ps1 -Pdb); it prints
                                             name @ module+0xRVA -- on the PC,
                                             with the .map beside the exe:
                                             py -3 tools\prof_resolve.py
                                             fobos.log --exe fobos.exe
