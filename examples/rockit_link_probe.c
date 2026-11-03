/* Local reference tooling. No RK_MPI function is called by this program. */
#include <stddef.h>
#include <stdio.h>
#include "rk_mpi_venc.h"
#include "rk_mpi_mb.h"
#include "rk_mpi_vi.h"
#include "rk_mpi_vpss.h"
#include "rk_mpi_sys.h"

/* Volatile function pointers retain typed relocations for the actual linker. */
static RK_S32 (*volatile get_stream)(VENC_CHN, VENC_STREAM_S *, RK_S32) = RK_MPI_VENC_GetStream;
static RK_S32 (*volatile release_stream)(VENC_CHN, VENC_STREAM_S *) = RK_MPI_VENC_ReleaseStream;
static RK_VOID *(*volatile map_block)(MB_BLK) = RK_MPI_MB_Handle2VirAddr;
static RK_S32 (*volatile sys_bind)(const MPP_CHN_S *, const MPP_CHN_S *) = RK_MPI_SYS_Bind;
static RK_S32 (*volatile create_venc)(VENC_CHN, const VENC_CHN_ATTR_S *) = RK_MPI_VENC_CreateChn;
static RK_S32 (*volatile enable_vi)(VI_PIPE, VI_CHN) = RK_MPI_VI_EnableChn;
static RK_S32 (*volatile start_vpss)(VPSS_GRP) = RK_MPI_VPSS_StartGrp;

int main(void) {
    const int ready = get_stream && release_stream && map_block && sys_bind &&
                      create_venc && enable_vi && start_vpss;
    printf("{\"symbols_resolved\":%s,\"venc_stream_bytes\":%zu,"
           "\"venc_pack_bytes\":%zu,\"pack_pts_offset\":%zu,"
           "\"pack_data_offset_offset\":%zu,\"camera_opened\":false,"
           "\"rockit_initialized\":false}\n",
           ready ? "true" : "false", sizeof(VENC_STREAM_S), sizeof(VENC_PACK_S),
           offsetof(VENC_PACK_S, u64PTS), offsetof(VENC_PACK_S, u32Offset));
    return ready ? 0 : 1;
}
