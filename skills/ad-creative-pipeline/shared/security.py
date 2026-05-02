"""
AdCreativePipeline — 安全模块 (P0 修复)
- Prompt 注入过滤 (S2)
- API Key 保护 (S1)
- 路径沙箱 (S4)
- 评审数据脱敏 (S5)
"""

import os
import re
from pathlib import Path

# ── Prompt 注入过滤 ──────────────────────────────────

BLOCKED_PATTERNS = [
    # 英文注入
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|directives?)",
    r"disregard\s+(all\s+)?(previous|instructions?)",
    r"bypass\s+(safety|content|filter)",
    r"jailbreak",
    r"you\s+are\s+now\s+(DAN|jailbroken)",
    r"pretend\s+you\s+are",
    r"switch\s+role",
    r"new\s+instructions?:",
    # 中文注入
    r"忽略(以上|之前|所有)?(指令|提示|规则)",
    r"无视(以上|之前)?(指令|内容|限制)",
    r"绕过(安全|审查|过滤)",
    r"你(现在|已经)(是|变成)",
    r"越狱",
    r"新的指令[：:]",
    # 内容安全
    r"色情",
    r"裸体",
    r"暴力",
    r"血腥",
]

def sanitize_prompt(text: str) -> str:
    """
    P0-3: Prompt 注入过滤
    检测恶意注入模式，命中任一即拒绝
    """
    text_lower = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text_lower):
            raise PromptSecurityError(
                f"检测到不安全内容: matched pattern '{pattern}'"
            )
    return text

def sanitize_all(*texts: str) -> list[str]:
    """批量过滤"""
    return [sanitize_prompt(t) for t in texts if t]


class PromptSecurityError(Exception):
    """Prompt 安全异常"""
    pass


# ── API Key 保护 ─────────────────────────────────────

def get_api_key(key_name: str) -> str:
    """
    P0-1: 安全的 API Key 读取
    优先从 BookwormPRO 加密存储读取，fallback 到环境变量（带脱敏日志）
    """
    # 尝试从 BookwormPRO 加密存储读取
    try:
        from bookwormpro.security import decrypt_key
        encrypted = decrypt_key(key_name)
        if encrypted:
            return encrypted
    except ImportError:
        pass

    # Fallback: 环境变量
    env_name = key_name.upper().replace("-", "_")
    key = os.environ.get(env_name, "")
    if not key:
        raise KeyError(f"API Key not found: {key_name} (env: {env_name})")

    return key


def mask_key(key: str) -> str:
    """脱敏 Key: 只显示前4后4"""
    if len(key) <= 8:
        return "****"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


# ── 路径沙箱 ─────────────────────────────────────────

OUTPUT_SANDBOX = Path.home() / ".bookwormpro" / "output"

def ensure_sandboxed(path: str | Path) -> Path:
    """
    P2-5: 确保路径在 sandbox 内
    所有文件写入必须经过此函数
    """
    resolved = Path(path).resolve()
    allowed = OUTPUT_SANDBOX.resolve()

    try:
        resolved.relative_to(allowed)
    except ValueError:
        raise PathSecurityError(
            f"路径越界: {resolved} 不在允许的沙箱 {allowed} 内"
        )

    return resolved


class PathSecurityError(Exception):
    pass


# ── 评审数据脱敏 ─────────────────────────────────────

def sanitize_critic_output(raw: dict) -> dict:
    """
    P0-S5: 评审结果脱敏
    保留评分数字，移除可能含敏感信息的文字描述
    """
    safe = {
        "overall_score": raw.get("overall_score"),
        "pass": raw.get("pass"),
        "needs_regeneration": raw.get("needs_regeneration"),
        "needs_fix": raw.get("needs_fix"),
    }
    # 只保留各维度的数字评分
    details = raw.get("details", {})
    safe_details = {}
    for k, v in details.items():
        safe_details[k] = {
            "score": v.get("score"),
            "issue_count": len(v.get("issues", []))
            # 不保留 issues 文字和 fix_suggestions
        }
    safe["details"] = safe_details
    return safe
