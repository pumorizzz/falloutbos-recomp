@echo off
rem Start the recompiled game in a window. An XInput pad is player 1; the
rem keyboard also works (WASD, Z/X/C/V = A/B/X/Y, Enter = Start).
cd /d "%~dp0"
set RECOMP_PB_EXEC=1
set RECOMP_FB_WINDOW=1
set RECOMP_KEYBOARD=1
rem Draw on the GPU (Direct3D 11); set RECOMP_GPU_RASTER=0 first for the
rem CPU rasteriser. Without a D3D11 device it falls back to the CPU itself.
if not defined RECOMP_GPU_RASTER set RECOMP_GPU_RASTER=1
rem F9 records your input (on/off), F10 plays the recording back.
if not defined RECOMP_PAD_RECORD set RECOMP_PAD_RECORD=saves\pad_path.txt
rem The picture is 2560x1440 (shrunk to fit the screen in a window); F11
rem switches to borderless full screen. The game still renders 640x480.
if not defined RECOMP_FB_SIZE set RECOMP_FB_SIZE=2560x1440
rem The GPU renders at 3x3 the game's resolution (640x480 -> 1920x1440) with
rem 4x MSAA. 4x3 is sharper still (2560x1440) and costs about half again as
rem much GPU time; 1 and no MSAA is the game's own resolution.
if not defined RECOMP_GPU_RASTER_SCALE set RECOMP_GPU_RASTER_SCALE=3
if not defined RECOMP_GPU_RASTER_MSAA set RECOMP_GPU_RASTER_MSAA=4
bin\fobos.exe %*
