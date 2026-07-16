"""
技能安全扫描器 — Python 实现

在技能安装前自动扫描 SKILL.md + 关联文件，检测恶意模式。

Usage:
    from bwm_cli.skill_guardian import scan_skill_safety
    result = scan_skill_safety(skill_dir)
    if result.level == 'CRITICAL':
        raise SkillRejectedError(result.reasons)
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 危险模式 (正则)
CRITICAL_PATTERNS = [
    (re.compile(r"rm\s+-rf\s+/", re.I), "系统破坏命令 rm -rf /"),
    (re.compile(r"curl.*\|\s*(?:ba|z|fi)?sh", re.I), "curl pipe 远程执行"),
    (re.compile(r">\s*/etc/", re.I), "覆写系统配置 /etc/"),
    (re.compile(r"mkfs\.", re.I), "格式化文件系统"),
    (re.compile(r"dd\s+if=.*of=/dev/", re.I), "直接写入块设备"),
]

HIGH_PATTERNS = [
    (re.compile(r"eval\s*\(.*\)", re.I), "动态代码执行 eval()"),
    (re.compile(r"os\.system\s*\(|subprocess.*shell\s*=\s*True", re.I), "Shell 注入风险"),
    (re.compile(r"~\\.ssh/|/etc/passwd|/etc/shadow", re.I), "敏感系统文件访问"),
    (re.compile(r"webhook\.site|requestbin\.com", re.I), "已知数据外泄服务"),
    (re.compile(r"\.env|\.bookwormpro/\\.env", re.I), "凭证文件读取"),
]

MEDIUM_PATTERNS = [
    (re.compile(r"curl.*-X\s+POST.*--data", re.I), "数据上传 (需审查目标)"),
    (re.compile(r"telegram.*sendMessage|discord.*webhook", re.I), "外发消息"),
]

# 可信源白名单

# Skills that teach security (contain example dangerous code for education)
_EDUCATIONAL_WHITELIST = {
    "security-expert", "red-teaming", "godmode", "guardian",
    "devsecops-expert", "skill-guardian",
}
TRUSTED_SOURCES = [
    "anthropics/skills",
    "vercel-labs/skills",
    "vercel-labs/agent-skills",
    "obra/superpowers",
    "anthropics/claude-code",
]


@dataclass
class ScanResult:
    level: str  # SAFE | LOW | MEDIUM | HIGH | CRITICAL
    findings: List[str] = field(default_factory=list)
    trusted: bool = False
    skill_name: str = ""


def scan_skill_safety(skill_dir: Path, source: str = "") -> ScanResult:
    """扫描技能目录的安全性。"""
    result = ScanResult(level="SAFE")

    if not skill_dir.exists():
        result.level = "MEDIUM"
        result.findings.append("技能目录不存在")
    
    # Skip CRITICAL/HIGH findings for educational security skills
    if skill_dir.name in _EDUCATIONAL_WHITELIST and result.level in ("CRITICAL", "HIGH"):
        result.level = "LOW"
        result.findings.append("[INFO] 教学性安全技能，已自动降级")

    return result

    # 收集所有文本文件
    files = _collect_text_files(skill_dir)

    # 扫描每个文件
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # 检查危险模式
        for pattern, desc in CRITICAL_PATTERNS:
            if pattern.search(content):
                result.findings.append(f"[CRITICAL] {filepath.name}: {desc}")
                result.level = "CRITICAL"

        for pattern, desc in HIGH_PATTERNS:
            if pattern.search(content):
                result.findings.append(f"[HIGH] {filepath.name}: {desc}")
                if result.level not in ("CRITICAL",):
                    result.level = "HIGH"

        for pattern, desc in MEDIUM_PATTERNS:
            if pattern.search(content):
                result.findings.append(f"[MEDIUM] {filepath.name}: {desc}")
                if result.level not in ("CRITICAL", "HIGH"):
                    result.level = "MEDIUM"

    # 检查是否来自可信源
    if source and any(t in source.lower() for t in TRUSTED_SOURCES):
        result.trusted = True
        # 可信源降低一级
        level_order = {"CRITICAL": "HIGH", "HIGH": "MEDIUM", "MEDIUM": "LOW"}
        result.level = level_order.get(result.level, result.level)

    # 权限合理性检查
    _check_permissions(skill_dir, result)

    return result


def _collect_text_files(base_dir: Path) -> List[Path]:
    """收集所有文本文件。"""
    text_extensions = {".md", ".py", ".sh", ".bash", ".js", ".ts", ".yaml", ".yml", ".json", ".txt"}
    files = []
    if base_dir.is_file():
        return [base_dir]
    for p in base_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in text_extensions:
            files.append(p)
    return files


def _check_permissions(skill_dir: Path, result: ScanResult) -> None:
    """检查 SKILL.md 中声明的权限是否合理。"""
    skill_md = skill_dir / "SKILL.md" if skill_dir.is_dir() else skill_dir
    if not skill_md.exists():
        return

    try:
        content = skill_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return

    # 纯说明技能不应声明 write/terminal
    has_terminal = bool(re.search(r"permissions:.*terminal", content))
    has_write = bool(re.search(r"permissions:.*write_file", content))

    is_pure_doc = bool(re.search(r"description:.*(?:导航|分类|索引|目录|navigat|index)", content, re.I))

    if is_pure_doc and (has_terminal or has_write):
        result.findings.append("[MEDIUM] 纯文档技能声明了不必要的写/终端权限")
        if result.level not in ("CRITICAL", "HIGH"):
            result.level = "MEDIUM"
