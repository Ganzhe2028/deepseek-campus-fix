#!/usr/bin/env python3
"""
DeepSeek API 网络修复守护脚本
===============================
场景: 校园网出口到 DeepSeek CDN 联通节点不通，DNS 轮询导致请求间歇性失败。

原理:
  每 N 分钟解析 api.deepseek.com → 测 TCP 443 通不通
    - 至少一个 IP 通 → DNS 正常，移除 hosts 覆盖（让 CDN 就近调度）
    - 全部不通     → 将备用 IP 写入 hosts，绕过问题 CDN 节点

  校园网修好后: DNS IP 恢复可达 → 自动切回 DNS，零手动操作。
  离开校园后:    DNS 本身就能通 → 脚本不写入 hosts，零影响。

跨平台: Windows / macOS / Linux，纯标准库，无第三方依赖。
权限:   修改 hosts 需要管理员/root。权限不足时会提示并跳过。
"""

import socket
import sys
import time
import os
import platform
import subprocess
import signal
import textwrap

# ============ 配置区 ============

TARGET_HOST = "api.deepseek.com"
TARGET_PORT = 443
CHECK_INTERVAL = 300        # 检测间隔（秒），5 分钟
CONNECT_TIMEOUT = 5          # TCP 连接超时（秒）
MARKER_BEGIN = "# >>> deepseek-auto-fix BEGIN (do not edit this block manually)"
MARKER_END   = "# <<< deepseek-auto-fix END"

# 备用 IP —— 检测到 DNS 不通时使用的逃生通道。
# 这些 IP 需要你和当前网络实测可达。用下面的命令验证：
#   curl -o NUL -w "%%{http_code}" --connect-timeout 5 https://<IP>/v1/models -H "Host: api.deepseek.com"
# 如果 IP 失效，替换为新的可达 IP 即可。
FALLBACK_IPS = [
    "183.131.191.171",   # 中国电信 浙江
    "61.170.66.121",     # 中国电信
]


# ============ 平台适配 ============

def get_hosts_path() -> str:
    """返回当前系统的 hosts 文件路径。"""
    if sys.platform == "win32":
        return r"C:\Windows\System32\drivers\etc\hosts"
    else:
        return "/etc/hosts"


def is_admin() -> bool:
    """当前进程是否有权限修改 hosts。"""
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        return os.geteuid() == 0


def elevate() -> None:
    """以管理员权限重新启动当前脚本。"""
    script = os.path.abspath(sys.argv[0])
    if sys.platform == "win32":
        # Windows: 用 runas 或者直接报错让用户手动提权
        ctypes = __import__("ctypes")
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}"', None, 1
        )
        if ret <= 32:
            print("[!] 提权失败，请右键 → 以管理员身份运行此脚本。")
        sys.exit(0)
    else:
        os.execvp("sudo", ["sudo", sys.executable, script])


# ============ DNS 解析 ============

def resolve_host(host: str) -> list[str]:
    """解析域名，返回 IPv4 地址列表。"""
    try:
        _, _, addrlist = socket.gethostbyname_ex(host)
        return addrlist
    except socket.gaierror:
        return []


# ============ 连通性检测 ============

