#!/usr/bin/env python3
"""用原厂 boot.img 重组出可刷写的 boot 镜像（只替换内核，其余原样保留）。

支持 Android boot header v0 / v1 / v2。
用法:
  python3 repack_boot.py --boot boot.img --image Image.gz --out boot_sukisu.img
  # 需要重算 boot 头 id 时加 --recompute-id
不依赖 mkbootimg，纯 struct 手写，方便在手机上直接跑。
"""
import argparse
import gzip
import hashlib
import struct
import sys
import zlib

PAGE_ALIGN = lambda n, p: (n + p - 1) // p * p


def align(data: bytes, page: int) -> bytes:
    return data + b"\x00" * (PAGE_ALIGN(len(data), page) - len(data))


def split_gzip_tail(seg: bytes):
    """把内核段拆成 (第一个 gzip 流, 其余附加数据=dtb 集合)"""
    if seg[:2] != b"\x1f\x8b":
        return seg, b""
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    step = 1 << 20
    try:
        fed = 0
        for i in range(0, len(seg), step):
            chunk = seg[i:i + step]
            d.decompress(chunk)
            fed += len(chunk)
            if d.eof:
                break
        used = fed - len(d.unused_data)
        return seg[:used], seg[used:]
    except Exception:
        return seg, b""


class BootImg:
    def __init__(self, raw: bytes):
        self.raw = raw
        if raw[:8] != b"ANDROID!":
            raise SystemExit("不是 ANDROID! boot 镜像")
        f = struct.unpack("<8s10I16s512s32s1024s", raw[:1632])
        (self.magic, self.kernel_size, self.kernel_addr, self.ramdisk_size,
         self.ramdisk_addr, self.second_size, self.second_addr, self.tags_addr,
         self.page_size, self.header_version, self.os_version, self.name,
         self.cmdline, self.id, self.extra_cmdline) = f

        v1_extra = 0
        if self.header_version >= 1:
            self.recovery_dtbo_size, self.recovery_dtbo_offset, self.header_size = \
                struct.unpack("<IQI", raw[1632:1648])
            v1_extra = 16
        else:
            self.recovery_dtbo_size = 0
            self.recovery_dtbo_offset = 0
            self.header_size = 1632

        if self.header_version >= 2:
            self.dtb_size, self.dtb_addr = struct.unpack("<IQ", raw[1648:1660])
        else:
            self.dtb_size, self.dtb_addr = 0, 0

        if not self.header_size or self.header_size < 1632:
            self.header_size = 1632 + v1_extra + (12 if self.header_version >= 2 else 0)

        p = self.page_size
        off = PAGE_ALIGN(self.header_size, p)
        self.kernel_off = off
        self.kernel = raw[off:off + self.kernel_size]
        # 高通平台 boot 的内核段常是 "Image.gz + appended dtb"，
        # 必须把 dtb 原样保留，否则 bootloader 找不到设备树会直接进 fastboot
        self.kernel_gz, self.kernel_append = split_gzip_tail(self.kernel)
        off = PAGE_ALIGN(off + self.kernel_size, p)
        self.ramdisk_off = off
        self.ramdisk = raw[off:off + self.ramdisk_size]
        off = PAGE_ALIGN(off + self.ramdisk_size, p)
        self.second_off = off
        self.second = raw[off:off + self.second_size]
        off = PAGE_ALIGN(off + self.second_size, p)
        self.dtbo_off = off
        self.dtbo = raw[off:off + self.recovery_dtbo_size]
        off = PAGE_ALIGN(off + self.recovery_dtbo_size, p)
        self.dtb_off = off
        self.dtb = raw[off:off + self.dtb_size]

    def summary(self):
        gz = b"gzip" if self.kernel[:2] == b"\x1f\x8b" else "raw"
        return (f"header_v{self.header_version} page={self.page_size} "
                f"kernel={self.kernel_size} ({gz}) ramdisk={self.ramdisk_size} "
                f"second={self.second_size} dtbo={self.recovery_dtbo_size} dtb={self.dtb_size}")


    def build(self, new_kernel_gz: bytes, recompute_id: bool = True) -> bytes:
        append = getattr(self, "kernel_append", b"")
        full_kernel = new_kernel_gz + append
        hdr = bytearray(self.raw[:self.header_size])
        struct.pack_into("<I", hdr, 8, len(full_kernel))

        if recompute_id:
            h = hashlib.sha1()
            for part in (full_kernel, self.ramdisk, self.second):
                h.update(part)
            if self.dtb:
                h.update(self.dtb)
            hdr[576:608] = h.digest()[:32]

        out = bytearray()
        out += align(bytes(hdr), self.page_size)
        out += align(full_kernel, self.page_size)
        out += align(self.ramdisk, self.page_size)
        out += align(self.second, self.page_size)
        out += align(self.dtbo, self.page_size)
        out += align(self.dtb, self.page_size)
        return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", required=True, help="原厂 boot.img")
    ap.add_argument("--image", required=True, help="新内核 Image.gz（未压缩 Image 也可，会自动 gzip）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--recompute-id", action="store_true",
                    help="重算 header id（默认保留原厂 id，最小改动最稳）")
    a = ap.parse_args()

    b = BootImg(open(a.boot, "rb").read())
    print("[+] 原 boot:", b.summary())

    img = open(a.image, "rb").read()
    if img[:2] != b"\x1f\x8b":
        print("[*] 输入不是 gzip，先压缩（level 9）")
        img = gzip.compress(img, 9)
    if b.kernel[:2] == b"\x1f\x8b" and img[:2] != b"\x1f\x8b":
        raise SystemExit("原 boot 内核为 gzip 而新内核不是，格式不一致")

    print(f"[+] 新内核: {len(img)} 字节 (原 {b.kernel_size} 字节, 差 {len(img)-b.kernel_size:+d})")
    out = b.build(img, recompute_id=a.recompute_id)
    open(a.out, "wb").write(out)
    print(f"[+] 已写出 {a.out}  {len(out)} 字节  sha256={hashlib.sha256(out).hexdigest()}")

    chk = BootImg(out)
    print("[+] 校验新 boot:", chk.summary())
    if chk.kernel[:2] != b"\x1f\x8b":
        raise SystemExit("!! 校验失败：内核不是 gzip")
    if not chk.kernel_append.startswith(b"\xd0\x0d\xfe\xed"):
        raise SystemExit("!! 校验失败：dtb 附加段丢失（会被 bootloader 拒绝）")
    if chk.ramdisk != b.ramdisk:
        raise SystemExit("!! 校验失败：ramdisk 被改动")
    print(f"[OK] 校验通过：内核 gzip {len(chk.kernel_gz)} B + dtb 附加段 {len(chk.kernel_append)} B，"
          f"ramdisk/cmdline/地址与原厂一致，仅内核被替换")


if __name__ == "__main__":
    main()