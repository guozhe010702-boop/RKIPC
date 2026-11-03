cmake_minimum_required(VERSION 3.16)
project(rkipc_ema_reference LANGUAGES C)

# This target checks the vendor Rockit ABI/link inputs only. It is not RKIPC.
set(ROCKIT_SDK_PREFIX "" CACHE PATH "Private vendor Rockit directory with include/ and lib/")
if(NOT ROCKIT_SDK_PREFIX)
    message(FATAL_ERROR "Set ROCKIT_SDK_PREFIX to the prepared vendor Rockit SDK; MPP alone is insufficient")
endif()
foreach(header rk_mpi_venc.h rk_mpi_mb.h rk_mpi_sys.h rk_mpi_vi.h rk_mpi_vpss.h rk_comm_venc.h)
    if(NOT EXISTS "${ROCKIT_SDK_PREFIX}/include/${header}")
        message(FATAL_ERROR "Missing Rockit header: ${header}")
    endif()
endforeach()
if(NOT EXISTS "${ROCKIT_SDK_PREFIX}/lib/librockit.so")
    message(FATAL_ERROR "Missing vendor AArch64 librockit.so")
endif()

add_library(vendor_rockit SHARED IMPORTED)
set_target_properties(vendor_rockit PROPERTIES
    IMPORTED_LOCATION "${ROCKIT_SDK_PREFIX}/lib/librockit.so"
    INTERFACE_INCLUDE_DIRECTORIES "${ROCKIT_SDK_PREFIX}/include")
add_executable(rockit_link_probe examples/rockit_link_probe.c)
target_compile_features(rockit_link_probe PRIVATE c_std_11)
target_compile_options(rockit_link_probe PRIVATE -Wall -Wextra -Werror)
target_link_libraries(rockit_link_probe PRIVATE vendor_rockit)
set_target_properties(rockit_link_probe PROPERTIES
    BUILD_RPATH "${ROCKIT_SDK_PREFIX}/lib"
    INSTALL_RPATH "$ORIGIN/../lib")

message(STATUS "Building a non-capturing link probe only; full upstream RKIPC is not enabled")