def tcp_reachable(ip: str, port: int, timeout: float) -> bool:
    """尝试 TCP 连接，成功返回 True。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def dns_is_healthy(host: str, port: int, timeout: float) -> bool:
    """DNS 解析出的 IP 中至少一个可达即视为健康。"""
    ips = resolve_host(host)
    if not ips:
        return False
    for ip in ips:
        if tcp_reachable(ip, port, timeout):
            return True
    return False


# ============ hosts 文件操作 ============

def build_hosts_entry(ips: list[str], host: str) -> str:
    """生成要写入 hosts 的条目块。"""
    lines = [MARKER_BEGIN]
    for ip in ips:
        lines.append(f"{ip} {host}")
    lines.append(MARKER_END)
    return "\n".join(lines) + "\n"


def read_hosts(path: str) -> str:
    """读取 hosts 文件全部内容。"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_hosts(path: str, content: str) -> None:
    """写入 hosts 文件。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


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


def apply_fix(content: str, ips: list[str], host: str) -> str:
    """在 hosts 内容末尾追加备用条目。"""
    return content.rstrip("\n") + "\n\n" + build_hosts_entry(ips, host)


# ============ 状态显示 ============

def status_line(msg: str, level: str = "info") -> None:
    """带时间戳的状态输出。"""
    ts = time.strftime("%H:%M:%S")
    prefix = {"info": "[*]", "ok": "[+]", "warn": "[!]", "fix": "[>]"}.get(level, "[*]")
    print(f"{ts} {prefix} {msg}")


# ============ 主循环 ============

def check_and_fix(hosts_path: str) -> str:
    """
    单次检测 → 修复周期。
    返回状态字符串: "healthy", "fixed", "removed", "noop", "no-permission"
    """
    if not is_admin():
        return "no-permission"

    content = read_hosts(hosts_path)
    healthy = dns_is_healthy(TARGET_HOST, TARGET_PORT, CONNECT_TIMEOUT)

    if healthy:
        if has_fix(content):
            new_content = remove_fix(content)
            write_hosts(hosts_path, new_content)
            return "removed"
        return "healthy"
    else:
        if has_fix(content):
            return "noop"  # 已经修过，DNS 仍然不通，保持不变
        new_content = apply_fix(content, FALLBACK_IPS, TARGET_HOST)
        write_hosts(hosts_path, new_content)
        return "fixed"


def main() -> None:
    hosts_path = get_hosts_path()

    # 启动自检
    print("=" * 60)
    print("  DeepSeek API 网络修复守护")
    print(f"  目标: {TARGET_HOST}:{TARGET_PORT}")
    print(f"  检测间隔: {CHECK_INTERVAL}s")
    print(f"  备用 IP: {', '.join(FALLBACK_IPS)}")
    print(f"  hosts: {hosts_path}")
    print("=" * 60)

    if not is_admin():
        print()
        status_line("需要管理员/root 权限才能修改 hosts 文件。", "warn")
        if sys.platform == "win32":
            status_line("正在请求提权...", "info")
            elevate()  # 不会返回
        else:
            status_line("请用 sudo 重新运行:  sudo python3 deepseek-fix.py", "warn")
            sys.exit(1)

    status_line("守护进程已启动。按 Ctrl+C 退出。", "ok")

    # 首次立即检测
    status_line("首次检测中...", "info")
    result = check_and_fix(hosts_path)
    _announce(result)

    # 循环
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            result = check_and_fix(hosts_path)
            _announce(result)
        except KeyboardInterrupt:
            print()
            status_line("收到退出信号。", "info")
            break

    # 退出时清理 hosts（可选）
    status_line("正在清理 hosts 条目...", "info")
    if is_admin():
        content = read_hosts(hosts_path)
        if has_fix(content):
            write_hosts(hosts_path, remove_fix(content))
            status_line("hosts 条目已清理。", "ok")
        else:
            status_line("无需清理。", "info")

    status_line("已退出。", "ok")


def _announce(result: str) -> None:
    """根据检测结果输出对应状态。"""
    messages = {
        "healthy":    ("DNS 可达，无需修复。", "ok"),
        "fixed":      ("DNS 全部不通！已启用备用 IP。", "fix"),
        "removed":    ("DNS 已恢复！已移除 hosts 覆盖，切回正常解析。", "ok"),
        "noop":       ("DNS 仍未恢复，保持备用 IP 不变。", "info"),
        "no-permission": ("无权限修改 hosts，跳过本轮。请以管理员身份运行。", "warn"),
    }
    msg, level = messages.get(result, (f"未知状态: {result}", "warn"))
    status_line(msg, level)


if __name__ == "__main__":
    main()
