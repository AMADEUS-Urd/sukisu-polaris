# 故障排查

## 一、CI 编译失败

先看 Actions 日志最后 100 行，再对照：

| 报错关键字 | 含义 | 处理 |
|---|---|---|
| `fatal: could not read Username` / `curl: (35)` | SukiSU 源站拉取失败 | 重跑一次；或把 `kernel/setup.sh` 里仓库地址换成可达镜像后自行提交 |
| `No such file or directory: drivers/kernelsu/Kconfig` | setup.sh 没跑完 | 看「集成 SukiSU Nova」这一步的日志 |
| `arch/arm64/configs/xxx_defconfig: No such file` | defconfig 名不对 | 换成 `polaris_defconfig` 或 `stock_defconfig` |
| `implicit declaration of function 'ksu_...'` | 缺手动 hook（tamper 未生效） | 确认 `enable_tamper=true`，并检查 `used.config` 里 `CONFIG_KSU_TAMPER_SYSCALL_TABLE=y` |
| `error: too few arguments to function` + KSU 函数 | 分支 API 与内核版本不匹配 | 用 `builtin-new`；仍不行就指定较老的 SukiSU tag |
| `Segmentation fault` + `scripts/...` | host 工具被新 GCC 编坏 | 在 workflow 里加 `HOSTCFLAGS=-fcommon`（Ubuntu GCC 10+ 常见） |
| `Killed` / `out of memory` | runner 内存不足 | 降低 `-j` 并发（把 `nproc` 改成 `nproc/2` 或 `-j4`） |

## 二、刷完不开机

按现象分：

1. **完全黑屏 / 无振动** → 内核根本没起来：基线源码与设备不匹配。回滚，换基线（`LA.UM.8.3.r1-05800-sdm845.0`）。
2. **卡小米 logo / 第一屏** → 内核起来了但 init 前挂了：多半是 `Image.gz` 打包参数或 ramdisk 被改动。用 `repack_boot.py` 的默认模式（不重算 id、不换 ramdisk），它保证与原厂逐字节一致。
3. **震动两次后重启** → 早期 panic：接 `adb` 不可用，用 `fastboot` 回滚；或在编译时打开 `CONFIG_KSU_DEBUG=y` 重编，看下一次是否落到 pstore / last_kmsg（需要内核开启 `CONFIG_PSTORE`）。
4. **开机进得去但 WLAN/触摸/相机异常** → 基线缺 MIUI 定制驱动：换基线，或改用原厂配置编译（把 `configs/polaris_stock_extracted.config` 复制为内核根目录 `.config` 后 `make olddefconfig`）。

## 三、开机了但管理器显示「未安装」

```bash
adb shell su -c id        # 预期: uid=0
adb shell dmesg | grep -i -E "ksu|kernelsu"
```

- `dmesg` 里没有任何 ksu 输出 → `CONFIG_KSU` 没编进去。看 `used.config` 是否有 `CONFIG_KSU=y`；确认 `drivers/Makefile` 里有 `obj-$(CONFIG_KSU) += kernelsu/`。
- 有 KSU 初始化日志但 `su` 无反应 → 管理器版本过旧或 hook 未启用：确认 `CONFIG_KSU_TAMPER_SYSCALL_TABLE=y`，并把管理器升到对应 Release。
- `su` 被 SELinux 拒绝（`avc: denied`）→ `CONFIG_SECURITY_SELINUX=y` 已有，通常是 hook 没生效，同上。

## 四、现场取证（不重启也能拿日志）

```bash
adb shell dmesg > dmesg.txt
adb shell cat /proc/last_kmsg > last_kmsg.txt   # 需内核支持
adb shell "cat /sys/fs/pstore/console-ramoops*" > pstore.txt
```

## 五、回滚

```bash
fastboot flash boot boot.img
fastboot reboot
```

原厂 boot 在仓库根目录 / 工作区都有一份。**先确认能进 fastboot**（关机后 `音量下 + 电源`）再开始刷。