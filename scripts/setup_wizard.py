#!/usr/bin/env python3

"""

BookwormPRO 智能安装向导 v2.0

- 新手模式: 一键全默认，只填 Key

- 专家模式: 自定义每个选项

- 进度条 + 彩色输出

"""



import sys, os, re, shutil, time, argparse

from pathlib import Path



# ── 终端色彩 ──

C = {'R':'\033[91m','G':'\033[92m','Y':'\033[93m','B':'\033[94m','M':'\033[95m','C':'\033[96m','W':'\033[97m','X':'\033[0m','D':'\033[2m'}

if sys.platform == 'win32':

    try:

        import ctypes

        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)

    except: 

        for k in C: C[k] = ''



HOME = Path.home()

TARGET = HOME / '.bookwormpro'

SRC = Path(__file__).parent.parent

MODE = 'beginner'  # default



# ── 进度条 ──

def progress_bar(current, total, label="", width=30):

    pct = current / total

    filled = int(width * pct)

    bar = f"{C['G']}{'█' * filled}{C['D']}{'░' * (width - filled)}{C['X']}"

    print(f"\r  {bar} {int(pct*100)}%  {label}", end='', flush=True)

    if current == total:

        print()



def spinner(seconds, label=""):

    chars = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

    for i in range(seconds * 10):

        c = chars[i % len(chars)]

        print(f"\r  {C['C']}{c}{C['X']} {label}", end='', flush=True)

        time.sleep(0.1)

    print(f"\r  {C['G']}✅{C['X']} {label}")



# ── 显示函数 ──

def banner():

    print(f"""

{C['C']}  ╔══════════════════════════════════════════════════════╗

  ║    ____              _                                ║

  ║   | __ )  ___   ___ | | _____      _____  _ __       ║

  ║   |  _ \\ / _ \\ / _ \\| |/ / \\ \\ /\\ / / _ \\| '__|      ║

  ║   | |_) | (_) | (_) |   <  \\ V  V / (_) | |         ║

  ║   |____/ \\___/ \\___/|_|\\_\\  \\_/\\_/ \\___/|_|         ║

  ║                                                      ║

  ║         {C['W']}AI 智能助手技能包 · 安装向导 v2.0{C['C']}            ║

  ╚══════════════════════════════════════════════════════╝{C['X']}

    """)



def section(title):

    print(f"\n{C['B']}  ▸ {title}{C['X']}")



def ok(msg):    print(f"  {C['G']}✅{C['X']} {msg}")

def warn(msg):  print(f"  {C['Y']}⚠️{C['X']}  {msg}")

def fail(msg):  print(f"  {C['R']}❌{C['X']} {msg}")

def info(msg):  print(f"  {C['D']}{msg}{C['X']}")



def ask(prompt, default=None, secret=False):

    hint = f" [{default}]" if default else ""

    val = input(f"  {prompt}{hint}: ").strip()

    return val if val else default



def validate_key(key, provider):

    patterns = {

        'deepseek': r'^sk-[a-zA-Z0-9]{32,}$',

        'dashscope': r'^sk-[a-zA-Z0-9]{20,}$',

        'google': r'^AIza[0-9A-Za-z\-_]{30,}$',

    }

    if provider not in patterns:

        return True

    return bool(re.match(patterns[provider], key))



def test_api(key, base_url):

    try:

        import urllib.request

        req = urllib.request.Request(f"{base_url}/models", headers={"Authorization": f"Bearer {key}"})

        urllib.request.urlopen(req, timeout=10)

        return True

    except:

        return False



def install_skills():

    src, dst = SRC / 'skills', TARGET / 'skills'

    if dst.exists(): shutil.rmtree(dst)

    # Progress during copy

    files = list(src.rglob('*'))

    for i, f in enumerate(files):

        if f.is_dir(): continue

        rel = f.relative_to(src)

        target = dst / rel

        target.parent.mkdir(parents=True, exist_ok=True)

        if i % 50 == 0:

            progress_bar(min(i, len(files)-1), len(files), f"复制技能...")

        shutil.copy2(f, target)

    progress_bar(len(files), len(files), f"技能包完成")

    return len(list(dst.rglob('SKILL.md')))



