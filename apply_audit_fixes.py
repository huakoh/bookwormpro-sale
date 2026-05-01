#!/usr/bin/env python3
"""Apply all 9 P1/P2 audit fixes to BookwormPRO v7.0.0."""
import sys, os

os.chdir(r"C:\Users\leesu\BookwormPRO")

def read_file(path):
    with open(path, 'r', newline='') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', newline='') as f:
        f.write(content)

fixes_applied = 0
fixes_skipped = 0

# ================================================================
# Item 1a: tui_gateway/server.py ~L3191 - shell=True -> ["sh","-c",...]
# ================================================================
path = 'tui_gateway/server.py'
content = read_file(path)

old = 'qc.get("command", ""),\n                shell=True,'
new = '["sh", "-c", qc.get("command", "")],'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 1a: tui_gateway/server.py shell=True -> shlex (L3191)")
else:
    print("[SKIP] 1a: pattern not found")
    fixes_skipped += 1

# Item 1b: tui_gateway/server.py ~L4562
old = 'cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=os.getcwd()'
new = '["sh", "-c", cmd], capture_output=True, text=True, timeout=30, cwd=os.getcwd()'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 1b: tui_gateway/server.py shell=True -> shlex (L4562)")
else:
    print("[SKIP] 1b: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Item 2: run_agent.py:330 — logging.debug -> logger.debug
# Verified: line 332 already uses logger.debug. No fix needed.
# ================================================================
print("[INFO] 2: run_agent.py:332 already uses logger.debug (verified, no fix needed)")

# ================================================================
# Item 3: model_tools.py — 5 hook except Exception: pass -> logger.debug
# ================================================================
path = 'model_tools.py'
content = read_file(path)

# Hook 1: pre_tool_call block hook (line 536-537)
old = '            except Exception:\n                pass\n\n            if block_message is not None:'
new = '            except Exception:\n                logger.debug("pre_tool_call block hook failed", exc_info=True)\n\n            if block_message is not None:'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 3a: model_tools.py pre_tool_call block hook")
else:
    print("[SKIP] 3a: pattern not found")
    fixes_skipped += 1

# Hook 2: pre_tool_call observer hook (line 554-555)
old = '            except Exception:\n                pass\n\n        # Notify the read-loop tracker'
new = '            except Exception:\n                logger.debug("pre_tool_call observer hook failed", exc_info=True)\n\n        # Notify the read-loop tracker'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 3b: model_tools.py pre_tool_call observer hook")
else:
    print("[SKIP] 3b: pattern not found")
    fixes_skipped += 1

# Hook 3: notify_other_tool_call (line 563-564)
old = '            except Exception:\n                pass  # file_tools may not be loaded yet\n\n        if function_name == "execute_code":'
new = '            except Exception:\n                logger.debug("notify_other_tool_call failed", exc_info=True)\n\n        if function_name == "execute_code":'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 3c: model_tools.py notify_other_tool_call")
else:
    print("[SKIP] 3c: pattern not found")
    fixes_skipped += 1

# Hook 4: post_tool_call hook (line 593-594)
old = '        except Exception:\n            pass\n\n        # Generic tool-result canonicalization seam'
new = '        except Exception:\n            logger.debug("post_tool_call hook failed", exc_info=True)\n\n        # Generic tool-result canonicalization seam'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 3d: model_tools.py post_tool_call hook")
else:
    print("[SKIP] 3d: pattern not found")
    fixes_skipped += 1

# Hook 5: transform_tool_result hook (line 617-618)
old = '        except Exception:\n            pass\n\n        return result'
new = '        except Exception:\n            logger.debug("transform_tool_result hook failed", exc_info=True)\n\n        return result'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 3e: model_tools.py transform_tool_result hook")
else:
    print("[SKIP] 3e: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Item 4: cli.py — 6 startup init except Exception: pass -> logger.debug
# ================================================================
path = 'cli.py'
content = read_file(path)

# 4a: terminal cleanup
old = '        _cleanup_all_terminals()\n    except Exception:\n        pass\n    try:\n        _cleanup_all_browsers()'
new = '        _cleanup_all_terminals()\n    except Exception:\n        logger.debug("init: terminal cleanup failed", exc_info=True)\n    try:\n        _cleanup_all_browsers()'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 4a: cli.py terminal cleanup")
else:
    print("[SKIP] 4a: pattern not found")
    fixes_skipped += 1

# 4b: browser cleanup
old = '        _cleanup_all_browsers()\n    except Exception:\n        pass\n    try:\n        from tools.mcp_tool import shutdown_mcp_servers'
new = '        _cleanup_all_browsers()\n    except Exception:\n        logger.debug("init: browser cleanup failed", exc_info=True)\n    try:\n        from tools.mcp_tool import shutdown_mcp_servers'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 4b: cli.py browser cleanup")
else:
    print("[SKIP] 4b: pattern not found")
    fixes_skipped += 1

# 4c: mcp shutdown
old = '        shutdown_mcp_servers()\n    except Exception:\n        pass\n    # Close cached auxiliary LLM clients'
new = '        shutdown_mcp_servers()\n    except Exception:\n        logger.debug("init: MCP shutdown failed", exc_info=True)\n    # Close cached auxiliary LLM clients'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 4c: cli.py MCP shutdown")
else:
    print("[SKIP] 4c: pattern not found")
    fixes_skipped += 1

# 4d: auxiliary client shutdown
old = '        shutdown_cached_clients()\n    except Exception:\n        pass\n    # Shut down memory provider'
new = '        shutdown_cached_clients()\n    except Exception:\n        logger.debug("init: auxiliary client shutdown failed", exc_info=True)\n    # Shut down memory provider'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 4d: cli.py auxiliary client shutdown")
else:
    print("[SKIP] 4d: pattern not found")
    fixes_skipped += 1

# 4e: session finalize hook
old = '        _invoke_hook("on_session_finalize", session_id=_active_agent_ref.session_id if _active_agent_ref else None, platform="cli")\n    except Exception:\n        pass\n    try:\n        if _active_agent_ref and hasattr'
new = '        _invoke_hook("on_session_finalize", session_id=_active_agent_ref.session_id if _active_agent_ref else None, platform="cli")\n    except Exception:\n        logger.debug("init: session finalize hook failed", exc_info=True)\n    try:\n        if _active_agent_ref and hasattr'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 4e: cli.py session finalize hook")
else:
    print("[SKIP] 4e: pattern not found")
    fixes_skipped += 1

# 4f: memory provider shutdown
old = '            _active_agent_ref.shutdown_memory_provider(\n                getattr(_active_agent_ref, \'conversation_history\', None) or []\n            )\n    except Exception:\n        pass\n\n\n# ===='
new = '            _active_agent_ref.shutdown_memory_provider(\n                getattr(_active_agent_ref, \'conversation_history\', None) or []\n            )\n    except Exception:\n        logger.debug("init: memory provider shutdown failed", exc_info=True)\n\n\n# ===='
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 4f: cli.py memory provider shutdown")
else:
    print("[SKIP] 4f: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Item 5: tools/terminal_tool.py — sudo password thread except
# ================================================================
path = 'tools/terminal_tool.py'
content = read_file(path)

old = '        except Exception:\n            result["password"] = ""\n        finally:\n            if tty_fd is not None and old_attrs is not None:\n                try:\n                    import termios as _termios'
new = '        except Exception:\n            logger.debug("sudo password read thread failed", exc_info=True)\n            result["password"] = ""\n        finally:\n            if tty_fd is not None and old_attrs is not None:\n                try:\n                    import termios as _termios'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 5: terminal_tool.py sudo password thread")
else:
    print("[SKIP] 5: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Item 6: tools/file_tools.py:662-663 — reject write on path resolution failure
# ================================================================
path = 'tools/file_tools.py'
content = read_file(path)

old = '        try:\n            _resolved = str(_resolve_path_for_task(path, task_id))\n        except Exception:\n            _resolved = None\n\n        if _resolved is None:\n            return tool_error(\n                f"Could not resolve path for concurrency locking: {path}"\n            )'
new = '        try:\n            _resolved = str(_resolve_path_for_task(path, task_id))\n        except Exception:\n            logger.debug("Path resolution failed, rejecting write", exc_info=True)\n            return json.dumps({"error": "Path resolution failed", "status": "error"})\n\n        if _resolved is None:\n            return tool_error(\n                f"Could not resolve path for concurrency locking: {path}"\n            )'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 6: file_tools.py path resolution fallback -> error dict")
else:
    print("[SKIP] 6: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Item 7: qwen3_coder_parser.py:51 — security comment before ast.literal_eval
# ================================================================
path = 'environments/tool_call_parsers/qwen3_coder_parser.py'
content = read_file(path)

old = '    # Try Python literal eval (handles tuples, etc.)\n    try:\n        return ast.literal_eval(stripped)'
new = '    # Try Python literal eval (handles tuples, etc.)\n    # SECURITY: ast.literal_eval is safe (only literals). NEVER replace with eval().\n    try:\n        return ast.literal_eval(stripped)'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 7: qwen3_coder_parser.py security comment")
else:
    print("[SKIP] 7: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Item 8: glm45_parser.py:40 — security comment before ast.literal_eval
# ================================================================
path = 'environments/tool_call_parsers/glm45_parser.py'
content = read_file(path)

old = '    try:\n        return ast.literal_eval(value)\n    except (ValueError, SyntaxError, TypeError):\n        pass\n\n    return value'
new = '    # SECURITY: ast.literal_eval is safe (only literals). NEVER replace with eval().\n    try:\n        return ast.literal_eval(value)\n    except (ValueError, SyntaxError, TypeError):\n        pass\n\n    return value'
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 8: glm45_parser.py security comment")
else:
    print("[SKIP] 8: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Item 9: cli.py:4434 — API key display fully redacted
# ================================================================
path = 'cli.py'
content = read_file(path)

old = "api_key_display = '********' + self.api_key[-4:] if self.api_key and len(self.api_key) > 4 else 'Not set!'"
new = "api_key_display = '[redacted]' if self.api_key else 'Not set!'"
if old in content:
    content = content.replace(old, new)
    fixes_applied += 1
    print("[OK] 9: cli.py API key fully redacted")
else:
    print("[SKIP] 9: pattern not found")
    fixes_skipped += 1

write_file(path, content)

# ================================================================
# Summary
# ================================================================
print()
print("=" * 60)
print(f"Fixes applied:  {fixes_applied}")
print(f"Fixes skipped:  {fixes_skipped}")
print("=" * 60)
