"""Fetch the locked, source-only RK3588 reference subset; preserve upstream bytes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Verify local files without network')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'source-lock.json').read_text(encoding='utf-8'))
    base = 'https://raw.githubusercontent.com/LuckfoxTECH/luckfox-pico/' + lock['commit'] + '/' + lock['base_path'] + '/'
    target = ROOT / 'upstream' / 'rkipc'

    def fetch(row):
        name = PurePosixPath(row['path'])
        if name.is_absolute() or '..' in name.parts:
            raise ValueError('Unsafe source path')
        path = target.joinpath(*name.parts)
        if path.exists():
            data = path.read_bytes()
            if git_blob(data) == row['git_blob_sha'] and len(data) == row['bytes']:
                return
            raise ValueError('Local source changed; refusing overwrite: ' + row['path'])
        if args.verify_only:
            raise ValueError('Missing source: ' + row['path'])
        for attempt in range(3):
            try:
                with urllib.request.urlopen(base + row['path'], timeout=30) as response:
                    data = response.read()
                break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
        if git_blob(data) != row['git_blob_sha'] or len(data) != row['bytes']:
            raise ValueError('Source checksum mismatch: ' + row['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if row['mode'] == '100755':
            path.chmod(0o755)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(fetch, lock['files']))
    print(json.dumps({'verified_files': len(lock['files']), 'commit': lock['commit']}))


if __name__ == '__main__':
    main()
