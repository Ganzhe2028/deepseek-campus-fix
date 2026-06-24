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
import locale


# ============ 配置区 ============

TARGET_HOST = "api.deepseek.com"

MARKER_BEGIN = "# >>> deepseek-auto-fix BEGIN (do not edit this block manually)"
MARKER_END   = "# <<< deepseek-auto-fix END"

# 备用 IP —— hosts 文件只支持一对一映射，多个 IP 指向同一域名时仅第一个（或最后一个，取决于 OS）生效。
# 这里保留列表格式方便维护，实际只写入第一个可用的 IP。
FALLBACK_IPS = [
    "183.131.191.171",   # 中国电信 浙江
    "61.170.66.121",     # 中国电信
]


# ============ 平台适配 ============

def get_hosts_path() -> str:
    """返回当前系统的 hosts 文件路径。"""
    if sys.platform == "win32":
        return r"C:\Windows\System32\drivers\etc\hosts"
    return "/etc/hosts"


def is_admin() -> bool:
    """当前进程是否有权限修改 hosts。"""
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    return os.geteuid() == 0


def elevate() -> None:
    """以管理员权限重新启动当前脚本（Windows: 弹出 UAC 提权窗口）。"""
    script = os.path.abspath(sys.argv[0])
    if sys.platform == "win32":
        import ctypes
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}"', None, 1
        )
        if ret <= 32:
            print("[!] 提权失败，请右键 → 以管理员身份运行此脚本。")
        sys.exit(0)
    else:
        os.execvp("sudo", ["sudo", sys.executable, script])


# ============ hosts 操作 ============

def _detect_hosts_encoding(path: str) -> str:
    """检测 hosts 文件的编码。Windows 上可能是 ANSI/GBK，优先尝试 UTF-8。"""
    if sys.platform != "win32":
        return "utf-8"
    # Windows hosts 可能是 UTF-8（有 BOM）或 ANSI/GBK
    try:
        with open(path, "rb") as f:
            raw = f.read(4)
        if raw[:3] == b"\xef\xbb\xbf":
            return "utf-8-sig"
    except OSError:
        pass
    # 回退到系统默认编码（中文 Windows 上是 GBK/cp936）
    encoding = locale.getpreferredencoding(False)
    return encoding if encoding else "utf-8"


def read_hosts(path: str) -> str:
    """读取 hosts 文件，自动处理编码。"""
    encoding = _detect_hosts_encoding(path)
    try:
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    except UnicodeDecodeError:
        # 最后回退：用 errors="replace" 强行读取
        with open(path, "r", encoding=encoding, errors="replace") as f:
            return f.read()


def write_hosts(path: str, content: str) -> None:
    """写入 hosts 文件。Windows 上使用 ANSI 编码（不带 BOM），兼容系统解析。"""
    if sys.platform == "win32":
        # Windows hosts 文件应为 ANSI/UTF-8 无 BOM；用系统默认编码写入
        encoding = locale.getpreferredencoding(False) or "utf-8"
    else:
        encoding = "utf-8"
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(content)


def build_hosts_entry(ip: str, host: str) -> str:
    """生成要写入 hosts 的条目块（单 IP）。"""
    return "\n".join([
        MARKER_BEGIN,
        f"{ip} {host}",
        MARKER_END,
    ]) + "\n"


def has_fix(content: str) -> bool:
    """检查 hosts 中是否已有本脚本写入的条目。"""
    return MARKER_BEGIN in content


def remove_fix(content: str) -> str:
    """从 hosts 内容中移除本脚本写入的条目块。"""
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
    try:
        content = read_hosts(hosts_path)
        if has_fix(content):
            write_hosts(hosts_path, remove_fix(content))
            print("[+] hosts 条目已清理。")
    except OSError as e:
        print(f"[!] 清理 hosts 失败: {e}")
        print(f"    请手动删除 {hosts_path} 中 {MARKER_BEGIN} 到 {MARKER_END} 之间的行。")


def _pause_on_error(msg: str) -> None:
    """打印错误并暂停，防止双击运行时窗口闪退。"""
    print()
    print(f"[!] 错误: {msg}")
    try:
        input("按 Enter 键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


# ============ 主流程 ============

def main() -> None:
    hosts_path = get_hosts_path()

    print("=" * 50)
    print("  DeepSeek API 强制备用 IP")
    print(f"  目标: {TARGET_HOST}")
    print(f"  备用 IP: {FALLBACK_IPS[0]}")
    print("=" * 50)
    print()

    # 权限检查 & 自动提权
    if not is_admin():
        if sys.platform == "win32":
            print("[*] 需要管理员权限，正在请求提权...")
            print('    如果弹出 UAC 窗口，请点击"是"。')
            elevate()  # 不会返回
        else:
            print("[!] 需要管理员/root 权限。")
            print("    macOS/Linux: sudo python3 deepseek-force-backup.py")
            _pause_on_error("权限不足")
            sys.exit(1)

    # 读取 hosts
    try:
        content = read_hosts(hosts_path)
    except OSError as e:
        _pause_on_error(f"无法读取 hosts 文件: {e}")
        sys.exit(1)

    # 如果已有旧条目则先清理
    if has_fix(content):
        content = remove_fix(content)

    # 写入备用 IP（只写第一个，因为 hosts 不支持同一域名的多 IP 故障转移）
    new_entry = build_hosts_entry(FALLBACK_IPS[0], TARGET_HOST)
    try:
        write_hosts(hosts_path, content.rstrip("\n") + "\n\n" + new_entry)
    except OSError as e:
        _pause_on_error(f"无法写入 hosts 文件: {e}\n"
                        f"    请检查杀毒软件是否拦截了对 {hosts_path} 的修改。")
        sys.exit(1)

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
    try:
        main()
    except Exception as e:
        _pause_on_error(str(e))
        sys.exit(1)
