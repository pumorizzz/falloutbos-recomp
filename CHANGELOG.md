# Changelog

All notable changes to this project are documented here. Format: [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [Unreleased]

### Fixed (talk prompt names in English, 2026-11-18)
- Jesse and Richard in Carbon showed only "Talk to" on the English text. The
  prompt hands the name's address to the text routine as a float, which rounds
  an address of 32-64 MB to a multiple of 4 (fixed for Russian in `0bbbac6`);
  `CRB_1a.sdb` from the disc starts both names 2 bytes past a multiple of 4,
  and the port loads the file a little above 32 MB.
- `py -3 tools/russian.py apply` now also writes `<name>.sdb.en4`, the same
  English with every string on 4 bytes; `<name>.sdb.en` stays the disc's file
  for `revert`. The launcher's English copies `.en4` (`.en` when there is none).
- `apply` keeps the language in place (English stays English, as `.en4`; the first
  apply still puts Russian), or takes it as `apply <resx> en|ru`. `status`
  counts the aligned `.sdb`, `revert` removes `.en4`. `package.ps1` follows.
- Run `py -3 tools/russian.py apply` again. On a purely English install `apply`
  also patches the fonts and the code of `default.xbe`, so follow it with
  `./regen.sh --disasm` and a build; the launcher has to be rebuilt too (an
  old one copies `.en` for English).

### Changed (combiner shaders by state, 2026-11-18)
- Each register-combiner state the game uses draws with a pixel shader of its
  own, compiled with the build from `config/gpu_rc_keys.txt` (nine states:
  the boot route, Ruby's bar and the Tutorial; the four largest are 91 % of
  the pixels, per `config/gpu_rc_keys.txt`). Why: on the Steam Deck's RDNA the one general combiner shader costs
  every pixel the registers of its worst path (`draw.rc` 22-24 ms of a 24 ms
  span, ~45x a flat shader). A state not in the file is drawn by the general
  shader, counted in the `[GPURAST]` line and logged as
  `combiner state with no shader of its own`; add it to the file and rebuild.
  `RECOMP_GPU_RASTER_RC_STATS=1` lists every state with its draws and pixels,
  `RECOMP_GPU_RASTER_RC_GENERIC=1` draws everything with the general shader.
  PC (RTX 3080 Ti, Ruby's bar, 6x5 + MSAA 2): the GPU span 6.5 -> 2.6-3.0 ms,
  `draw.rc` 5.0-5.4 -> 0.85-0.94 ms; the Deck's settings (1x, MSAA 2): spawn
  span 1.81 -> 1.18 ms, the bar 1.80 -> 1.92 ms (more pixels in that scene).
  Steam Deck (Proton Experimental, the kit: 1280x800, 1x, MSAA 2, the whole
  Tutorial): every draw on an own shader, none on the general one, no state
  missing; the GPU span 2.0-2.8 ms a frame (p95 at most 3.1 ms). The Tutorial
  holds 60 in light scenes and drops to 30-40 in heavy ones (the robots,
  lasers, radiation) with the GPU still at ~2.5 ms of a 33 ms frame: the limit
  there is the CPU, the pushbuffer executor's thread with the vertex transform.
- On WARP the own shaders draw bit for bit what the general one does. On NVIDIA
  the main state's own shader differs by 1 in an 8-bit channel in tens of
  pixels a frame (`RECOMP_GPU_RASTER_PSCHECK`; compiler flags do not change it,
  it is the driver's compiler); accepted. `RC_GENERIC=1` avoids it.

### Fixed (hot paths, 2026-11-18)
- `getenv` no longer runs on repeating paths: `recomp_unimpl` (called from
  DirectSound's `cli`/`sti` pair on every APU position read), the APU MMIO
  trap (`RECOMP_APU_TRACE`), every draw (`RECOMP_PB_EXEC_VERBOSE`) and every
  flip (`RECOMP_FB_VA`). Under Proton the environment is long and `getenv`
  walks all of it. On PC it was 0.019 % of the samples.

### Added (profiler, 2026-11-18)
- `FBOS_PROFILE` prints every function as `name @ module+0xRVA`, the image's
  time stamp and PDB id, and each thread's start address; waits in ntdll are
  recognised by their exports. `tools\prof_resolve.py <fobos.log> --exe
  <fobos.exe>` names the addresses from `fobos.pdb` on the PC (it checks the
  log's image against the exe and pdb) and sums by function and thread;
  `tools\test_prof_resolve.py` is its self-check. Known gap: `fobos.pdb`
  holds only public symbols for the toolkit's libraries, so a toolkit
  function that is `static` gets the name of the nearest public one before
  it (code of `nv2a_pb_exec.c` shows as `xbox_XcVerifyPKCS1Signature`, the
  vertex workers as `nv2a_pb_set_wake`); names of the game's `sub_` functions,
  of exported toolkit functions and of other modules are right.

### Added (frame skip and the Steam Deck kit, 2026-11-17)
- Frame skip (`RECOMP_FRAME_SKIP`, toolkit): at a frame limit below 60 -- the
  launcher's 50, 45, 40, 30, or an outside one (Steam Deck, NVIDIA's Max Frame
  Rate, RTSS) -- the game still flips every 1/60 s and only that many frames
  are shown, so it no longer slows down and the Tutorial charge counts (it did
  not at a native 45 or 30). Frames not shown are not drawn: their GPU work is
  logged and dropped, or drawn when a later frame needs it. `auto` (set by
  `fobos.exe` on the GPU path) also shows a frame only when the swapchain (now
  a flip-model one) can take it without waiting. The window says
  `FPS: 45.0 (game 60.0)`; `RECOMP_FRAME_SKIP=0` keeps the old way.
- The launcher's frame limit: 60, 50, 45, 40 and 30, the game at 60 in each;
  the hint says 50/45/40 judder a little (1-1-2 at 45).
- `fobos.exe` runs on its own: it finds `game\` from the exe's folder (or the
  one above), and reads `fobos.ini` there (`NAME=VALUE`, the environment wins;
  `log=` for the messages). `tools/test_fobos_ini.py` checks both.
- The Steam Deck kit: `tools\package.ps1` builds `fobos.exe` with the static C
  runtime (`-DFBOS_STATIC_CRT=ON`, `build-dist`) and puts it with `fobos.ini`
  (1280x800 16:10, GPU 1x, MSAA 2x, frame skip auto), `README-SteamDeck.txt`
  and a copy of `game\` -- in Russian with the movie subtitles by default --
  into `dist\fbos-deck` (not in git); `-WithSaves` adds your saves and settings
  (`saves\UDATA\49500008`), not the disk images the game makes itself.
- The present and scaling shaders are compiled with the build too (toolkit):
  at run time only diagnostics compile a shader (Proton's d3dcompiler is
  Wine's).

### Added (GPU rendering and play, 2026-10-30 to 2026-11-14)
- Direct3D 11 render back end (`RECOMP_GPU_RASTER`, toolkit `gpu-rastr`):
  depth, stencil, the register combiners in pixel shaders, presented from a
  swapchain; `compare` mode; device loss falls back to the CPU rasteriser.
  `Play.cmd` draws on the GPU by default.
- 60 fps cap at the flip (`RECOMP_FPS_LIMIT`, `0` turns it off).
- F8/F10 in the window: record the pad into `saves\pad_path.txt`, play it back.
- Pad vibration: the game's rumble reports reach the host pad (toolkit, from
  upstream; `RECOMP_RUMBLE=0` turns it off). Checked against an Xbox 360.
- Vertex programs of large batches on several threads (`RECOMP_VSH_THREADS`),
  bit for bit as on one: by Ruby's bar, uncapped, 66 -> 130 fps.
- README: what the fork fixed and the checks.
- 16:9: `tools/widescreen.py` maps Nemesis2000's PAL widescreen patch onto the
  USA image (11 sites, each checked; `revert` restores 4:3). The game draws
  16:9 by default (`FBOS_ASPECT`, see Aspect at start below); the XBE patch no
  longer changes the generated C, and `Setup.cmd` no longer applies it (the
  disc is left as it is; the patch stays for an Xbox or an emulator). The
  window shows the frame at 16:9 by itself.
- The picture opens at 2560x1440 (`RECOMP_FB_SIZE`, fitted to the screen),
  filtered into the display aspect with bars (`RECOMP_FB_ASPECT`); F11 for
  borderless full screen.
- Internal resolution and MSAA on the GPU path (`RECOMP_GPU_RASTER_SCALE`,
  `RECOMP_GPU_RASTER_MSAA`): targets and depth drawn N times larger with
  multisampling, read back to guest RAM averaged; `Play.cmd` uses 3x3 + 4x.
- SSAA on the GPU path (`RECOMP_GPU_RASTER_SSAA`, toolkit): drawn at scale x n,
  each n x n block averaged down to the chosen scale before it is shown.
  Launcher: render resolution 1x-4x (640x480 to 2560x1920), plus 4x3
  (2560x1440, pixel for pixel at 16:9) only when Aspect is 16:9 (a chosen
  `render=4x3` falls back to 4x at Aspect 4:3), SSAA
  (off/2x/3x/4x) and MSAA as separate choices, kept as `ssaa` in
  `bin\launcher.ini`. SSAA is locked (Off, greyed) until "Unlock" is ticked
  and a warning on how it works and what it costs is answered Yes; kept as
  `ssaa_unlocked`.
- Aspect at start, one exe: the C is generated from a copy of `default.xbe`
  with `tools/widescreen.py`'s 11 sites at 4:3, and `tools/aspect.py` lifts
  them as reads of a table (`gen/recomp_fbos_aspect.c`) that `main.c` fills
  from `FBOS_ASPECT` (`16:9`, the default, or `4:3`), so a patched and an
  unpatched XBE give the same C. Launcher: Aspect (16:9 / 4:3), kept as
  `aspect` in `bin\launcher.ini`; the 4x3 render entry follows it instead of
  the XBE.
- 16:10 (`FBOS_ASPECT=16:10`): a third set in the aspect table, by the rule
  Nemesis2000's 16:9 numbers follow -- the camera aspect 1.6, and the x scale of
  the projection and of the three matrices 5/6 of 4:3's (320 -> 266.67, 496 ->
  413.33); the window shows 16:10. Launcher: Aspect 16:10, with a 6x5 render
  entry (3840x2400, pixel for pixel at 16:10; `render=6x5` falls back to 4x at
  another aspect; no SSAA, as scale x SSAA is at most 8) and 16:10 output sizes
  (1280x800 to 3840x2400).
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
- Russian movie subtitles, as in a film: the narration of the intro, the three
  chapter movies, the trailer and the countdown, and the on-screen English in
  them (the T. S. Eliot quotes, the chapter titles, the GNN card), white at the
  bottom in the game's own font. Cues in `tools/ru/movies.tsv` (speech
  transcribed with Whisper medium.en), put into `gtext.sdb` of the Russian set
  as `SUB_<movie>` keys; the port queues the current cue each movie frame in a
  replaced `sub_0003A250` (`recomp_manual.c`). English has no such keys and no
  subtitles. Songs are not subtitled.
- The trailer in Extras (Russian set): `FO_Trailer.bik` is movie 0 of the
  game's movie table, and nothing in the game ever picks movie 0, so the
  trailer on the disc was unreachable. Extras now lists "Трейлер" after
  "Вступление Fallout" when `gtext.sdb` has the key `BONUS_TRAILER` (added by
  `russian.py apply`); the list is built in a replaced `sub_000447D0` and an
  entry hook of `sub_000449B0` stores movie 0 for it. English keeps the
  original list.
- Fallout 1's intro in Extras (Russian set), with the GNN card's subtitle:
  `fo1_intro.bik` is on the disc but not even in the movie table, which
  cannot grow. "Вступление Fallout 1" (key `BONUS_FO1_INTRO`) follows
  "Трейлер", and the choice hook writes the chosen movie's path into movie
  0's slot, which nothing else uses.
- Two more movies nothing in the game names, in Extras the same way (Russian
  set): "Ядерная Хроника" (`NuclearBlast.bik`, the same file as
  `MainMenu.bik`: a minute of nuclear-test footage to music, after "Вступление
  Fallout 1") and "Клип Skinlab 2" (`New_Bonus_SkinLab.bik`: the Skinlab clip
  titled "Beneath the Surface", quieter, after "Клип Skinlab"). The added
  movies are one table, `bonus_movies` in `recomp_manual.c`.
- `FBOS_TEST_LEVELUP=<secs>`, a test switch: raises player 1's level-gained
  flag (bit 0 of `[player+0x828]`, player 1 at `[0x10D0CC]`) that many seconds
  after the player object appears, so the 4-second "Press BACK to Level Up"
  prompt can be seen without playing to a level (checked in Russian:
  "Нажми BACK: Новый Уровень" fits its plate).
- Russian credits: each heading and role, and the thanks, get a Russian line
  under the English one, like subtitles (in place of blank spacer lines; the
  Russian text in the dashboard title image `$$XTIMAGE`). The level-up prompt
  and the disc error's fallback lines inside the XBE are Russian too.
- Launcher: Language, English (original) or Russian; before the start it
  copies the chosen set of `game\resx\*.sdb` (`.en`/`.ru`) into place and sets
  the XBE's strings in `game\default.xbe` from `default.xbe.en`/`.ru`, leaving
  its code alone.
- README rewritten around the current build, with new 16:9 screenshots; the old
  4:3 screenshots and the GIF are gone.
- `bin\FalloutLauncher.exe` (`tools/launcher`): render resolution, picture
  size, full screen, MSAA and the frame-rate limit (30 or 60), then the game; remembered in `bin\launcher.ini`.
- A GPU profile of the Direct3D 11 path (`RECOMP_GPU_PROF=<secs>`, toolkit):
  timestamps by pass and render target, draws, pixels, clears and resolves per
  frame, off by default.
- `RECOMP_GPU_RASTER_PSCHECK=<ref.hlsl>[,<every>]` (toolkit): every
  `<every>`-th frame each draw of the Direct3D 11 path is drawn again through its pixel
  shader and through a reference shader, and the differing pixels are
  counted; diagnostics only, off by default.

### Changed (GPU rendering and play)
- Pad recording is on F8 (F10 still plays it back): F9 also toggles the
  mouse-and-keyboard capture (`RECOMP_MKB`), so one key did both. Recording
  and playback keep time in frames and need the pushbuffer executor
  (`RECOMP_PB_EXEC`, set by the launcher and `Play.cmd`); without it the
  recorder now says so instead of writing every step at 0.
- The Direct3D 11 path's pixel shader is cheaper (toolkit): the register
  combiners keep their registers in registers rather than in an array the GPU
  keeps in memory, there is one shader per path (screen, fixed-function,
  combiners by what their stages sample), and wrapping a texel coordinate no
  longer divides. By Ruby's bar at 6x5 + MSAA 2 the GPU's frame goes from
  24.6 to 6.9 ms (combiner draws 22.8 -> 5.5 ms); the picture is the same bit
  for bit, checked against the previous shader on WARP and on the GPU. At
  6x5 + MSAA 2 with the 60 fps cap the game now holds 60 fps (RTX 3080 Ti):
  100 % of frames at 16.7 ms at the Carbon spawn and 99.9 % by Ruby's bar;
  before, it ran at about 44-47 fps. The
  shaders are compiled when the toolkit is built, so the window opens at once
  and the game reaches control sooner (16.0 s from start against 20.3).

### Fixed (GPU rendering and play)
- Inventory at 16:9 and 16:10: the right panel's 3D view (the character and
  the bar behind them) stood left of its place at 4:3 (about 17 % of the
  panel's width at 16:9, 11 % at 16:10), and the item models in the list were
  pulled towards the screen's centre. The widescreen projection squeezed their
  x placement along with the models. `tools/aspect.py` now scales that
  placement by 320 / the projection's x (4/3 at 16:9, 1.2 at 16:10, 1 at 4:3) at two port-only sites
  (0x32AC1, 0x32EC0): they stand as at 4:3 and on the PS2 and keep the
  widescreen proportions. `widescreen.py apply` (Nemesis2000's patch for an
  Xbox) is unchanged and keeps the offset.
- A crash on the first Bink movie when the frame rate was uncapped (`RECOMP_FPS_LIMIT=0`), and stray `[ICALL] … is not code` lines at 60 fps, both right after the pad connects: XInput's capability query waited on an event built on its stack, the wait failed at once, and the USB interrupt later wrote the request's completion into whatever frame had replaced it. A KEVENT on a guest stack is now a real event, and a USB control transfer completes in a few milliseconds instead of up to 62 (toolkit).
- `Play.cmd` hitched for about 80 ms every 10 s: the pushbuffer executor
  printed its periodic report into the console line by line (~90 console
  writes; stderr is unbuffered) while the game waited for it. The report, the
  D3D11 back end's 10 s line and the kernel's 2 s summary now go out in one
  write each (toolkit); under PowerShell's `Start-Process` redirection the
  same report stood the game still for 300-400 ms.
- Frame pacing: game frames came in pairs (4 + 28 ms at 60 fps, 5 + 61 ms at
  30). Flips now land only on a 60 Hz vblank grid of real time, at least
  60/limit ticks apart, and a late frame waits for the next tick, as on a
  console with vsync (toolkit `RECOMP_FPS_LIMIT`; 39 fps now shows as a steady
  30). The game's own frame time follows the flip: D3D's kick-off is answered
  on a thread of its own while the executor waits for the tick, and the fence
  event is set only where the GPU's wake-up method would set it (toolkit). The
  launcher's 120 fps choice is gone: the limit tops out at 60.
- Point sprites were mirrored vertically for about 85 % of Fallout's particles,
  the mirroring flipping with the camera: the square's orientation followed the
  sign of a vertex-program constant (`c[58].y`) that is the game's own data.
  Texcoord v now always grows down the screen, and a point whose program holds
  a zero there is drawn instead of dropped.
- Occlusion (visibility) counts at an internal scale were divided into pixels
  per query, each losing up to a pixel; samples are summed and divided once per
  report.
- A batch of more than 32768 points (196608 back-end vertices) lost the rest;
  it now goes over in more than one draw.
- Enter and Esc did nothing in the launcher; Enter now plays, Esc quits.
- `Setup.cmd`, with the toolkit checked out on another branch or a detached
  commit, could move the local `gpu-rastr` past commits of its own (left only
  in git's reflog); it now leaves such a branch as it is.
- `russian.py apply` read the translations only after it had written the fonts
  and the XBE, and a bad line was reported without its file; every TSV and
  `movies.tsv` is now checked first, an error names `file:line`, a line without
  a TAB or a text is refused instead of blanking the string, and the movie
  cues are held to what the port draws (48 a movie, 191 bytes, 4 lines).
  `tools/test_russian.py` checks it.
- `widescreen.py` wrote `default.xbe` in place; it now goes through a temporary
  file and a rename, as `russian.py` does, and a missing XBE is said instead of
  a traceback.
- After a code patch the launcher and `russian.py` advised `./regen.sh`; they
  now say `./regen.sh --disasm`, as the README does.
- The launcher at a display scale of 125 % and more: labels, the hint and long list entries were cut off, the full-screen box ran into Output. The layout now scales with the system DPI.
- The credits lost their lower lines (English too): the game draws a frame's
  8-bit text in one batch of quads, and the pushbuffer executor kept 1024
  immediate vertices, 256 glyphs, and dropped the rest. A list of primitives
  now draws what it has and goes on (toolkit, `nv2a_pb_exec.c`); the credits
  fill the screen as on the Xbox, on the GPU and the CPU path.
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
- Main-menu freeze with `intro.bik` looping, likely (it never reproduced, so the link is not proven): Fallout closes its `.clp` handles
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
  `apply` and `revert` say so and exit 1 instead of a `FileNotFoundError`, as
  does `code-mark` without its argument or without `game/default.xbe`.
- Three Russian lines (a ghoul's compliment, two Shop-Tec adverts) had a
  double space where the English has its ellipsis (byte 0x85); now "...".
  "Français"/"Español" (a language menu the USA game does not show) are
  translated, since the Russian fonts draw ç and ñ as "з" and "с".
- In Russian the talk prompt by Ruby in Carbon was "Поговорить:" with no name.
  The game's formatter (0x729A0) takes the name's pointer as a float, which
  rounds an address of 32-64 MB to a multiple of 4. The Russian name started
  2 bytes off that, and the prompt read the end of the string before it.
  `russian.py` now starts every `.sdb` string on 4 bytes; run `apply` again.
- Russian names of items, characters, enemies and objects follow the
  original's capitals ("Руби, Проститутка Пустоши", "Силовой Шлем"), and the
  "Wasteland" the translation had dropped is back in nine of them. So do the
  menus, perks, skills, prompts ("} Открыть Дверь"), speakers' names and the
  inventory labels in the XBE ("Нет Вещей"); `apply` and `revert` take the
  earlier lowercase labels in `default.xbe` as their own. In the lines,
  speakers' names take capitals too ("Матрона Рейдеров:"), speech cut off with
  a dash in the original ends with one ("Мы —"), and "?!?" and the questions
  the translation had turned into statements follow the original.
- The Russian text checked against a full walkthrough video (OCR of a frame a
  second, matched to the strings by hash): about 160 lines fixed. Lines to
  and from the hero no longer assume a man where the hero may be Nadia
  (Armpit's "Honey" line is hers), lost meanings and a pun are back, "?!?"
  inside lines kept, a few prompts in the original's capitals, and the level
  name "Vault Lab 1, mutated" back in English (level names go into save
  names through an 8-bit path).
- The Russian text checked against a second walkthrough, with Nadia as the
  hero, for the lines the first one did not show: 14 lines fixed. The raider
  Matron, Ruby, the Shop-Tek and the hero's own replies no longer speak to a
  man only, Nadia's perk is "Женщина Будущего" (Future Woman), and two lines
  have their meaning and swearing back.
- The rest of the Russian text checked for the hero's gender (lines with a
  gendered form next to "я/ты/вы" or an address word, checked against both
  walkthroughs): 33 lines to or from the hero no longer say "he" only (Jessie,
  the raider Matron, Giese, the Mutant General and others, and the hero's own
  "I'm outta here" replies), and one agreement error is fixed.
- The Russian text checked against a third walkthrough, with Cain as the
  hero, for the lines the first two did not show and the ghoul lines none
  showed: 8 lines fixed (the Mutant Blob speaks to one hero and not to a man
  only, Armpit's last joke, the Necropolis pun and the hero's swearing at Rhombus back,
  the "Use Stimpak" tutorial title, a grammar slip), and the 15 quest
  "ПОДСКАЗКА:" hints start with a capital as the original's "HINT:" does.
- The rest of the Russian text read against the English with no video (1440
  strings no walkthrough showed: other dialogue branches, barks, shop lines,
  labels, quest texts): 26 lines fixed. "Bowling for Brahmin" is "Боулинг
  для Браминов" (the film reference, brahmin as the pins), the Star Wars
  "not the door you're looking for" and "I'm your Huckleberry" are back,
  Jesse's "sons-of-WHORES" joke about Ruby works again, five lines to or from
  the hero no longer assume a man, "Вставьте %u." no longer puts the device's
  name in the wrong case, and a few prompts take Title Case.
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
  Its message, and the README's Russian section, say where `./regen.sh` runs:
  in Git Bash (Git for Windows, from Setup), opened in the game's folder.
- A fresh clone with no `src/game/recomp/gen/` built nothing and failed at the
  link: CMake now runs `regen.sh` when `game/default.xbe` is there, and stops
  with a plain message when it is not.
- After an edit to the Russian credits, `russian.py apply` took the credits an
  earlier apply had written for another disc's and refused, and `revert` then
  deleted `default.xbe.en`, the only copy of the English credits, while saying
  "back to English". Both now take what `default.xbe.ru` holds as their own,
  and `revert` on an image it does not know keeps `.en`/`.ru` and exits 1.
- The build did not regenerate when `recomp_manual.c` replaced, hooked or named
  other functions, so a pull with a new replacement failed to link (LNK2005).
  `regen.sh` now records what the generator took from it (`tools/manual_scan.py`,
  `gen/.manual_scan`), and CMake regenerates when that changes; an edit inside a
  function's body costs no regen.

### Added (boot to Carbon, 2026-10-17 to 2026-10-18)
- Project from the xboxrecomp new-game template and the Half-Life 2 port's
  layout: `regen.sh`, CMake, `main.c`, netlab recipe `falloutbos-recomp`.
- Boots to the main menu with no arguments: Interplay logo, intro FMV, menu
  over `Main_Menu.bik`. 0 faults, 0 unresolved indirect calls in 150 s.
- GPU fence mirror for the D3D device at `0x000B5E58`.
- `RECOMP_AC97_READY` on by default, so DirectSound initialises.
- Deferred file I/O APCs turned on (needs xboxrecomp `fix/io-apc-delivery`).
- Native override of Bink's MMX probe `sub_000A4E60` (until xboxrecomp #186).
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

### Changed (boot to Carbon)
- The profiler samples about 35 times faster (raw addresses, named at the
  end; thread list refreshed once a second).

### Fixed (boot to Carbon)
- Bink video block artifacts (scattered white and coloured blocks in the menu
  background and the intro). The lifter turned `movsx ebp, bp` into a
  zero-extension; Bink's inverse DCT (`0x000CD7BC`) then read every negative
  row-6 coefficient as a large positive one. Fixed in xboxrecomp's lifter
  (`gpu-rastr`); the build re-runs `./regen.sh` by itself to pick it up.
- `regen.sh` resolves `TRACE_FUNCS` to an absolute path; the toolkit runs from
  its own directory and could not find a relative one.
