# RKIPC / RK3588：EVM3588 相机应用参考

这里单独保存 Rockchip RKIPC 的 RK3588 单摄实现及本板检查工具。它用于学习 Rockit 如何组织相机业务，与 `Low latency stream/`、EdgeVision 和现有 FFmpeg 程序分开。

本项目仓库：[guozhe010702-boop/RKIPC](https://github.com/guozhe010702-boop/RKIPC)。仓库同步参考源码、检查工具、说明和脱敏验证结果；私有 SDK、动态库、日志和构建产物保留本地。

**当前结果：英码 SDK 确有 Rockit MPI 头文件和 ARM64 库；已在本板编译、链接、装载独立检查程序。完整 RKIPC 尚未构建或启动。** 原始 `video.c` 语法检查首先因缺少 FreeType 开发头文件失败，不能据此断言其余接口全部兼容。没有切换摄像头、停用 ISP/3A 服务、修改系统库或注册开机服务。

参考来自 [LuckfoxTECH/luckfox-pico](https://github.com/LuckfoxTECH/luckfox-pico)，固定提交 `824b817f889c2cbff1d48fcdb18ab494a68f69d1`，上游路径 `project/app/rkipc/rkipc/`。保留 76 个 RK3588 和公共模块源码/配置文件的原始字节、Git blob 哈希与许可证。此目录是有选择的源码参考集，并非完整 Luckfox SDK；其它芯片、云平台、字体、模型和预编译库未复制。

## 从哪里开始读

先看 [video.c](upstream/rkipc/src/rk3588_ipc/video/video.c) 的 `rkipc_get_venc_0()`，固定版本第 92 行；再沿以下调用链阅读。

```text
main.c
  参数 / 系统 / ISP 初始化 → RK_MPI_SYS_Init → rk_video_init
    VI → VPSS → VENC0 / VENC1 / VENC2 / JPEG
                   ↓ 每个已启用的视频编码通道有自己的取流线程
             RK_MPI_VENC_GetStream
                   ↓ MB 映射为 CPU 可访问地址
                   ├─ RTSP：码流数据、长度、原始 PTS
                   ├─ 录像：码流数据、长度、PTS、关键帧标记
                   └─ RTMP：码流数据、长度、PTS、关键帧标记
             RK_MPI_VENC_ReleaseStream

  另一显示支路：VI → 独立 VPSS 组 → VO / HDMI
```

这里的 HDMI 是原始图像经过 VPSS 后送 VO，**不是先把 VENC 码流硬解再显示**。如果要验证“编码→解码→HDMI”，需另接 VDEC 支路，本参考中的 HDMI 出画不能证明那条链路通过。

### `rkipc_get_venc_0()` 的完整职责

1. 准备 `VENC_STREAM_S`，为 `pstPack` 分配描述符；这是码流描述信息，不是分配相机原始图像。
2. `RK_MPI_VENC_GetStream(0, &stFrame, 2500)` 从 VENC0 取已压缩码流，等待参数为 2500 毫秒。图像采集、VPSS 和编码此前已通过绑定建立，这个线程不逐帧调用编码器喂入原始图像。
3. `RK_MPI_MB_Handle2VirAddr(pMbBlk)` 获取 MB 的虚拟地址。这不是“拷贝一帧”，也不使该地址变成应用永久所有。
4. 将数据地址、`u32Len` 和 `u64PTS` 传给 `rkipc_rtsp_write_video_frame(0, ...)`。
5. 按源码的 NAL 类型判断生成关键帧标记，再调用录像和 RTMP 写入函数。
6. 三路调用返回后，执行 `RK_MPI_VENC_ReleaseStream(0, &stFrame)` 归还编码输出；失败会记录日志。
7. 继续循环；停止标志改变后退出并释放描述符。GetStream 失败的分支不调用 ReleaseStream，因为本次没有成功借到输出。

**一对成功 GetStream / ReleaseStream 表示一段借用期。** MB 映射地址只能在合法持有期内使用。后续增加异步网络/磁盘队列时，应在释放前复制压缩数据到自有包，或依照匹配 SDK 的 MB 引用规则延长生命期；不能仅把 `data` 指针入队后立刻释放。每次成功取得的流在异常、提前返回等分支也必须归还，适合用 C++ RAII 管理。

### PTS、封装与发送

| 位置 | 此源码实际做的事 |
| --- | --- |
| `VENC_PACK_S.u64PTS` | 编码输出携带的时间戳；应用不在此用系统当前时间重新生成 |
| `common/rtsp/rtsp.c` | 原值传入 `rtsp_tx_video`，初始化时用相对时间/NTP 时间建立同步关系，随后处理 RTSP 事件 |
| `common/storage/storage.c` | 持有 muxer 互斥锁，仅在对应录像运行标志启用时写入 `rkmuxer_write_video_frame` |
| `common/rtmp/rtmp.c` | 持有 RTMP 互斥锁，仅在启用时写入 muxer；编号使用 `id + 3` 区分录像通道 |

PTS 不是帧序号，也不是可直接解释成日期的时间。这里保留编码时间轴；移植到 FFmpeg、90 kHz RTP 或其它封装时，需要按匹配 SDK/封装库的时间单位做明确换算，并处理重启后的时间基线。仅凭这些包装函数，不能证明私有 muxer/RTSP 库内部是否复制数据或是否可能阻塞。

原版三路分发在同一取流线程中顺序执行，RTSP 还有多个通道共享的互斥锁。因此慢存储、锁等待或网络处理可能延长编码缓冲持有时间。成熟应用的模块组织值得参考，但这不等同于已经完成有界、低延迟的异步分发。

### 移植时要细化的边界

- 原函数没有清零整个 `VENC_STREAM_S`，也未检查描述符分配结果；移植时应按当前 SDK 契约初始化并检查所有结果。
- 它只分配、访问一个 `VENC_PACK_S`。SDK 结构包含 `u32PackCount`；不能把单包假设推广为任意编码模式。要先核对当前 SDK 的 pack 数量查询和容量契约，再处理所有有效 pack。
- 本地 SDK 的 pack 还含 `u32Offset`，原函数未显式使用。迁移时要核对长度、偏移和 MB 大小的语义，校验有效范围，不能把旧版本“起始指针+长度”的假设套到任意库。
- `DataType` 是联合体；新的关键帧判断应按当前编码格式选择成员。跨格式同时比较成员的原写法不宜直接照搬；普通 I 帧也不一定等价于可独立恢复的 IDR。
- `rk_video_init()` 多处按位汇总错误后继续初始化。新的实现应在失败点停止并逆序清理已经创建的模块。
- 停机时先通知、唤醒并等待取流线程，再销毁它还可能访问的网络/录像模块；共享运行标志应采用明确的线程同步。原主程序的存储退出与视频线程退出顺序需要一起复核。

## 文件和子目录

| 路径 | 功能 |
| --- | --- |
| `upstream/rkipc/src/rk3588_ipc/main.c` | 配置、ISP/SYS、视频/音频、控制服务、存储的初始化和退出入口 |
| `upstream/rkipc/src/rk3588_ipc/video/video.c` | VI、VPSS、VENC、VO、模块绑定、取流线程、JPEG、参数修改 |
| `upstream/rkipc/src/rk3588_ipc/video/video.h` | 视频控制接口及 Rockit/RGA 头文件依赖 |
| `upstream/rkipc/src/rk3588_ipc/rkipc.ini` | 上游原始配置；默认 4K30、多路视频、音频和 HDMI，尚非本板配置 |
| `upstream/rkipc/src/rk3588_ipc/CMakeLists.txt` | RK3588 目标的源码、头文件路径、链接库、安装资源列表 |
| `upstream/rkipc/common/isp/rk3588/` | RKAIQ 初始化及曝光、白平衡等 ISP 参数控制 |
| `upstream/rkipc/common/audio/rk3588/` | 音频采集/编码和输出 |
| `upstream/rkipc/common/rtsp/`、`rtmp/`、`storage/` | RTSP、RTMP、录像封装与存储管理 |
| `upstream/rkipc/common/osd/`、`roi/`、`region_clip/` | OSD、编码 ROI、裁剪参数与回调 |
| `upstream/rkipc/common/param/` | INI 配置解析、持久化及参数访问 |
| `upstream/rkipc/common/socket_server/` | 应用控制服务，不是视频 RTSP 服务 |
| `upstream/rkipc/common/system/`、`network/`、`event/` | 设备、网络、事件业务；需要逐项适配 Ubuntu 环境 |
| `upstream/rkipc/common/rockiva/` | 额外智能分析接口；不属于完成硬编所必需的基础 Rockit 接口 |
| `source-lock.json` | 上游提交、精确文件清单、字节数和 Git blob 哈希 |
| `tools/fetch_reference.py` | 下载/校验锁定的源码，不覆盖已改动的文件 |
| `tools/prepare_sdk.py` | 只读扫描厂商 SDK，仅提取私有 Rockit 头文件、ARM64 库和来源清单 |
| `tools/probe_board.py` | 只读检查系统/私有 SDK 头文件、库、相关进程；不打开相机 |
| `CMakeLists.txt`、`examples/rockit_link_probe.c` | 独立基础接口编译/链接检查；不调用 RK_MPI 函数 |
| `tools/build_probe.sh` | 板端编译检查程序、列出动态依赖并运行检查程序 |
| `tools/check_video_syntax.py` | 对未改动的 `video.c` 做编译语法检查；不链接、不运行应用 |
| `validation/ema3588-20261103.json` | 脱敏检查结论及明确未验证项 |
| `.cache/`、板端 `local/`、`build/` | 私有 SDK、原始检查输出和构建产物，均不入源码 |

上游启动脚本也保留用于阅读。**不要在当前 Ubuntu 系统执行 `RkLunch.sh` / `RkLunch-stop.sh`**：原脚本会操作网络、频率、启动目录等系统设置，路径针对另一套固件，并非本板部署入口。

## 英码 SDK 与当前板端检查结果

检查日期：2026-11-03。设备为 EVM3588 B1、aarch64、Linux 5.10.110。基础链接测试时原 EdgeVision 与 `rkaiq_3A_server` 均在运行，检查工具没有停止它们。

收尾只读检查发现开发板在当日 15:47:04 重新启动，15:49 时 3A 服务已运行、EdgeVision 未运行。重启原因未确认，本轮命令没有执行重启、关机或相机应用切换，也没有自动恢复其它应用。初始链接测试结果与重启后的运行状态分别记录在验收 JSON 中。

| 检查 | 结果和适用范围 |
| --- | --- |
| 系统已安装 Rockit 开发环境 | 未找到 `rk_mpi_venc.h` / `rk_comm_venc.h` 和系统 `librockit.so` |
| 系统的 `/usr/include/rockchip/rk_mpi.h` | 属于底层 MPP，不能替代 Rockit 的 VI/VPSS/VENC/SYS API |
| 英码 SDK 压缩包 | 找到 `external/rockit/mpi/sdk/include/` 和 `external/rockit/lib/lib64/librockit.so`；提取并记录 43 个文件 |
| 私有库基础检查 | AArch64 ELF64；板端 g++/gcc 9.4 环境中编译、链接、动态装载成功；7 个关键符号可解析 |
| 已确认的关键符号 | GetStream、ReleaseStream、MB 映射、SYS Bind、VENC CreateChn、VI EnableChn、VPSS StartGrp |
| 完整 `video.c` 语法检查 | 失败：当前首先缺少 `freetype2/ft2build.h`；尚未走完其它头文件/API 检查 |
| 完整应用依赖 | 原 CMake 还链接 rkaiq、rtsp、freetype、wpa_client、rkmuxer、rockiva、iconv 等；系统库缓存中目前仅找到 rkaiq/freetype 运行库，其余未找到，不排除厂商其它私有目录中另有 SDK |
| 真实采集/编码/RTSP/HDMI | 本轮未运行 RKIPC，因此没有这些链路的验收结论 |

有 `libfreetype.so.6` 运行库不代表有 FreeType 开发头文件；同样，基础 Rockit 链接通过不代表相机路由、RKAIQ 版本或所有结构体 ABI 已匹配。glibc 系统通常自带 iconv 功能，原构建中的 `-liconv` 也需要根据实际 SDK 修正，而不是随意拷贝另一套库。

## 可以执行的命令

### Windows PowerShell：本地源码检查和 SDK 准备

先进入本目录：

```powershell
Set-Location -LiteralPath 'C:\Users\dvsense_docker\Desktop\work\RK3588\av_dev\RKIPC'
```

解释：`-LiteralPath` 按完整字面路径切换目录，不把空格或特殊字符当成模式。

```powershell
python .\tools\fetch_reference.py --verify-only
```

解释：检查 76 个上游文件的长度和 Git blob 哈希；`--verify-only` 不下载、不修改源码。首次缺少源码时去掉该参数可按锁定提交下载。

```powershell
python .\tools\prepare_sdk.py --sdk '..\..\Linux\SDK&Image\SDK\evm3588_linux_rkr3.3-v1.0.3_v1.2.1.23_sdk.tar.gz'
```

解释：`--sdk` 指英码 SDK 压缩包；程序识别实际 TAR 格式，仅提取 Rockit 到本目录 `.cache/vendor-rockit/`，不解压整个 11 GB SDK，不修改系统。源码和私有库分别管理。

### 板端 Linux：只读检查与独立链接测试

本轮检查材料位于 `/userdata/rkipc-reference/`。这些命令在 `root@ema:~#` 或 SSH/ADB 打开的板端 Bash 执行，不能直接粘到 Windows PowerShell。

```bash
python3 /userdata/rkipc-reference/tools/probe_board.py
```

解释：读取当前系统的依赖和相关进程，返回 JSON；不把私有 SDK 的存在误算为系统已经安装 Rockit。

```bash
python3 /userdata/rkipc-reference/tools/probe_board.py --sdk-prefix /userdata/rkipc-reference/.cache/vendor-rockit
```

解释：`--sdk-prefix` 额外检查指定私有 SDK，结果中的 `rockit_build_inputs_present` 仅表示基础头文件和库存在，不表示完整 RKIPC 已就绪。

```bash
bash /userdata/rkipc-reference/tools/build_probe.sh
```

解释：使用本目录私有 SDK、最多 4 个构建任务，编译并运行不采集的链接检查程序；输出动态依赖和 JSON。程序不调用 `RK_MPI_SYS_Init`、不创建 VI/VENC，也不启动 RTSP。

```bash
python3 /userdata/rkipc-reference/tools/check_video_syntax.py --output /userdata/rkipc-reference/local/video-syntax.json
```

解释：对原始 `video.c` 运行编译器语法检查，`--output` 保存诊断；当前预期会报告上述缺失的 FreeType 头文件并非零退出。它不是启动命令，也不是完整构建。

## 下一步怎么迁移到 IMX415

1. 补齐与英码 SDK 同版本的开发头文件及 RTSP/muxer 等链接依赖，再做完整语法/链接验证。优先裁掉未使用的 RockIVA、音频、无线网络和 RTMP业务；应修改本地派生工程，不改这里已锁定的上游文件。
2. 建立独立本板配置，第一轮仅单路 1080p、无音频、无 OSD、无自动录像。核对 RKAIQ/IQ 文件及 ISP 所有权，不能同时让 RKIPC 和现有 3A 服务重复初始化同一相机。
3. 实测 VI 的设备/pipe/通道映射、实际格式、缓冲布局与 AFBC/NV12 协议。Rockit 的 VI 通道编号不等于 `/dev/video44` 的 44；不能仅替换字符串完成适配。原 VPSS 组和多个编码分支用了 AFBC，必须与输入和当前驱动能力一起核对。
4. 先验证 VI→VPSS→单路 VENC 的实拍帧数、PTS 与缓冲归还，再加入独立端口的 RTSP；输出新鲜度、队列和慢客户端行为单独验收。
5. 若需 HDMI，先核对 GNOME/X11 对显示设备的占用。原 VO 直接输出和桌面 ffplay 是不同路径，需要选择合适的显示所有权方案。
6. 最后逐项加入手动录像、OSD、参数重配和受控启停；稳定后再考虑开机服务。

`Low latency stream` 的 V4L2 lease 归还、有界队列和 IDR 恢复策略可作为本地实现经验；RKIPC 提供的是更完整的业务模块划分。两者暂不混合运行或直接共享 SDK 头文件名称。

## 来源、许可与交付边界

参考原文：[RK3588 video.c（固定提交）](https://github.com/LuckfoxTECH/luckfox-pico/blob/824b817f889c2cbff1d48fcdb18ab494a68f69d1/project/app/rkipc/rkipc/src/rk3588_ipc/video/video.c)。上游 RKIPC [LICENSE](upstream/rkipc/LICENSE) 为 BSD 风格三条款，相关文件自己的许可声明也保持原样；不能沿用前一个 C++ 工程的 MIT 结论。SDK 头文件和闭源二进制另按各自声明管理，保存在忽略目录，不在本轮发布到 GitHub。

本轮交付的是**可追溯的参考源码、实机基础依赖检查工具、检查结果和迁移说明**。未生成完整 RKIPC 成品，不提供尚未验证的相机启动命令。
