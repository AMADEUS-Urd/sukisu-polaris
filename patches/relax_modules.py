#!/usr/bin/env python3
"""放宽内核模块版本校验：允许加载异版本 vendor .ko（WiFi/相机等）。
在 kernel 源码根目录执行。只改 kernel/module.c 的三处硬校验。
"""
import re, sys

p = 'kernel/module.c'
s = open(p).read()
orig = s
log = []

# 1) vermagic 不匹配 -> 只告警，继续
pat1 = re.compile(r'\} else if \(!same_magic\(modmagic, vermagic, info->index\.vers\)\) \{.*?return -ENOEXEC;\s*\}', re.S)
s2 = pat1.sub('} else if (!same_magic(modmagic, vermagic, info->index.vers)) {\n\t\tpr_warn("%s: vermagic %s != %s, forcing\\n", mod->name, modmagic, vermagic);\n\t}', s, count=1)
log.append(('vermagic', s2 != s)); s = s2

# 2) CRC 不匹配 -> 只告警，继续
pat2 = re.compile(r'bad_version:\s*pr_err\("%s: disagrees about version of symbol %s\\n", mod->name, symname\);\s*return -EINVAL;', re.S)
s2 = pat2.sub('bad_version:\n\tpr_warn("%s: symbol %s version mismatch, forced\\n", mod->name, symname);\n\treturn 0;', s, count=1)
log.append(('crc', s2 != s)); s = s2

# 3) 无版本信息也不拒绝
pat3 = re.compile(r'if \(!versions\) \{\s*pr_err\("no symbol version for %s\\n", symname\);\s*return -EINVAL;\s*\}', re.S)
s2 = pat3.sub('if (!versions) { pr_warn("no version for %s, forced\\n", symname); return 0; }', s, count=1)
log.append(('no_versions', s2 != s)); s = s2

if s == orig:
    print('[WARN] 没有匹配到任何补丁点（源码文本可能不同）')
else:
    open(p, 'w').write(s)
for name, ok in log:
    print(f'  {name}: {"patched" if ok else "no-match"}')
print('[+] relax_modules done')
