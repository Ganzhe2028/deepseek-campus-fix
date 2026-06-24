# 🛰️ 校园网 DeepSeek API 一键修复

> 如果你在学校里用 DeepSeek 的 API 或聊天，经常**一会儿能用一会儿不行**，这个脚本就是给你的。

---

## 🤔 这是干嘛的？

你的校园网到 DeepSeek 服务器的某几条线路是断的。就像快递有两条路可以走，但其中一条被封了。每次你用 DeepSeek，你的电脑随机选一条路——运气好通了，运气不好就卡死。

这个脚本做的事情很简单：**帮你检查路通不通，不通的话自动换成能走的那条。**

你只需要双击运行一次，它就在后台默默守着了。校园网哪天修好了，它也会自动退回去，不用你再管。

---

## 📦 你需要准备什么

| 东西 | 说明 |
|------|------|
| Python 3 | 几乎每台电脑都有。如果没有 → [python.org](https://www.python.org/downloads/) 下载安装，装的时候**勾选 "Add Python to PATH"** |
| 管理员权限 | 脚本需要写一个系统文件（hosts），所以需要管理员运行 |
| 这个脚本 | 就一个文件 `deepseek-fix.py`，下载到任意位置就行 |

---

## 🚀 怎么用

### Windows

1. **下载** 这个仓库里的 `deepseek-fix.py`，放到桌面上（放哪都行，你记得住就行）
2. **右键** `deepseek-fix.py` → 复制文件路径
3. **右键** Windows 开始菜单 → **终端（管理员）** 或 **PowerShell（管理员）**
4. 输入下面这行命令（把 `文件路径` 换成你刚才复制的路径）：

```powershell
python "文件路径"
```

比如你放在了 `D:\tools\deepseek-fix.py`，就输入：

```powershell
python "D:\tools\deepseek-fix.py"
```

5. 看到 `守护进程已启动` 就说明跑起来了。**窗口不要关**，最小化放后台就行。
6. 不用的时候按 `Ctrl + C` 退出，它会自动把改过的东西清理干净。

> 💡 **想开机自动启动？** 按 `Win + R`，输入 `shell:startup`，把脚本的**快捷方式**丢进去就行了。

### macOS

1. 下载 `deepseek-fix.py`
2. 打开 **终端**（在 启动台 → 其他 → 终端）
3. 输入：

```bash
sudo python3 ~/Downloads/deepseek-fix.py
```

4. 输入你的电脑密码（输入时屏幕不会显示，正常现象）
5. 看到 `守护进程已启动` 就行了。按 `Ctrl + C` 退出。

### Linux

```bash
sudo python3 deepseek-fix.py
```

---

## 🧠 它到底干了什么（一句话版）

每 5 分钟问一次：DeepSeek 的服务器通不通？

- ✅ **通的** → 什么都不做（或者把之前改过的东西恢复）
- ❌ **不通** → 自动把你的网络指向一条能走的路

---

## 🗺️ 三种场景，你都不用管

| 你在哪里 | 网络状态 | 脚本做什么 |
|----------|----------|------------|
| 🏫 在校园 | 网不好（现在） | 检测到不通 → 自动修复 |
| 🏫 在校园 | 网修好了（以后） | 检测到通了 → 自动恢复，零操作 |
| 🏠 回家/离校 | 网本来就好 | 什么都不改，零影响 |

---

## ❓ 常见问题

<details>
<summary><b>提示"需要管理员/root 权限"？</b></summary>

Windows：右键 → 以管理员身份运行终端或 PowerShell，再执行命令。

macOS/Linux：记得命令前面加 `sudo`。
</details>

<details>
<summary><b>备用 IP 是什么？会过期吗？</b></summary>

脚本里写了两个备用的 DeepSeek 服务器 IP，万一这两个也挂了，打开脚本文件，找到：

```python
FALLBACK_IPS = [
    "183.131.191.171",
    "61.170.66.121",
]
```

换成新的 IP 就行。怎么找新 IP 见下一节。
</details>

<details>
<summary><b>怎么找新的可用 IP？</b></summary>

在终端里运行这几行（Windows 把单引号换成双引号）：

```bash
# 1. 查 DNS 给了哪些 IP
nslookup api.deepseek.com

# 2. 挨个试能不能连上 443 端口
curl -o /dev/null -w "%{http_code}" --connect-timeout 5 https://替换成IP/v1/models -H "Host: api.deepseek.com"
# Windows 用户用这个：
# curl.exe -o NUL -w "%{http_code}" --connect-timeout 5 https://替换成IP/v1/models -H "Host: api.deepseek.com"
```

返回 `401`（没带 API key 的正常报错）就说明通。`000` 就是不通。
</details>

<details>
<summary><b>会影响校园网其他网站吗？</b></summary>

不会。脚本只改 `api.deepseek.com` 这一个地址，其他网站完全不受影响。
</details>

<details>
<summary><b>关掉脚本后 hosts 会被恢复吗？</b></summary>

会的。按 `Ctrl + C` 正常退出时会自动清理。如果异常退出（比如直接关窗口），hosts 里会留一条记录，不影响用，下次运行脚本时会自己清理。
</details>

---

## ⚙️ 自定义配置

打开 `deepseek-fix.py`，文件开头有个配置区，你可以改：

```python
CHECK_INTERVAL = 300        # 多久检查一次（秒），默认 5 分钟
CONNECT_TIMEOUT = 5          # 连接超时（秒）
FALLBACK_IPS = [             # 备用的服务器 IP 列表
    "183.131.191.171",
    "61.170.66.121",
]
```

改完保存，重启脚本就生效。

---

## 📜 协议

MIT License。随便用、随便改、随便分享。

如果这个脚本帮到了你，给个 ⭐ Star 让更多校园网受苦的同学看到。
