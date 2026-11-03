"""Read an EVM3588 SDK tar and extract only private Rockit build dependencies."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'evm3588_linux_v1.0.3/external/rockit/'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', required=True, type=Path, help='Vendor SDK tar or tar.gz')
    parser.add_argument('--output', type=Path, default=ROOT / '.cache' / 'vendor-rockit')
    args = parser.parse_args()
    output = args.output.resolve()
    files = []
    with tarfile.open(args.sdk, 'r:*') as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith(PREFIX):
                continue
            relative = member.name[len(PREFIX):]
            if relative.startswith('mpi/sdk/include/') and relative.endswith('.h'):
                target = 'include/' + relative[len('mpi/sdk/include/'):]
            elif relative == 'lib/lib64/librockit.so':
                target = 'lib/librockit.so'
            elif relative in ('README.md', 'CMakeLists.txt'):
                target = 'vendor-notes/' + relative
            else:
                continue
            path = PurePosixPath(target)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe SDK path')
            data = archive.extractfile(member).read()
            destination = output.joinpath(*path.parts)
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError('SDK destination differs; use another --output: ' + str(destination))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            files.append({'source_member': member.name, 'path': target,
                          'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    required = ('include/rk_mpi_venc.h', 'include/rk_mpi_mb.h',
                'include/rk_mpi_sys.h', 'include/rk_comm_venc.h', 'lib/librockit.so')
    missing = [p for p in required if not (output / p).is_file()]
    if missing:
        raise ValueError('Incomplete vendor Rockit SDK: ' + ', '.join(missing))
    library = (output / 'lib/librockit.so').read_bytes()
    if library[:4] != b'\x7fELF' or library[4] != 2 or library[5] != 1 or int.from_bytes(library[18:20], 'little') != 183:
        raise ValueError('librockit.so is not little-endian ELF64 AArch64')
    manifest = {'sdk_filename': args.sdk.name, 'sdk_bytes': args.sdk.stat().st_size,
                'sdk_prefix': PREFIX, 'private_dependencies_only': True, 'files': files}
    (output / 'sdk-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'files': len(files), 'elf': 'AArch64 ELF64'}))


if __name__ == '__main__':
    main()
