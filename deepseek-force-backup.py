#!/usr/bin/env python3
"""
DeepSeek API 强制备用 IP 脚本
==============================
场景: 运行期间一律走备用 IP，不检测、不自动切回。Ctrl+C 退出时清理 hosts。

用法:
    Windows（管理员终端）:  python deepseek-force-backup.py
    macOS/Linux:           sudo python3 deepseek-force-backup.py

和 deepseek-fix.py 的区别:
    - 不检测 DNS 通不通，不自动切回。
    - 只要在运行，就一直是备用 IP。
    - 退出时一样会清理 hosts。
"""

import sys
import os
import time


# ============ 配置区 ============

TARGET_HOST = "api.deepseek.com"

MARKER_BEGIN = "# >>> deepseek-auto-fix BEGIN (do not edit this block manually)"
MARKER_END   = "# <<< deepseek-auto-fix END"

FALLBACK_IPS = [
    "183.131.191.171",   # 中国电信 浙江
    "61.170.66.121",     # 中国电信
]


# ============ 平台适配 ============

def get_hosts_path() -> str:
    if sys.platform == "win32":
        return r"C:\Windows\System32\drivers\etc\hosts"
    return "/etc/hosts"


def is_admin() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return os.geteuid() == 0


# ============ hosts 操作 ============

def build_hosts_entry(ips: list[str], host: str) -> str:
    lines = [MARKER_BEGIN]
    for ip in ips:
        lines.append(f"{ip} {host}")
    lines.append(MARKER_END)
    return "\n".join(lines) + "\n"


def read_hosts(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_hosts(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def has_fix(content: str) -> bool:
    return MARKER_BEGIN in content


def remove_fix(content: str) -> str:
    lines = content.splitlines(keepends=True)
    result = []
    skipping = False
    for line in lines:
        if line.strip() == MARKER_BEGIN:
            skipping = True
            continue
        if line.strip() == MARKER_END:
            skipping = False
            continue
        if not skipping:
            result.append(line)
    return "".join(result)


def cleanup_hosts(hosts_path: str) -> None:
    """退出时清理 hosts 中的标记块。"""
    content = read_hosts(hosts_path)
    if has_fix(content):
        write_hosts(hosts_path, remove_fix(content))
        print("[+] hosts 条目已清理。")


# ============ 主流程 ============

def main() -> None:
    hosts_path = get_hosts_path()

    print("=" * 50)
    print("  DeepSeek API 强制备用 IP")
    print(f"  目标: {TARGET_HOST}")
    print(f"  备用 IP: {', '.join(FALLBACK_IPS)}")
    print("=" * 50)
    print()

    if not is_admin():
        print("[!] 需要管理员/root 权限。")
        print("    Windows: 右键终端 → 以管理员身份运行")
        print("    macOS/Linux: sudo python3 deepseek-force-backup.py")
        sys.exit(1)

    # 写入备用 IP
    content = read_hosts(hosts_path)
    if has_fix(content):
        content = remove_fix(content)
    new_entry = build_hosts_entry(FALLBACK_IPS, TARGET_HOST)
    write_hosts(hosts_path, content.rstrip("\n") + "\n\n" + new_entry)

    print("[+] 已强制切换到备用 IP！按 Ctrl+C 退出并恢复。")
    print()

    # 挂起，等待 Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("[*] 正在清理 hosts...")
        cleanup_hosts(hosts_path)
        print("[*] 已退出。")


if __name__ == "__main__":
    main()
