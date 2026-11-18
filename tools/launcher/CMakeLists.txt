# FalloutLauncher.exe: the render resolution, picture size and anti-aliasing,
# then bin\fobos.exe as Play.cmd starts it. Built next to the game, in bin\
# (a FBOS_STATIC_CRT build: beside the game's exe in <build>/dist-bin).
add_executable(FalloutLauncher WIN32 launcher.c)
target_link_libraries(FalloutLauncher PRIVATE user32 gdi32)
target_compile_definitions(FalloutLauncher PRIVATE _CRT_SECURE_NO_WARNINGS)
set(_fbos_launcher_bin "${CMAKE_SOURCE_DIR}/bin")
if(FBOS_STATIC_CRT AND MSVC)
    set(_fbos_launcher_bin "${CMAKE_BINARY_DIR}/dist-bin")
endif()
set_target_properties(FalloutLauncher PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${_fbos_launcher_bin}"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${_fbos_launcher_bin}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${_fbos_launcher_bin}")
