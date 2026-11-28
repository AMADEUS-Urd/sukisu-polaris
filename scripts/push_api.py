#!/usr/bin/env python3
"""不依赖 git，用 GitHub REST API 把当前仓库目录逐个文件推上去。

- 只用 python3 标准库（urllib/json/base64），无需 curl / git
- 每个文件单独一个请求，网络抖动可断点重跑（已存在的会自动更新）
- 自动创建仓库（已存在则复用）

用法（在仓库根目录，也就是本文件的上一级）：
    GH_TOKEN=ghp_xxx python3 scripts/push_api.py                 # 仓库名默认 sukisu-polaris
    GH_TOKEN=ghp_xxx python3 scripts/push_api.py my-repo --with-boot
    python3 scripts/push_api.py --dry-run                        # 只列将上传的文件，不联网
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
SKIP_DIRS = {".git", "work", "out", "node_modules"}
SKIP_FILES = {"Image", "Image.gz", "boot_sukisu.img", "kernel-artifacts.zip"}
SKIP_SUFFIX = (".zip", ".tar.gz", ".img")


def req(method, url, token, payload=None, tries=3):
    data = json.dumps(payload).encode() if payload is not None else None
    last = None
    for i in range(tries):
        r = urllib.request.Request(url, data=data, method=method)
        r.add_header("Authorization", "Bearer " + token)
        r.add_header("Accept", "application/vnd.github+json")
        r.add_header("X-GitHub-Api-Version", "2022-11-28")
        r.add_header("User-Agent", "push-api-script")
        if data:
            r.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                body = resp.read()
                return resp.status, (json.loads(body) if body else {})
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {"raw": body[:300].decode("utf-8", "replace")}
            if e.code in (401, 403, 404, 422):
                return e.code, parsed
            last = (e.code, parsed)
        except Exception as e:  # 网络类错误，重试
            last = (0, {"error": str(e)})
        time.sleep(2 * (i + 1))
    return last if last else (0, {"error": "unknown"})


def walk(root, with_boot):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if fn in SKIP_FILES:
                continue
            if fn.lower().endswith(SKIP_SUFFIX) and not (with_boot and fn == "boot.img"):
                continue
            if fn == "boot.img" and not with_boot:
                print(f"[skip] {rel} （45MB，默认跳过；要传加 --with-boot）")
                continue
            out.append((p, rel))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default="sukisu-polaris")
    ap.add_argument("--with-boot", action="store_true", help="同时上传 boot.img（45MB）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--desc", default="polaris (MIX 2S) MIUI12 Android10 SukiSU Nova kernel build")
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = walk(root, a.with_boot)
    print(f"[+] 待上传 {len(files)} 个文件，根目录 {root}")
    for _, rel in files:
        print("    " + rel)
    if a.dry_run:
        print("[dry-run] 不联网，结束")
        return

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("缺少环境变量 GH_TOKEN（形如 GH_TOKEN=ghp_xxx python3 scripts/push_api.py）")

    code, me = req("GET", API + "/user", token)
    if code != 200 or "login" not in me:
        sys.exit(f"token 无效或网络不通（HTTP {code}: {me}）")
    login = me["login"]
    print(f"[+] 账号: {login}")

    code, _ = req("POST", API + "/user/repos", token, {
        "name": a.repo, "private": False, "description": a.desc, "auto_init": False,
    })
    if code == 201:
        print(f"[+] 已创建仓库 {login}/{a.repo}")
    elif code == 422:
        print(f"[+] 仓库已存在，复用 {login}/{a.repo}")
    else:
        print(f"[!] 创建仓库返回 {code}，继续尝试上传")

    ok = fail = 0
    for path, rel in files:
        rel_q = urllib.parse.quote(rel, safe="/")
        url = f"{API}/repos/{login}/{a.repo}/contents/{rel_q}"
        sha = None
        code, cur = req("GET", url, token, tries=2)
        if code == 200 and isinstance(cur, dict):
            sha = cur.get("sha")
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        payload = {"message": f"add {rel}", "content": content}
        if sha:
            payload["sha"] = sha
            payload["message"] = f"update {rel}"
        code, res = req("PUT", url, token, payload)
        if code in (200, 201):
            print(f"[ok] {rel}")
            ok += 1
        else:
            print(f"[FAIL] {rel} -> HTTP {code} {str(res)[:200]}")
            fail += 1

    print(f"\n完成: {ok} 成功, {fail} 失败")
    print(f"仓库地址: https://github.com/{login}/{a.repo}")
    if fail:
        print("失败的文件可直接重跑本脚本，会只补差异（已存在的会 update）")
        sys.exit(1)


if __name__ == "__main__":
    main()