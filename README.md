# polaris (小米 MIX 2S) · MIUI 12 / Android 10 · SukiSU Nova 内核集成

为 **小米 MIX 2S（codename `polaris`，骁龙 845 / MSM8998）** 在 MIUI 12（Android 10，内核 `4.9.186-perf-g83532fd`）上使用 **SukiSU Nova** 管理器，做**手动内核集成（builtin）+ 线上编译**的完整仓库。

参考：[SukiSU Nova 安装文档](https://sukisu.org/zh/guide/installation) / [集成指导](https://sukisu.org/zh/guide/how-to-integrate)

## 为什么走 builtin（不用 LKM）

| 判据 | 你这台的实测值 | 结论 |
|---|---|---|
| 内核版本 | `4.9.186-perf-g83532fd` | 非 GKI，LKM 预编译模块用不上 |
| `CONFIG_KPROBES` | **未开启** | `main` 分支的 kprobe hook 不可用 |
| `CONFIG_KALLSYMS_ALL` | 已开启 | 满足 builtin / KPM 前提 |
| 官方指引 | 4.4+ 传统内核需手动编译 | 走 `builtin-new` + 手动 hook |

官方文档对 4.9 明确给了 `CONFIG_KSU_TAMPER_SYSCALL_TABLE=y`（原文：verified 3.0~7.1，recommended 3.0~4.14），开启后 syscall 表直接替换 `sys_execve / sys_faccessat / sys_newfstatat / sys_reboot`，**可以跳过那一堆手动 hook 补丁**，改动面最小。

## 本仓库做了什么

1. 拉取内核源码（默认 `unknownbaka/utopia_kernel_polaris`，基于小米官方 `dipper-q-oss` 移植到 polaris，4.9.337；也可切 `avantgarde280/kernel_xiaomi_polaris-miui` 的 `LA.UM.8.3.r1-05800-sdm845.0`，正好 4.9.186）
2. 用官方 `kernel/setup.sh` 把 SukiSU 集成进 `drivers/kernelsu`
3. 在你的 defconfig 上注入 `CONFIG_KSU=y` + `CONFIG_KSU_TAMPER_SYSCALL_TABLE=y` 等
4. GCC 4.9 工具链编译 `Image.gz`
5. 提供 `scripts/repack_boot.py`：用**你自己的原厂 boot.img** 只替换内核段重打包，ramdisk / cmdline / addr / id 全部原样保留（已回归验证：喂回原内核时输出与原厂 boot **逐字节一致**）
6. 全部产物带 sha256

## 你的原厂 boot.img 参数（已实测）

```
header_version = 1        page_size = 4096
kernel_addr = 0x8000      ramdisk_addr = 0x1000000     tags_addr = 0x100
kernel  = 44282080 B (gzip)   ramdisk = 810223 B   second/dtbo/dtb = 0
cmdline = console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0xA84000
          androidboot.hardware=qcom androidboot.console=ttyMSM0 video=...
```

`second/dtbo/dtb` 都是 0 → dtb 在独立 dtbo 分区，本方案不动它，所以**不会打乱设备树**。

## 使用步骤

### 0. 前置

- BL 已解锁；电脑有 adb / fastboot（`platform-tools`）
- **备份**：你的原厂 boot 在工作区根目录 `boot.img`（44MB，已实测解析过），另存一份到网盘/电脑，别只留在手机上（见「回滚」）
- 本机已确认：`/proc/config.gz` 权限拒绝，内核配置是从 boot 里内嵌的 IKCONFIG 提取的（见 `configs/polaris_stock_extracted.config`）

### 1. 建仓库并上传

GitHub 新建空仓库 → 把本目录**除 `work/` 以外的全部文件**上传（网页拖拽即可，全部是小文件）。

> 想让 CI 直接出可刷 `boot.img`：把原厂 `boot.img` 放到仓库根目录（45MB，网页上传超限，用 `git push`）。不放也行，产物是 `Image.gz`，在手机上用脚本合成。

### 2. 跑 Actions

`Actions` → `build-sukisu-polaris` → `Run workflow`，参数建议第一轮：

| 参数 | 值 |
|---|---|
| kernel_repo | `unknownbaka/utopia_kernel_polaris` |
| kernel_branch | `main` |
| defconfig | `stock_defconfig`（面向 MIUI 原厂） |
| ksu_setup_arg | `builtin-new` |
| enable_tamper | ✅ |
| enable_susfs | ❌（需额外打 susfs4ksu 内核补丁，见下） |
| enable_kpm | ❌（4.9 上编译会被裁掉，开了无效） |
| repack_boot | ✅（仓库里有 boot.img 才生效） |

时长约 20~40 分钟。失败看日志，`Build log` 也会一起打包。

### 3. 取产物

Artifacts → `kernel-artifacts`：

```
Image.gz          # 新内核
Image             # 未压缩
used.config       # 实际使用的配置
boot_sukisu.img   # 若仓库放了 boot.img，可直接刷
SHA256SUMS.txt
```

### 4. 本地合成 boot（没让 CI 打包时）

把 `Image.gz` 传到手机，在本仓库目录下：

```bash
# 在 /sdcard/dsh-work6（工作区根）下执行：
cp boot.img sukisu-polaris/          # 原厂 boot，把仓库放哪就复制到哪
cd sukisu-polaris
./scripts/build_boot_local.sh Image.gz   # 等价于下面这行
# python3 scripts/repack_boot.py --boot boot.img --image Image.gz --out boot_sukisu.img
```

脚本会打印校验结果，要求 `ramdisk/cmdline/地址与原厂一致，仅内核被替换`。

### 5. 刷入

```bash
fastboot flash boot boot_sukisu.img
fastboot reboot
```

### 6. 验证

- 装 SukiSU Nova 管理器 APK（[Releases](https://git.zako.shirkneko.top:20004/shirkneko/SukiSU/releases)）
- 打开应显示「已安装 / 工作中」，设置 → 关于手机 里内核版本应变成新内核的版本串
- 给一个 App 授权 root，确认能弹授权框

### 7. 回滚（务必先看）

任何异常（黑屏、卡第一屏、震动循环）：

```bash
fastboot flash boot boot.img     # 仓库里那份原厂 boot
fastboot reboot
```

boot 分区没被写坏的前提下，这一步一定救得回来。不要动 `vbmeta` 除非明确知道在干什么。

## 常见失败与对策

| 现象 | 原因 | 处理 |
|---|---|---|
| 编译报 `drivers/kernelsu` 相关错误 | setup.sh 拉下来的分支与内核 API 不匹配 | 把 `enable_tamper=true` 保持，`ksu_setup_arg` 换 `builtin-new`，或指定具体 tag（如 `v1.0.0`） |
| `scripts/config` 报选项未生效 | 该分支没有对应 Kconfig | 正常，只是跳过；确认 `CONFIG_KSU=y` 在 `used.config` 里即可 |
| 编出 Image.gz 但开机卡 logo | 内核与 MIUI 12 厂商驱动不匹配 | 换 `avantgarde280/...` 的 `LA.UM.8.3.r1-05800-sdm845.0`（4.9.186）再编一轮 |
| 能开机但 WLAN/触摸失效 | 基线内核缺 MIUI 定制驱动 | 同上换基线；或改用 `polaris_defconfig` 试 |
| 开机后管理器显示未安装 | hook 没生效 | `adb shell dmesg \| grep -i ksu`；确认 `CONFIG_KSU_TAMPER_SYSCALL_TABLE=y` 已进 `used.config` |

更细的排查清单见 [docs/troubleshooting.md](docs/troubleshooting.md)，逐步照做版见 **[docs/操作手册.md](docs/操作手册.md)**（建仓、传 PAT、填参数、下载、合成、刷机、回滚全都具体到命令）。

## 目录

```
.github/workflows/build.yml     CI 流水线
configs/polaris_stock_extracted.config   从你原厂 boot 提取的完整内核配置（对照用）
scripts/ksu_config.sh           注入 KSU 配置项
scripts/repack_boot.py          原 boot + 新内核 → 可刷 boot.img
scripts/build_boot_local.sh     本地一键合成
docs/操作手册.md                逐步操作手册（照着做）
docs/troubleshooting.md         故障排查
boot.img                        原厂 boot（可选；只有放进来 CI 才会顺带出可刷 boot）
```

## 说明

- 这套内核是在 **MIUI 12 原厂 vendor 之上**的替换，硬件兼容性取决于基线源码与 MIUI 的贴合度，第一轮不一定一次点亮，属正常。
- **SUSFS**：`KSU_TAMPER_SYSCALL_TABLE` 与 `KSU_SUSFS` 在内核 Kconfig 里互斥（`depends on !KSU_SUSFS`）。开 SUSFS 必须先在源码里应用 `susfs4ksu` 的内核补丁（往 `fs/exec.c`、`fs/namei.c`、`fs/stat.c` 等插 inline hook），否则只有开关没有实现。所以第一轮别开，本仓库也未内置该补丁。
- **KPM**：官方 Kconfig 写明「只在 Linux 5.10 及更新内核上构建，更老内核上该选项被忽略」。4.9 上开了等于没开。
- 任何一步都不需要重新锁定 BL，也不需要刷第三方 recovery。