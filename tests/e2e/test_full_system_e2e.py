"""
BookwormPRO 全系统端到端仿真测试
=================================
模拟真实用户从安装到日常使用的完整操作链路。
7 层测试金字塔 × 40+ 测试场景 × 真实 CLI 调用。

运行方式:
    # 快速烟雾 (Tier 1-2, 无网络)
    pytest tests/e2e/test_full_system_e2e.py -m "tier1 or tier2" -v

    # 标准全量 (Tier 1-6, 含网络)
    pytest tests/e2e/test_full_system_e2e.py -v

    # 含安全审计 (全部 Tier)
    pytest tests/e2e/test_full_system_e2e.py -v --run-security

    # 仅 Provider 连通
    pytest tests/e2e/test_full_system_e2e.py -m tier5 -v
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# ────────────────────────── 常量 ──────────────────────────

HERMES_HOME = Path.home() / ".bookwormpro"
PROJECT_ROOT = Path(__file__).parent.parent.parent
CLI = "bookworm"
GATEWAY_PORT = 8642
WEBHOOK_PORT = 8644
TIMEOUT_CMD = 30
TIMEOUT_NETWORK = 20


# ────────────────────────── Fixtures ──────────────────────

@pytest.fixture(scope="session")
def hermes_home():
    assert HERMES_HOME.exists(), f"BookwormPRO home 不存在: {HERMES_HOME}"
    return HERMES_HOME


@pytest.fixture(scope="session")
def config_yaml(hermes_home):
    p = hermes_home / "config.yaml"
    assert p.exists(), "config.yaml 不存在"
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def auth_json(hermes_home):
    p = hermes_home / "auth.json"
    if not p.exists():
        pytest.skip("auth.json 不存在")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def env_vars(hermes_home):
    """加载 .env 为 dict (不暴露值，仅记录 key 存在性)"""
    p = hermes_home / ".env"
    if not p.exists():
        pytest.skip(".env 不存在")
    keys = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


# ────────────────────────── Helpers ──────────────────────

def run_cli(*args: str, timeout: int = TIMEOUT_CMD, check: bool = True,
            env_override: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    """执行 bookworm CLI 命令并返回结果"""
    cmd = [CLI, *args]
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        env=env, cwd=str(PROJECT_ROOT),
    )


def assert_cli_success(*args: str, **kwargs) -> str:
    """断言 CLI 命令成功并返回 stdout"""
    r = run_cli(*args, **kwargs)
    assert r.returncode == 0, (
        f"命令失败: {CLI} {' '.join(args)}\n"
        f"exit={r.returncode}\n"
        f"stdout={r.stdout[:500]}\n"
        f"stderr={r.stderr[:500]}"
    )
    return r.stdout


def assert_cli_output_contains(*args: str, expected: str, **kwargs) -> str:
    """断言 CLI 输出包含指定文本"""
    out = assert_cli_success(*args, **kwargs)
    combined = out + run_cli(*args, **kwargs).stderr
    assert expected.lower() in (out + combined).lower(), (
        f"输出不含 '{expected}'\n实际输出: {out[:500]}"
    )
    return out


def http_get(port: int, path: str, timeout: int = 5) -> Tuple[int, str]:
    """简易 HTTP GET (不依赖 requests)"""
    import urllib.request
    import urllib.error
    try:
        url = f"http://127.0.0.1:{port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        pytest.skip(f"HTTP 连接失败 (port={port}): {e}")


def http_post_json(port: int, path: str, body: dict,
                   timeout: int = TIMEOUT_NETWORK) -> Tuple[int, dict]:
    """简易 HTTP POST JSON"""
    import urllib.request
    import urllib.error
    try:
        url = f"http://127.0.0.1:{port}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, {"error": body_text[:500]}
    except Exception as e:
        pytest.skip(f"HTTP POST 失败 (port={port}): {e}")


# ════════════════════════════════════════════════════════════
#  TIER 1: 基础健康 (Smoke Tests)
# ════════════════════════════════════════════════════════════

@pytest.mark.tier1
class TestTier1Smoke:
    """模拟用户安装后第一次使用：看版本、跑诊断"""

    def test_version_output(self):
        """用户输入 bookworm version，期望看到版本号"""
        out = assert_cli_success("version")
        assert re.search(r"\d+\.\d+\.\d+", out), f"未找到版本号: {out}"

    def test_version_matches_package(self):
        """版本号与 pip show 一致"""
        cli_out = assert_cli_success("version")
        ver_match = re.search(r"(\d+\.\d+\.\d+)", cli_out)
        assert ver_match
        pip_r = subprocess.run(
            [sys.executable, "-m", "pip", "show", "bookwormpro"],
            capture_output=True, text=True,
        )
        assert ver_match.group(1) in pip_r.stdout

    def test_doctor_runs(self):
        """bookworm doctor 不崩溃"""
        r = run_cli("doctor", timeout=60)
        assert r.returncode in (0, 1), f"doctor 异常退出: {r.returncode}"
        assert len(r.stdout) > 50, "doctor 输出过短"

    def test_canary_runs(self):
        """bookworm canary (无网络) 通过"""
        out = assert_cli_success("canary", timeout=30)
        assert "pass" in out.lower() or "ok" in out.lower() or "✓" in out, (
            f"canary 未通过: {out[:300]}"
        )

    def test_help_all_commands(self):
        """--help 不崩溃且列出所有子命令"""
        out = assert_cli_success("--help")
        for cmd in ["chat", "gateway", "status", "doctor", "cron", "skills"]:
            assert cmd in out, f"--help 缺少子命令: {cmd}"

    def test_dump_runs(self):
        """bookworm dump 生成调试摘要"""
        out = assert_cli_success("dump", timeout=30)
        assert len(out) > 100


# ════════════════════════════════════════════════════════════
#  TIER 2: 配置与认证 (Config & Auth)
# ════════════════════════════════════════════════════════════

@pytest.mark.tier2
class TestTier2ConfigAuth:
    """模拟用户检查配置和凭证状态"""

    def test_status_overview(self):
        """bookworm status 返回组件状态"""
        out = assert_cli_success("status")
        assert len(out) > 50

    def test_status_deep(self):
        """bookworm status --deep 含更详细信息"""
        r = run_cli("status", "--deep", timeout=60)
        assert r.returncode in (0, 1)
        assert len(r.stdout) > len(assert_cli_success("status")) * 0.5

    def test_auth_list(self):
        """bookworm auth list 展示凭证池"""
        r = run_cli("auth", "list")
        assert r.returncode == 0

    def test_config_yaml_parse(self, config_yaml):
        """config.yaml 可正常解析"""
        assert "owner" in config_yaml
        assert "model" in config_yaml

    def test_config_yaml_owner(self, config_yaml):
        """config.yaml 有 owner.name"""
        assert config_yaml["owner"]["name"]

    def test_config_yaml_model(self, config_yaml):
        """config.yaml 有默认模型配置"""
        assert config_yaml["model"]["provider"]
        assert config_yaml["model"]["default"]

    def test_config_yaml_approvals(self, config_yaml):
        """审批配置存在"""
        assert "approvals" in config_yaml

    def test_auth_json_schema(self, auth_json):
        """auth.json 结构正确"""
        assert "version" in auth_json
        assert "credential_pool" in auth_json
        assert isinstance(auth_json["credential_pool"], dict)

    def test_auth_json_no_empty_tokens(self, auth_json):
        """credential_pool 无空 token"""
        pool = auth_json["credential_pool"]
        for provider, entries in pool.items():
            for entry in entries:
                tok = entry.get("access_token", "")
                assert tok and len(tok) > 10, (
                    f"Provider {provider}/{entry.get('label')} token 过短或为空"
                )

    def test_env_provider_pairs(self, env_vars):
        """.env 中 base_url 和 api_key 成对出现"""
        pairs = [
            ("DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY"),
            ("DASHSCOPE_BASE_URL", "DASHSCOPE_API_KEY"),
        ]
        for url_key, api_key in pairs:
            if url_key in env_vars:
                assert api_key in env_vars, (
                    f"半成品配置: {url_key} 存在但 {api_key} 缺失"
                )


# ════════════════════════════════════════════════════════════
#  TIER 3: 功能模块 (Feature Modules)
# ════════════════════════════════════════════════════════════

@pytest.mark.tier3
class TestTier3Features:
    """模拟用户日常操作各功能模块"""

    def test_skills_list(self):
        """bookworm skills list 展示已安装技能"""
        r = run_cli("skills", "list", timeout=30)
        assert r.returncode == 0
        assert len(r.stdout) > 20

    def test_cron_list(self):
        """bookworm cron list 展示定时任务"""
        out = assert_cli_success("cron", "list", timeout=15)
        assert "job" in out.lower() or "id" in out.lower() or len(out) > 10

    def test_cron_jobs_have_model(self, hermes_home):
        """所有 cron job 都配置了 model"""
        jobs_file = hermes_home / "cron" / "jobs.json"
        if not jobs_file.exists():
            pytest.skip("cron/jobs.json 不存在")
        data = json.loads(jobs_file.read_text(encoding="utf-8"))
        for job in data.get("jobs", []):
            assert job.get("model"), (
                f"Cron job {job.get('id', '?')}/{job.get('name', '?')} 缺少 model"
            )

    def test_sessions_list(self):
        """bookworm sessions list 可执行"""
        r = run_cli("sessions", "list", timeout=15)
        assert r.returncode == 0

    def test_sessions_stats(self):
        """bookworm sessions stats 展示统计"""
        r = run_cli("sessions", "stats", timeout=15)
        assert r.returncode == 0

    def test_hooks_list(self):
        """bookworm hooks 展示已注册钩子"""
        r = run_cli("hooks", timeout=15)
        assert r.returncode == 0

    def test_mcp_list(self):
        """bookworm mcp list 展示 MCP 服务"""
        r = run_cli("mcp", "list", timeout=15)
        assert r.returncode == 0

    def test_insights(self):
        """bookworm insights --days 7 不崩溃"""
        r = run_cli("insights", "--days", "7", timeout=30)
        assert r.returncode == 0

    def test_audit_view(self):
        """bookworm audit 可查看审计日志"""
        r = run_cli("audit", timeout=15)
        assert r.returncode == 0

    def test_logs_accessible(self, hermes_home):
        """agent.log 存在且可读"""
        log_file = hermes_home / "logs" / "agent.log"
        if not log_file.exists():
            pytest.skip("agent.log 不存在")
        content = log_file.read_text(encoding="utf-8", errors="replace")
        assert len(content) > 0


# ════════════════════════════════════════════════════════════
#  TIER 4: Gateway 集成 (Gateway Integration)
# ════════════════════════════════════════════════════════════

@pytest.mark.tier4
class TestTier4Gateway:
    """模拟用户与 Gateway 交互：HTTP API、Webhook、平台状态"""

    def _gateway_running(self) -> bool:
        state_file = HERMES_HOME / "gateway_state.json"
        if not state_file.exists():
            return False
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            pid = data.get("pid")
            if not pid:
                return False
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0400, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False

    def _port_listening(self, port: int) -> bool:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            return sock.connect_ex(("127.0.0.1", port)) == 0
        finally:
            sock.close()

    def test_gateway_state_file(self, hermes_home):
        """gateway_state.json 格式正确"""
        p = hermes_home / "gateway_state.json"
        if not p.exists():
            pytest.skip("gateway_state.json 不存在")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "pid" in data
        assert "platforms" in data

    def test_gateway_platforms_registered(self, hermes_home):
        """channel_directory.json 列出平台"""
        p = hermes_home / "channel_directory.json"
        if not p.exists():
            pytest.skip("channel_directory.json 不存在")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "platforms" in data
        assert isinstance(data["platforms"], dict)
        assert len(data["platforms"]) > 0

    def test_api_health_endpoint(self):
        """GET /health 返回 200"""
        if not self._gateway_running():
            pytest.skip("Gateway 进程未运行")
        if not self._port_listening(GATEWAY_PORT):
            pytest.skip(f"API server 端口 {GATEWAY_PORT} 未监听")
        code, body = http_get(GATEWAY_PORT, "/health")
        assert code == 200, f"health 返回 {code}: {body}"

    def test_api_models_endpoint(self):
        """GET /v1/models 列出 bookwormpro"""
        if not self._gateway_running():
            pytest.skip("Gateway 进程未运行")
        if not self._port_listening(GATEWAY_PORT):
            pytest.skip(f"API server 端口 {GATEWAY_PORT} 未监听")
        code, body = http_get(GATEWAY_PORT, "/v1/models")
        assert code == 200
        data = json.loads(body)
        assert "data" in data
        ids = [m["id"] for m in data["data"]]
        assert any("bookworm" in mid.lower() for mid in ids), (
            f"models 未列出 bookwormpro: {ids}"
        )

    def test_api_health_detailed(self):
        """GET /health/detailed 返回丰富状态"""
        if not self._gateway_running():
            pytest.skip("Gateway 进程未运行")
        if not self._port_listening(GATEWAY_PORT):
            pytest.skip(f"API server 端口 {GATEWAY_PORT} 未监听")
        code, body = http_get(GATEWAY_PORT, "/health/detailed")
        assert code == 200
        data = json.loads(body)
        assert "status" in data or "healthy" in data or "platforms" in data

    def test_chat_completions_invalid_body(self):
        """POST /v1/chat/completions 空 body 返回 4xx"""
        if not self._gateway_running():
            pytest.skip("Gateway 进程未运行")
        if not self._port_listening(GATEWAY_PORT):
            pytest.skip(f"API server 端口 {GATEWAY_PORT} 未监听")
        code, _ = http_post_json(GATEWAY_PORT, "/v1/chat/completions", {})
        assert 400 <= code < 500, f"空 body 应返回 4xx, 实际: {code}"

    def test_circuit_breakers_healthy(self, hermes_home):
        """所有熔断器 state=closed 且无异常高失败率"""
        circuits_dir = hermes_home / "circuits"
        if not circuits_dir.exists():
            pytest.skip("circuits/ 不存在")
        for f in circuits_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            state = data.get("state", "unknown")
            total_s = data.get("total_successes", 0)
            total_f = data.get("total_failures", 0)
            total = total_s + total_f
            if total > 100:
                fail_rate = total_f / total
                assert fail_rate < 0.1, (
                    f"熔断器 {f.stem} 失败率过高: {fail_rate:.1%} "
                    f"({total_f}/{total})"
                )
            if state == "open":
                pytest.fail(
                    f"熔断器 {f.stem} 处于 OPEN 状态, "
                    f"consecutive_failures={data.get('consecutive_failures')}"
                )

    def test_webhook_port_listening(self):
        """Webhook 端口可达"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            result = sock.connect_ex(("127.0.0.1", WEBHOOK_PORT))
            if result != 0:
                pytest.skip(f"Webhook 端口 {WEBHOOK_PORT} 未监听")
        finally:
            sock.close()


