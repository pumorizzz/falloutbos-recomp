# FalloutLauncher.exe: the render resolution, picture size and anti-aliasing,
# then bin\fbos.exe as Play.cmd starts it. Built next to the game, in bin\.
add_executable(FalloutLauncher WIN32 launcher.c)
target_link_libraries(FalloutLauncher PRIVATE user32 gdi32)
target_compile_definitions(FalloutLauncher PRIVATE _CRT_SECURE_NO_WARNINGS)
set_target_properties(FalloutLauncher PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_SOURCE_DIR}/bin"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_SOURCE_DIR}/bin")