def install_soul():

    src = SRC / 'soul'

    for f in src.glob('*.md'):

        shutil.copy(f, TARGET / f.name)

    claude_dir = HOME / '.claude'

    claude_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(SRC / 'soul' / 'SOUL.md', claude_dir / 'SOUL.md')



def install_config():

    config_src = SRC / 'config'

    if not (TARGET / 'config.yaml').exists():

        shutil.copy(config_src / 'config.yaml', TARGET / 'config.yaml')

    if not (TARGET / '.env').exists():

        shutil.copy(config_src / '.env.template', TARGET / '.env')



# ── 模式选择 ──

def choose_mode():

    global MODE

    print(f"\n  {C['W']}请选择安装模式：{C['X']}\n")

    print(f"  {C['G']}[1]{C['X']}  🚀 新手模式 — 全自动默认配置，只需填 API Key（推荐）")

    print(f"  {C['Y']}[2]{C['X']}  🔧 专家模式 — 自定义每个 Provider 和选项")

    print()

    choice = ask("请选择", default="1")

    MODE = 'beginner' if choice == '1' else 'expert'

    ok(f"模式: {'新手' if MODE == 'beginner' else '专家'}")



# ── 新手模式：快速配置 ──

def beginner_setup():

    env_lines = []

    section("API Key 配置（新手模式）")

    info("只需填一个 DeepSeek Key，其他全自动")

    

    print(f"\n  {C['W']}DeepSeek API Key{C['X']}")

    info("去 platform.deepseek.com 注册获取（支持支付宝）")

    key = ask("粘贴 Key 到这里")

    

    if key and validate_key(key, 'deepseek'):

        ok("格式正确，测试连通性...")

        if test_api(key, "https://api.deepseek.com/v1"):

            ok("连通成功！")

        else:

            warn("无法验证连通性，稍后可重新测试")

        env_lines.append(f"DEEPSEEK_API_KEY={key}")
        env_lines.append("DEEPSEEK_BASE_URL=https://api.deepseek.com/v1")
    elif key:
        fail("格式不正确（应以 sk- 开头），已跳过")
    
    return env_lines

# ── 版本检测 ──
VERSION = "1.0.0"
def check_version():
    """检查 GitHub Releases 是否有新版本"""
    try:
        import urllib.request, json
        url = "https://api.github.com/repos/huakoh/bookwormpro-sale/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "BookwormPRO"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        latest = data.get("tag_name", "").lstrip("v")
        if latest and latest != VERSION:
            print(f"\n  {C['Y']}📦 有新版本可用: v{latest}（当前 v{VERSION}）{C['X']}")
            print(f"  {C['D']}访问 https://github.com/huakoh/bookwormpro-sale/releases 下载{C['X']}")
    except:
        pass  # 网络不可用时静默跳过

# ── 遥测 ──
def telemetry_consent():
    """询问遥测同意"""
    tf = TARGET / '.telemetry'
    if tf.exists():
        return
    print(f"\n  {C['D']}📊 帮助改进？发送匿名使用统计（不上传任何个人数据）{C['X']}")
    choice = ask("同意？[y/N]", default="N")
    if choice.lower() == 'y':
        import uuid
        tf.parent.mkdir(parents=True, exist_ok=True)
        tf.write_text('{"enabled":true,"install_id":"' + str(uuid.uuid4())[:12] + '"}')
        ok("已启用，感谢！")
    else:
        info("已跳过")


# ── 专家模式：全部自定义 ──

