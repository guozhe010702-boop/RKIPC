"""Read-only board inventory. Does not initialize Rockit or open any camera."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-prefix', type=Path, help='Optional private Rockit SDK directory')
    parser.add_argument('--output', type=Path, help='Optional local JSON result path')
    args = parser.parse_args()
    roots = [Path('/usr/include'), Path('/usr/local/include'), Path('/opt/include')]
    libraries = [Path('/usr/lib'), Path('/usr/local/lib'), Path('/lib'), Path('/oem/usr/lib')]
    if args.sdk_prefix:
        roots.insert(0, args.sdk_prefix / 'include')
        libraries.insert(0, args.sdk_prefix / 'lib')
    headers = {name: sorted({str(p) for root in roots if root.is_dir() for p in root.rglob(name)})
               for name in ('rk_mpi_venc.h', 'rk_mpi_mb.h', 'rk_mpi_sys.h', 'rk_comm_venc.h', 'rk_mpi.h')}
    libs = sorted({str(p) for root in libraries if root.is_dir() for p in root.rglob('librockit.so*')})
    cache = subprocess.run(['ldconfig', '-p'], capture_output=True, text=True, check=True).stdout
    required = ('rockit', 'rkaiq', 'rtsp', 'freetype', 'wpa_client', 'rkmuxer', 'rockiva', 'iconv')
    linked = {name: [line.strip() for line in cache.splitlines()
                     if re.match(r'\s*lib' + re.escape(name) + r'\.so(?:\.|\s)', line)]
              for name in required}
    model = Path('/proc/device-tree/model')
    processes = subprocess.run(['ps', '-eo', 'pid,comm,args'], capture_output=True, text=True, check=True).stdout.splitlines()
    active = [line.strip() for line in processes
              if any(name in line for name in ('rkaiq_3A_server', 'rkipc ', 'rknn_yolov8_demo_stream', 'dmabuf_rtsp_stream'))]
    report = {'machine': platform.machine(), 'kernel': platform.release(),
              'model': model.read_bytes().rstrip(b'\0').decode() if model.is_file() else None,
              'headers': headers, 'rockit_libraries': libs,
              'upstream_dynamic_libraries_in_system_cache': linked,
              'rockit_build_inputs_present': all(headers[n] for n in ('rk_mpi_venc.h', 'rk_mpi_mb.h', 'rk_mpi_sys.h', 'rk_comm_venc.h')) and bool(libs),
              'mpp_header_is_not_rockit': bool(headers['rk_mpi.h']) and not bool(headers['rk_mpi_venc.h']),
              'relevant_processes': active, 'camera_opened': False, 'rockit_initialized': False}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
