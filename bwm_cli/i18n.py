"""
BookwormPRO i18n 国际化模块。

用法：
    from bwm_cli.i18n import _, setup_i18n, get_language
    print(_("Welcome to BookwormPRO"))  # → "欢迎使用 BookwormPRO"

语言检测顺序：config.yaml ``language`` → ``LANG`` 环境变量 → 默认 ``zh_CN``。
使用自实现翻译器（不依赖系统 gettext locale），确保 Windows 中文环境正常。
"""

from __future__ import annotations

import os
import struct
import threading
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 翻译器实现（自包含，UTF-8，不依赖系统 locale）
# ---------------------------------------------------------------------------

class _Translator:
    """轻量 .mo 文件翻译器。"""

    def __init__(self):
        self._catalog: dict[str, str] = {}

    def load(self, mo_path: Path) -> bool:
        """加载 .mo 文件。返回是否成功。"""
        try:
            data = mo_path.read_bytes()
        except (OSError, FileNotFoundError):
            return False
        return self._parse(data)

    def _parse(self, data: bytes) -> bool:
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != 0x950412DE:
            return False

        N = struct.unpack_from("<I", data, 8)[0]
        O = struct.unpack_from("<I", data, 12)[0]
        T = struct.unpack_from("<I", data, 16)[0]

        catalog: dict[str, str] = {}
        for i in range(N):
            o_len = struct.unpack_from("<I", data, O + i * 8)[0]
            o_off = struct.unpack_from("<I", data, O + i * 8 + 4)[0]
            t_len = struct.unpack_from("<I", data, T + i * 8)[0]
            t_off = struct.unpack_from("<I", data, T + i * 8 + 4)[0]

            # 读取字符串（去掉末尾 NUL）
            orig = data[o_off : o_off + o_len].rstrip(b"\x00").decode("utf-8")
            trans = data[t_off : t_off + t_len].rstrip(b"\x00").decode("utf-8")

            if orig:  # 跳过空 header
                catalog[orig] = trans

        self._catalog = catalog
        return True

    def gettext(self, text: str) -> str:
        return self._catalog.get(text, text) or text

    def __bool__(self) -> bool:
        return bool(self._catalog)


# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
_translator: _Translator | None = None
_current_language: str | None = None
_setup_lock = threading.Lock()
_initialized = False


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

def setup_i18n(language: str | None = None, force: bool = False) -> str:
    """初始化 i18n。

    Args:
        language: 语言代码 (``zh_CN``, ``en``)。None 时自动检测。
        force: 强制重新初始化。

    Returns:
        实际使用的语言代码。
    """
    global _translator, _current_language, _initialized

    with _setup_lock:
        if _initialized and not force:
            return _current_language or "zh_CN"

        if language is None:
            language = _detect_language()

        _current_language = language

        _translator = _Translator()
        locale_dir = Path(__file__).resolve().parent.parent / "locale"

        if language and language != "en":
            mo_path = locale_dir / language / "LC_MESSAGES" / "bookwormpro.mo"
            if not _translator.load(mo_path):
                # 翻译文件不存在，回退到英文
                pass

        _initialized = True
        return _current_language or "zh_CN"


def _(text: str) -> str:
    """翻译字符串。无翻译时返回原文。"""
    global _translator, _initialized

    if not _initialized:
        setup_i18n()

    if _translator is not None and _translator:
        return _translator.gettext(text)
    return text


def get_language() -> str:
    """返回当前语言代码。"""
    if _current_language is None:
        setup_i18n()
    return _current_language or "zh_CN"


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------

def _detect_language() -> str:
    """按优先级：config → 环境变量 → zh_CN。"""
    try:
        from bwm_cli.config import load_cli_config
        config = load_cli_config()
        lang = config.get("language", "")
        if lang and lang.strip():
            return lang.strip()
    except Exception:
        pass

    for var in ("LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES"):
        val = os.environ.get(var, "")
        if val:
            lang_part = val.split(".")[0]
            if lang_part:
                return lang_part

    return "zh_CN"
