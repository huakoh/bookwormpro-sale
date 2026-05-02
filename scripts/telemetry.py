#!/usr/bin/env python3
"""
BookwormPRO 遥测模块 (opt-in, 匿名)
仅在用户明确同意后才上报。不上传任何个人数据、API Key 或文件内容。
"""

import json, urllib.request, uuid, platform, sys
from pathlib import Path

TELEMETRY_URL = "https://telemetry.bookwormpro.example.com/ping"  # 占位
TELEMETRY_FILE = Path.home() / '.bookwormpro' / '.telemetry'

def is_enabled():
    """检查用户是否已同意遥测"""
    if not TELEMETRY_FILE.exists():
        return False
    try:
        data = json.loads(TELEMETRY_FILE.read_text())
        return data.get('enabled', False)
    except:
        return False

def enable():
    """启用遥测"""
    TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    install_id = str(uuid.uuid4())[:12]
    TELEMETRY_FILE.write_text(json.dumps({
        'enabled': True,
        'install_id': install_id,
        'version': '1.0.0',
        'os': platform.system(),
        'python': sys.version.split()[0],
    }))
    return install_id

def disable():
    """禁用遥测"""
    if TELEMETRY_FILE.exists():
        TELEMETRY_FILE.unlink()

def ping(event, **data):
    """发送遥测事件（匿名）"""
    if not is_enabled():
        return
    
    try:
        cfg = json.loads(TELEMETRY_FILE.read_text())
        payload = {
            'install_id': cfg.get('install_id'),
            'event': event,
            'version': cfg.get('version'),
            'os': cfg.get('os'),
            **data
        }
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=5)
    except:
        pass  # 遥测失败不影响用户

def ask_consent():
    """询问用户是否同意遥测"""
    if TELEMETRY_FILE.exists():
        return  # 已经决定过
    
    print(f"""
  📊 帮助我们改进 BookwormPRO

  是否允许发送匿名使用统计？我们只收集：
    · 安装事件（新版本安装量）
    · 技能使用频次（哪些技能最受欢迎）
    · 操作系统和 Python 版本

  ❌ 不会收集：
    · API Key 或任何凭据
    · 对话内容
    · 文件名或项目信息
    · 任何可识别个人身份的信息

  [1] ✅ 同意，帮助改进（推荐）
  [2] ❌ 不同意
    """)
    
    choice = input("  请选择 [1/2]: ").strip()
    if choice == '1':
        enable()
        print("  ✅ 已启用匿名遥测，感谢！")
    else:
        print("  ⚪ 已跳过")
