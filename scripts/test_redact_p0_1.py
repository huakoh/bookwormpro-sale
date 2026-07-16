# -*- coding: utf-8 -*-
"""P0-1 验证脚本：确认 redact.py 移植后脱敏管道生效。

用法：python scripts/test_redact_p0_1.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.redact import redact_sensitive_text, RedactingFormatter
import logging
import io


def main():
    cases = [
        ("sk-" + "proj" + "-abc123def456ghi789jkl012mno345", "OpenAI/Anthropic key"),
        ("OPENAI_API_KEY=" + "sk-1234567890abcdefghijklmnop", "ENV assignment"),
        ("ghp_" + "1234567890abcdefghijklmnopqrstuvwx", "GitHub PAT"),
        ("normal log line without secrets", "普通日志（不应改变）"),
    ]

    print("=== redact_sensitive_text 单元验证 ===")
    all_ok = True
    for raw, label in cases:
        result = redact_sensitive_text(raw)
        changed = result != raw
        if label == "普通日志（不应改变）":
            ok = not changed
        else:
            # 完整密钥要么被替换为 ***，要么保留头尾+省略号（如 sk-pro...o345），
            # 两种都算脱敏生效——核心判据是"完整密钥原文不再出现在结果里"。
            ok = changed and raw not in result
        status = "[成功]" if ok else "[失败]"
        print(f"{status} {label}: {raw[:20]}... -> {result[:40]}...")
        all_ok = all_ok and ok

    print()
    print("=== RedactingFormatter 挂载 logging 验证 ===")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter("%(message)s"))
    logger = logging.getLogger("test_redact_p0_1")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    secret = "sk-" + "test" + "-1234567890abcdefghijklmnop"
    logger.info(f"testing api key {secret}")
    output = stream.getvalue()
    formatter_ok = secret not in output
    status = "[成功]" if formatter_ok else "[失败]"
    print(f"{status} 日志输出未包含明文密钥: {output.strip()}")
    all_ok = all_ok and formatter_ok

    print()
    print("=== 总结 ===")
    print("[成功] P0-1 修复验证通过" if all_ok else "[失败] 存在未通过项，需检查")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