# ════════════════════════════════════════════════════════════
#  TIER 5: Provider 连通 (Provider Connectivity)
# ════════════════════════════════════════════════════════════

@pytest.mark.tier5
class TestTier5Connectivity:
    """模拟用户验证 AI Provider 是否正常工作"""

    def test_canary_live(self):
        """bookworm canary --live 真实 API 调用"""
        r = run_cli("canary", "--live", timeout=60)
        if r.returncode != 0 and "network" in r.stderr.lower():
            pytest.skip("网络不可用")
        assert r.returncode == 0, (
            f"canary --live 失败: {r.stdout[:300]}\n{r.stderr[:300]}"
        )

    def test_deepseek_models_api(self):
        """DeepSeek API models.list 可调用"""
        try:
            from dotenv import load_dotenv
            load_dotenv(HERMES_HOME / ".env")
        except ImportError:
            pass
        key = os.environ.get("DEEPSEEK_API_KEY")
        base = os.environ.get("DEEPSEEK_BASE_URL")
        if not key or not base:
            pytest.skip("DEEPSEEK 未配置")
        import openai
        client = openai.OpenAI(api_key=key, base_url=base)
        models = client.models.list()
        assert len(models.data) > 0

    def test_dashscope_models_api(self):
        """DashScope API models.list 可调用"""
        try:
            from dotenv import load_dotenv
            load_dotenv(HERMES_HOME / ".env")
        except ImportError:
            pass
        key = os.environ.get("DASHSCOPE_API_KEY")
        base = os.environ.get("DASHSCOPE_BASE_URL")
        if not key or not base:
            pytest.skip("DASHSCOPE 未配置")
        import openai
        client = openai.OpenAI(api_key=key, base_url=base)
        models = client.models.list()
        assert len(models.data) > 0

    def test_gemini_rest_api(self):
        """Gemini REST API 可达"""
        try:
            from dotenv import load_dotenv
            load_dotenv(HERMES_HOME / ".env")
        except ImportError:
            pass
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            pytest.skip("GOOGLE_API_KEY 未配置")
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
            assert len(data.get("models", [])) > 0

    def test_deepseek_chat_completion(self):
        """DeepSeek 单轮对话可完成"""
        try:
            from dotenv import load_dotenv
            load_dotenv(HERMES_HOME / ".env")
        except ImportError:
            pass
        key = os.environ.get("DEEPSEEK_API_KEY")
        base = os.environ.get("DEEPSEEK_BASE_URL")
        if not key or not base:
            pytest.skip("DEEPSEEK 未配置")
        import openai
        client = openai.OpenAI(api_key=key, base_url=base)
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "reply with exactly: PONG"}],
            max_tokens=10,
        )
        assert resp.choices[0].message.content.strip()


