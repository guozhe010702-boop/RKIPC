#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
sdk=${1:-"$root/.cache/vendor-rockit"}
if [[ $(uname -m) != aarch64 ]]; then
  echo 'This script is for native AArch64 build. Cross compilation requires a matching toolchain/sysroot.' >&2
  exit 2
fi
cmake -S "$root" -B "$root/build/probe" \
  -DCMAKE_BUILD_TYPE=Release -DROCKIT_SDK_PREFIX="$sdk"
cmake --build "$root/build/probe" --parallel 4
echo 'Rockit dependencies (this does not start a camera):'
ldd "$sdk/lib/librockit.so"
echo 'Probe executable dependencies:'
ldd "$root/build/probe/rockit_link_probe"
"$root/build/probe/rockit_link_probe"
