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
bin\fbos.exe %*
