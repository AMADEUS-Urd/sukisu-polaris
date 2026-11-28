#!/usr/bin/env bash
# 把 KernelSU / SukiSU 所需的内核配置项注入 defconfig 生成的 .config
# 用法: ksu_config.sh <.config 路径> [tamper] [susfs] [kpm]
#
# 依赖关系（来自 SukiSU builtin-new 分支 kernel/Kconfig）:
#   KSU_TAMPER_SYSCALL_TABLE  depends on !KSU_SUSFS
#   KSU_HACK_ARM64_BRANCH_LINK depends on !KSU_SUSFS && !KSU_TAMPER_SYSCALL_TABLE
#   KSU_SUSFS                depends on KSU = y && ARM64（还需 susfs4ksu 内核补丁）
#   KPM                      在 <5.10 内核上被编译掉，开了也无效
set -uo pipefail

CFG="${1:?用法: ksu_config.sh <.config路径> [tamper] [susfs] [kpm] [ksu_on]}"
TAMPER="${2:-true}"
SUSFS="${3:-false}"
KPM="${4:-false}"
KSU_ON="${5:-true}"

KSRC="$(pwd)"
CFGTOOL="$KSRC/scripts/config"
[ -f "$CFGTOOL" ] || CFGTOOL="scripts/config"

warn=0
setopt() {
  if ! "$CFGTOOL" --file "$CFG" "$@" 2>/dev/null; then
    echo "[WARN] 配置项未生效（该分支可能没有此选项）: $*"
    warn=$((warn + 1))
  fi
}

# ---- 基础项 ----
if [ "$KSU_ON" = "false" ]; then
  setopt --disable KSU
  setopt --enable KALLSYMS
  setopt --enable SECURITY_SELINUX
  setopt --enable MODULES
  setopt --disable LOCALVERSION_AUTO
  echo "[*] KSU 已关闭（纯内核对照构建）"
  echo "[OK] 配置注入完成，警告 $warn 条"
  grep -E '^CONFIG_(KSU|KALLSYMS)' "$CFG" | sort || true
  exit 0
fi
setopt --enable KSU
setopt --enable KALLSYMS
setopt --enable KALLSYMS_ALL
setopt --enable SECURITY_SELINUX
setopt --enable MODULES
# 版本串不要自动追加 git describe 后缀，避免 vermagic 与模块对不上
setopt --disable LOCALVERSION_AUTO

# 用 GNU 工具链时必须关闭 clang LTO/CFI，否则链接器会被塞 --lto-O3
setopt --disable LTO_CLANG
setopt --disable LTO
setopt --disable THINLTO
setopt --disable LTO_CLANG_THIN
setopt --disable CFI_CLANG
# spmi-pmic-arb.c 无条件调用 log_wakeup_reason()，其声明受此开关保护
setopt --enable DEDUCE_WAKEUP_REASONS

# ---- hook 后端：4.9 首选 syscall 表篡改，无补丁、改动面最小 ----
if [ "$SUSFS" = "true" ]; then
  echo "[!] 启用 SUSFS：与 tamper 互斥，改用 SUSFS inline hook（需要 susfs4ksu 内核补丁）"
  setopt --disable KSU_TAMPER_SYSCALL_TABLE
  setopt --enable KSU_SUSFS
  setopt --enable KSU_SUSFS_INLINE_HOOK
  setopt --enable KSU_SUSFS_SUS_PATH
  setopt --enable KSU_SUSFS_SUS_MOUNT
  setopt --enable KSU_SUSFS_SPOOF_UNAME
  setopt --enable KSU_SUSFS_ENABLE_LOG
else
  if [ "$TAMPER" = "true" ]; then
    setopt --enable KSU_TAMPER_SYSCALL_TABLE
  fi
fi

# ---- KPM：<5.10 自动忽略 ----
if [ "$KPM" = "true" ]; then
  setopt --enable KPM
  echo "[!] KPM 在 4.9 内核上会被编译掉（官方 Kconfig 明确说明），仅供对照"
fi

echo "[OK] 配置注入完成，警告 $warn 条"
echo "--- 结果 ---"
grep -E '^CONFIG_(KSU|KPM|KALLSYMS)|^# CONFIG_KSU_(TAMPER|SUSFS)' "$CFG" | sort || true