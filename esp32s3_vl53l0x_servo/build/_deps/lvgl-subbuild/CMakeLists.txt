# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.30.2)

# Reject any attempt to use a toolchain file. We must not use one because
# we could be downloading it here. If the CMAKE_TOOLCHAIN_FILE environment
# variable is set, the cache variable will have been initialized from it.
unset(CMAKE_TOOLCHAIN_FILE CACHE)
unset(ENV{CMAKE_TOOLCHAIN_FILE})

# We name the project and the target for the ExternalProject_Add() call
# to something that will highlight to the user what we are working on if
# something goes wrong and an error message is produced.

project(lvgl-populate NONE)



include(ExternalProject)
ExternalProject_Add(lvgl-populate
                     "UPDATE_DISCONNECTED" "False" "DOWNLOAD_EXTRACT_TIMESTAMP" "FALSE" "EXTERNALPROJECT_INTERNAL_ARGUMENT_SEPARATOR" "URL" "https://codeload.github.com/lvgl/lvgl/tar.gz/refs/tags/v8.4.0" "URL_HASH" "SHA256=3b454d602e1667b9bd2c434f5e8156753d92cf3e71fc40a0cb0d99fca9a605be" "SOURCE_SUBDIR" "idf-component-only"
                    SOURCE_DIR          "/workspace/esp32s3_vl53l0x_servo/build/_deps/lvgl"
                    BINARY_DIR          "/workspace/esp32s3_vl53l0x_servo/build/_deps/lvgl-build"
                    CONFIGURE_COMMAND   ""
                    BUILD_COMMAND       ""
                    INSTALL_COMMAND     ""
                    TEST_COMMAND        ""
                    USES_TERMINAL_DOWNLOAD  YES
                    USES_TERMINAL_UPDATE    YES
                    USES_TERMINAL_PATCH     YES
)


