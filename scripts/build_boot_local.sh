#!/usr/bin/env bash
# 本地合成：原厂 boot.img + 新 Image.gz → boot_sukisu.img
set -euo pipefail
cd "$(dirname "$0")/.."

IMG="${1:-Image.gz}"
[ -f "$IMG" ] || { echo "找不到内核镜像: $IMG"; echo "用法: $0 [Image.gz]"; exit 1; }
[ -f boot.img ] || { echo "当前目录没有 boot.img（原厂 boot），请先放进来"; exit 1; }

python3 scripts/repack_boot.py --boot boot.img --image "$IMG" --out boot_sukisu.img
echo
echo "下一步: fastboot flash boot boot_sukisu.img && fastboot reboot"