def expert_setup():

    env_lines = []

    section("API Key 配置（专家模式）")

    info("Key 只存储在本地，不会上传\n")

    

    # DeepSeek

    print(f"  {C['W']}── DeepSeek（推荐）──{C['X']}")

    key = ask("API Key")

    if key:

        if validate_key(key, 'deepseek'):

            ok("格式正确")

            env_lines.append(f"DEEPSEEK_API_KEY={key}")

            env_lines.append("DEEPSEEK_BASE_URL=https://api.deepseek.com/v1")

        else:

            fail("格式不正确")

    else:

        info("跳过")

    

    # DashScope

    print(f"\n  {C['W']}── 通义千问/DashScope（视觉+图片生成）──{C['X']}")

    key = ask("API Key")

    if key:

        if validate_key(key, 'dashscope'):

            ok("格式正确")

            env_lines.append(f"DASHSCOPE_API_KEY={key}")

            env_lines.append("DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1")

            env_lines.append("AUXILIARY_VISION_MODEL=qwen-vl-max")

        else:

            fail("格式不正确")

    else:

        info("跳过")

    

    # Gemini

    print(f"\n  {C['W']}── Google Gemini（可选）──{C['X']}")

    key = ask("API Key")

    if key and validate_key(key, 'google'):

        ok("格式正确")

        env_lines.append(f"GOOGLE_API_KEY={key}")

    elif key:

        fail("格式不正确")

    else:

        info("跳过")

    

    return env_lines



# ── 主流程 ──

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument('--beginner', action='store_true', help='新手模式')

    parser.add_argument('--expert', action='store_true', help='专家模式')

    parser.add_argument('--quick', action='store_true', help='超快模式（跳过交互）')

    args = parser.parse_args()

    

    banner()

    

    # 模式

    if args.quick:

        MODE = 'beginner'

        print(f"\n  {C['C']}⚡ 超快模式 — 仅复制文件，之后手动编辑 ~/.bookwormpro/.env{C['X']}")

        TARGET.mkdir(parents=True, exist_ok=True)

        spinner(1, "安装技能包...")

        n = install_skills()

        install_soul()

        install_config()

        ok(f"完成！{n} 个技能已安装")

        print(f"\n  {C['W']}下一步：{C['X']} 编辑 {TARGET / '.env'} 填入 API Key，重启 AI 助手")

        return

    

    if args.expert:

        MODE = 'expert'

    elif args.beginner:

        MODE = 'beginner'

    else:

        choose_mode()

    

    # 安装流程

    section(f"开始安装（{MODE}模式）")

    TARGET.mkdir(parents=True, exist_ok=True)

    

    # API 配置

    env_lines = beginner_setup() if MODE == 'beginner' else expert_setup()

    

    if not env_lines:

        warn("未配置任何 API Key，可稍后手动编辑 .env 添加")

    

    # 安装文件（带进度条）

    section("安装技能文件")

    n = install_skills()

    ok(f"{n} 个技能就绪")

    

    install_soul()

    ok("SOUL.md + CLAUDE.md 就绪")

    

    install_config()

    ok("config.yaml + .env 就绪")

    

    # 写入 .env

    env_file = TARGET / '.env'

    with open(env_file, 'a', encoding='utf-8') as f:

        if env_lines:

            f.write('\n' + '\n'.join(env_lines) + '\n')

    

    # 完成

    spinner(1, "最终验证...")

    section("安装完成！")

    

    not_ready = []

    if not (TARGET / 'skills').exists(): not_ready.append("技能文件")

    if not (TARGET / 'SOUL.md').exists(): not_ready.append("SOUL.md")

    if not env_lines: not_ready.append("API Key")

    

    if not_ready:

        print(f"\n  {C['Y']}⚠ 以下项目需关注：{C['X']}")

        for item in not_ready: print(f"    · {item}")

    else:

        print(f"\n  {C['G']}✅ 所有组件就绪！{C['X']}")

    

    print(f"""

  {C['W']}📋 下一步：{C['X']}

    1. 打开 {C['C']}docs/快速开始.html{C['X']} 查看图文教程

    2. 重启 AI 助手

    3. 输入 {C['C']}bookworm自检{C['X']} 验证



  {C['D']}诊断: python scripts/check.py{C['X']}

  {C['D']}更新: 重新运行本向导即可{C['X']}

    """)



if __name__ == '__main__':

    try:

        main()

    except KeyboardInterrupt:

        print(f"\n\n{C['Y']}  安装已取消{C['X']}\n")

    except Exception as e:

        print(f"\n{C['R']}  ❌ 错误: {e}{C['X']}\n")

        sys.exit(1)

