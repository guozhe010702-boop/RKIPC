"""Compile-check the unchanged reference video.c; never link or run RKIPC."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-prefix', type=Path, default=ROOT / '.cache' / 'vendor-rockit')
    parser.add_argument('--cc', default='cc', help='Native or cross C compiler')
    parser.add_argument('--output', type=Path, help='Optional JSON result')
    args = parser.parse_args()
    ref = ROOT / 'upstream' / 'rkipc'
    paths = [args.sdk_prefix / 'include', ref / 'src/rk3588_ipc/video', ref / 'common']
    paths += sorted(p.parent for p in (ref / 'common').rglob('*.h'))
    command = [args.cc, '-fsyntax-only', '-std=gnu11', '-DISP_HW_V30', '-Werror=implicit-function-declaration']
    for path in dict.fromkeys(paths):
        command.extend(['-I', str(path)])
    command.append(str(ref / 'src/rk3588_ipc/video/video.c'))
    result = subprocess.run(command, capture_output=True, text=True)
    report = {'exit_code': result.returncode, 'syntax_passed': result.returncode == 0,
              'full_rkipc_linked': False, 'camera_opened': False,
              'stdout': result.stdout, 'stderr': result.stderr}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if result.returncode == 0 else 1)


if __name__ == '__main__':
    main()