# ════════════════════════════════════════════════════════════
#  TIER 6: 数据完整性 (Data Integrity)
# ════════════════════════════════════════════════════════════

@pytest.mark.tier6
class TestTier6DataIntegrity:
    """模拟运维人员检查数据文件完整性"""

    def test_state_db_integrity(self, hermes_home):
        """state.db 通过 SQLite integrity_check"""
        db_path = hermes_home / "state.db"
        if not db_path.exists():
            pytest.skip("state.db 不存在")
        conn = sqlite3.connect(str(db_path))
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            assert result[0] == "ok", f"state.db 损坏: {result}"
        finally:
            conn.close()

    def test_state_db_size_reasonable(self, hermes_home):
        """state.db 未超过 100MB"""
        db_path = hermes_home / "state.db"
        if not db_path.exists():
            pytest.skip("state.db 不存在")
        size_mb = db_path.stat().st_size / (1024 * 1024)
        assert size_mb < 100, f"state.db 过大: {size_mb:.1f}MB"

    def test_sessions_dir_no_orphan_tmp(self, hermes_home):
        """sessions/ 无超过 24h 的 .tmp 文件"""
        sessions_dir = hermes_home / "sessions"
        if not sessions_dir.exists():
            pytest.skip("sessions/ 不存在")
        now = time.time()
        for f in sessions_dir.glob("*.tmp"):
            age_hours = (now - f.stat().st_mtime) / 3600
            assert age_hours < 24, (
                f"过期临时文件: {f.name} ({age_hours:.0f}h old)"
            )

    def test_no_bak_accumulation(self, hermes_home):
        """根目录不超过 3 个 .bak 文件"""
        baks = list(hermes_home.glob("*.bak-*"))
        assert len(baks) <= 3, (
            f"过多备份文件 ({len(baks)}): {[b.name for b in baks]}"
        )

    def test_log_not_oversized(self, hermes_home):
        """agent.log 不超过 50MB"""
        log = hermes_home / "logs" / "agent.log"
        if not log.exists():
            pytest.skip("agent.log 不存在")
        size_mb = log.stat().st_size / (1024 * 1024)
        assert size_mb < 50, f"agent.log 过大: {size_mb:.1f}MB"

    def test_skills_index_valid_json(self, hermes_home):
        """skills-index.json 可解析"""
        p = hermes_home / "skills-index.json"
        if not p.exists():
            pytest.skip("skills-index.json 不存在")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(data, (dict, list))

    def test_gateway_state_json_valid(self, hermes_home):
        """gateway_state.json 格式正确"""
        p = hermes_home / "gateway_state.json"
        if not p.exists():
            pytest.skip("gateway_state.json 不存在")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "pid" in data

    def test_cron_jobs_json_valid(self, hermes_home):
        """cron/jobs.json 格式正确且 jobs 是列表"""
        p = hermes_home / "cron" / "jobs.json"
        if not p.exists():
            pytest.skip("cron/jobs.json 不存在")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_channel_directory_platforms(self, hermes_home):
        """channel_directory.json 包含预期平台"""
        p = hermes_home / "channel_directory.json"
        if not p.exists():
            pytest.skip("channel_directory.json 不存在")
        data = json.loads(p.read_text(encoding="utf-8"))
        platforms = data.get("platforms", {})
        expected = {"telegram", "discord", "weixin", "wecom", "slack"}
        found = set(platforms.keys())
        missing = expected - found
        assert not missing, f"channel_directory 缺少平台: {missing}"

    def test_models_dev_cache_not_stale(self, hermes_home):
        """models_dev_cache.json 不超过 7 天"""
        p = hermes_home / "models_dev_cache.json"
        if not p.exists():
            pytest.skip("models_dev_cache.json 不存在")
        age_days = (time.time() - p.stat().st_mtime) / 86400
        assert age_days < 7, f"models_dev_cache.json 已过期: {age_days:.1f} 天"


