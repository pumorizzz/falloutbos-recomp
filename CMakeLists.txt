cmake_minimum_required(VERSION 3.20)
project(fbos_recomp C)

# Fallout: Brotherhood of Steel (Xbox, 2004) - Static Recompilation
# Builds all compatibility layers and the recompiled game executable

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# How many cl.exe processes /MP is allowed to fork. Half the cores, so a
# rebuild does not make the desktop unusable -- the generated chunks are large
# enough that each compiler is a multi-gigabyte process, and saturating both
# cores and RAM is what actually locks the machine up, not CPU alone.
cmake_host_system_information(RESULT _fbos_cores QUERY NUMBER_OF_LOGICAL_CORES)
math(EXPR _fbos_default_jobs "${_fbos_cores} / 2")
if(_fbos_default_jobs LESS 1)
    set(_fbos_default_jobs 1)
endif()
set(FBOS_COMPILE_JOBS "${_fbos_default_jobs}" CACHE STRING
    "Parallel cl.exe processes for the recompiled sources (/MP<n>)")
message(STATUS "Compile jobs: ${FBOS_COMPILE_JOBS} of ${_fbos_cores} cores")

# Common definitions
add_compile_definitions(
    WIN32_LEAN_AND_MEAN
    NOMINMAX
)

# Record every indirect-branch target the game reaches, so the next codegen
# pass can seed function detection with measurements instead of inference.
# Costs one byte store per indirect call; off by default.
# See xboxrecomp docs/technical/indirect-calls.md ("Target Feedback").
option(FBOS_ICALL_FEEDBACK "Record indirect-branch targets for codegen feedback" OFF)
if(FBOS_ICALL_FEEDBACK)
    add_compile_definitions(RECOMP_ICALL_FEEDBACK)
    message(STATUS "ICALL target feedback: ON")
endif()

# ebx/esi/edi are callee-saved on x86 and live in globals here, so a lifted
# function that skips its epilogue corrupts its *caller* and nothing crashes.
# This makes every indirect call check them and name the offender. Costs three
# compares per call; off by default.
option(FBOS_ABI_CHECK "Report functions that clobber callee-saved registers" OFF)
if(FBOS_ABI_CHECK)
    add_compile_definitions(RECOMP_ABI_CHECK)
    message(STATUS "Callee-saved register check: ON")
endif()

# ── xboxrecomp runtime libraries ──────────────────────────
# Point this to your xboxrecomp checkout
# Setup.cmd puts the toolkit in deps/xboxrecomp; a side-by-side checkout works too.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/deps/xboxrecomp/CMakeLists.txt")
    set(_fbos_toolkit "${CMAKE_CURRENT_SOURCE_DIR}/deps/xboxrecomp")
else()
    set(_fbos_toolkit "${CMAKE_CURRENT_SOURCE_DIR}/../xboxrecomp")
endif()
set(XBOXRECOMP_DIR "${_fbos_toolkit}" CACHE PATH "Path to xboxrecomp toolkit")
add_subdirectory(${XBOXRECOMP_DIR} ${CMAKE_BINARY_DIR}/xboxrecomp)

# ── Recompiled game executable ─────────────────────────────
add_subdirectory(src/game)


# ── Launcher (render resolution, picture size, anti-aliasing) ──
add_subdirectory(tools/launcher)