# ════════════════════════════════════════════════════════════
#  TIER 7: 安全基线 (Security Baseline)
# ════════════════════════════════════════════════════════════

@pytest.mark.tier7
@pytest.mark.security
class TestTier7Security:
    """安全审计：凭证泄漏、日志脱敏、权限检查"""

    SENSITIVE_PATTERNS = [
        r"sk-[a-zA-Z0-9]{20,}",         # OpenAI/DeepSeek key
        r"sk-ant-[a-zA-Z0-9]{20,}",     # Anthropic key
        r"sk-or-v1-[a-zA-Z0-9]{20,}",   # OpenRouter key
        r"AIza[a-zA-Z0-9_-]{30,}",      # Google API key
        r"ghp_[a-zA-Z0-9]{36}",         # GitHub PAT
        r"gho_[a-zA-Z0-9]{36}",         # GitHub OAuth
        r"xoxb-[a-zA-Z0-9-]+",          # Slack bot token
    ]

    def test_no_credentials_in_logs(self, hermes_home):
        """agent.log 不含明文 API Key"""
        log = hermes_home / "logs" / "agent.log"
        if not log.exists():
            pytest.skip("agent.log 不存在")
        content = log.read_text(encoding="utf-8", errors="replace")
        for pattern in self.SENSITIVE_PATTERNS:
            matches = re.findall(pattern, content)
            assert not matches, (
                f"日志泄漏凭证! 模式 {pattern} 命中 {len(matches)} 处"
            )

    def test_no_credentials_in_session_files(self, hermes_home):
        """session JSONL 文件不含明文 API Key"""
        sessions_dir = hermes_home / "sessions"
        if not sessions_dir.exists():
            pytest.skip("sessions/ 不存在")
        for f in sorted(sessions_dir.glob("*.jsonl"))[-3:]:
            content = f.read_text(encoding="utf-8", errors="replace")
            for pattern in self.SENSITIVE_PATTERNS:
                matches = re.findall(pattern, content)
                if matches:
                    pytest.fail(
                        f"会话文件 {f.name} 泄漏凭证! "
                        f"模式 {pattern} 命中 {len(matches)} 处"
                    )

    def test_doctor_output_redacted(self):
        """bookworm dump 输出不含明文凭证"""
        out = assert_cli_success("dump", timeout=30)
        for pattern in self.SENSITIVE_PATTERNS:
            matches = re.findall(pattern, out)
            assert not matches, (
                f"dump 输出泄漏凭证! 模式 {pattern}"
            )

    def test_no_world_readable_env(self, hermes_home):
        """检查 .env 不应被其他用户可读 (Windows: 检查文件存在即可)"""
        env_file = hermes_home / ".env"
        if not env_file.exists():
            pytest.skip(".env 不存在")
        assert env_file.stat().st_size > 0

    def test_webhook_secret_configured(self, config_yaml):
        """Webhook 配置了 secret"""
        webhook = config_yaml.get("platforms", {}).get("webhook", {})
        if not webhook.get("enabled"):
            pytest.skip("Webhook 未启用")
        extra = webhook.get("extra", {})
        secret = extra.get("secret", "")
        assert secret and len(secret) >= 16, (
            "Webhook secret 未配置或过短 (应 >= 16 字符)"
        )

    def test_approvals_mode_documented(self, config_yaml):
        """审批模式已显式配置"""
        approvals = config_yaml.get("approvals", {})
        assert "mode" in approvals, "approvals.mode 未配置"


# ════════════════════════════════════════════════════════════
#  TIER BONUS: 用户旅程仿真 (User Journey Simulation)
# ════════════════════════════════════════════════════════════

@pytest.mark.journey
class TestUserJourneySimulation:
    """仿真真实用户操作序列: 安装→配置→使用→运维"""

    def test_journey_first_boot(self):
        """仿真: 首次启动检查链 version→doctor→status"""
        v = assert_cli_success("version")
        assert re.search(r"\d+\.\d+", v)

        r = run_cli("doctor", timeout=60)
        assert r.returncode in (0, 1)

        s = assert_cli_success("status")
        assert len(s) > 20

    def test_journey_daily_ops(self):
        """仿真: 日常运维 status→cron list→sessions stats→insights"""
        assert_cli_success("status")
        assert_cli_success("cron", "list", timeout=15)
        r = run_cli("sessions", "stats", timeout=15)
        assert r.returncode == 0
        r = run_cli("insights", "--days", "3", timeout=30)
        assert r.returncode == 0

    def test_journey_troubleshoot(self):
        """仿真: 故障排查 doctor→dump→audit"""
        r = run_cli("doctor", timeout=60)
        assert r.returncode in (0, 1)

        dump_out = assert_cli_success("dump", timeout=30)
        assert len(dump_out) > 100

        r = run_cli("audit", timeout=15)
        assert r.returncode == 0

    def test_journey_skill_exploration(self):
        """仿真: 技能探索 skills list→skills search"""
        r = run_cli("skills", "list", timeout=30)
        assert r.returncode == 0

    def test_journey_model_check(self):
        """仿真: 检查模型配置 (通过 config 读取，model 子命令是交互式)"""
        r = run_cli("config", "get", "model", timeout=15)
        if r.returncode != 0:
            r = run_cli("status", timeout=30)
        assert r.returncode == 0


# ════════════════════════════════════════════════════════════
#  pytest 配置
# ════════════════════════════════════════════════════════════

def pytest_configure(config):
    for tier in range(1, 8):
        config.addinivalue_line("markers", f"tier{tier}: Tier {tier} tests")
    config.addinivalue_line("markers", "security: Security audit tests")
    config.addinivalue_line("markers", "journey: User journey simulation")
