"""
SMR Hook — 智能模型路由 (Smart Model Routing) 非侵入式主流程集成

设计原则（对齐 routing/bwr_hook.py）:
  - 单一入口类 SMRHook，导入失败/任何异常均静默降级，绝不影响主对话流程
  - SMR 核心逻辑位于 ~/.bookwormpro/smr/（用户态，与代码库解耦），通过 sys.path 惰性注入导入
  - 依据 config.yaml 的 custom_providers 建立 model -> {base_url, api_key, provider} 凭证映射
  - 惰性阈值：同一 task_type 不重复切换；分数需超过当前模型一定优势才切换，避免抖动破坏 prompt 缓存

用法（在 run_agent.py 的 run_conversation 中）:
    from routing.smr_hook import SMRHook
    _smr = SMRHook.get(agent=self)              # 每个 agent 实例复用同一 hook
    _smr.route_and_switch(self, user_message)   # 评估并（可能）切换 self.model

会话内开关（仅影响当前 CLI 会话，新开 CLI 不受影响）:
    - 环境变量 SMR_DISABLE=1 → 进程级全局禁用
    - config.yaml smr.enabled: false → 配置级禁用
    - 语言指令 "关闭模型切换" / "恢复模型切换" → 运行时切换当前会话状态
      · 短语须为精确子串匹配，勿加夹字（如“暂停模型自动切换”中“模型”“切换”被“自动”隔开，
        不构成连续子串“模型切换”，将不会命中，引擎不会真正暂停）。正确写法：关闭模型切换。
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 路径常量 ──────────────────────────────────────────────────
_SMR_DIR = Path.home() / ".bookwormpro" / "smr"
_CONFIG_PATH = Path.home() / ".bookwormpro" / "config.yaml"

# ── 惰性阈值 ──────────────────────────────────────────────────
# 候选模型得分需比当前模型高出此值才触发切换，避免频繁抖动破坏 prompt 缓存
_SWITCH_MARGIN = 0.03

# ── 会话内语言指令 ────────────────────────────────────────────
_DISABLE_PHRASES = ("关闭模型切换", "停止模型切换", "禁用模型切换", "disable model switch")
_ENABLE_PHRASES = ("恢复模型切换", "开启模型切换", "启用模型切换", "enable model switch")


def _import_smr():
    """惰性导入 SMR 核心模块。失败返回 None（静默降级）。"""
    import sys

    smr_path = str(_SMR_DIR)
    if _SMR_DIR.exists() and smr_path not in sys.path:
        sys.path.insert(0, smr_path)
    try:
        import smr_router  # type: ignore
        import smr_feedback  # type: ignore

        return smr_router, smr_feedback
    except Exception as exc:  # pragma: no cover - 环境相关
        logger.debug("SMR 模块导入失败，路由禁用: %s", exc)
        return None


class SMRHook:
    """SMR 主流程桥接。每个 AIAgent 实例持有一个（通过 SMRHook.get 复用）。"""

    # 进程级全局默认开关（config + env 决定，只读一次）
    _process_enabled: Optional[bool] = None

    def __init__(self, agent: Any = None):
        self.agent = agent
        self._router = None
        self._feedback = None
        self._model_map: Optional[dict] = None
        # 会话内开关：None 表示跟随进程级默认；True/False 表示本会话显式覆盖
        self._session_override: Optional[bool] = None
        # 惰性状态：上次切换到的 task_type / model，用于避免同类重复切换
        self._last_task_type: Optional[str] = None
        self._last_routed_model: Optional[str] = None
        # 最近一次路由决策（供反馈闭环回填）
        self.last_decision: Optional[dict] = None

    # ── 实例复用 ──────────────────────────────────────────────
    @classmethod
    def get(cls, agent: Any) -> "SMRHook":
        """获取 / 创建绑定到该 agent 的 SMRHook 实例。"""
        existing = getattr(agent, "_smr_hook", None)
        if isinstance(existing, cls):
            return existing
        hook = cls(agent=agent)
        try:
            agent._smr_hook = hook
        except Exception:
            pass
        return hook

    # ── 进程级开关（config + env）─────────────────────────────
    @classmethod
    def _resolve_process_enabled(cls) -> bool:
        if cls._process_enabled is not None:
            return cls._process_enabled

        enabled = True
        # 环境变量兜底：SMR_DISABLE=1 紧急关闭
        if os.environ.get("SMR_DISABLE", "").strip() in ("1", "true", "yes", "on"):
            enabled = False
        else:
            # config.yaml smr.enabled（默认 true）
            try:
                import yaml  # type: ignore

                if _CONFIG_PATH.exists():
                    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                    smr_cfg = cfg.get("smr", {})
                    if isinstance(smr_cfg, dict) and smr_cfg.get("enabled") is False:
                        enabled = False
            except Exception:
                pass  # 读取失败按默认开启

        cls._process_enabled = enabled
        return enabled

    @staticmethod
    def _read_config_margin() -> float:
        """读取 config.yaml smr.switch_margin（默认 _SWITCH_MARGIN）。"""
        try:
            import yaml  # type: ignore

            if _CONFIG_PATH.exists():
                with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                smr_cfg = cfg.get("smr", {})
                if isinstance(smr_cfg, dict):
                    m = smr_cfg.get("switch_margin")
                    if isinstance(m, (int, float)) and 0 <= m <= 1:
                        return float(m)
        except Exception:
            pass
        return _SWITCH_MARGIN

    def _is_enabled(self) -> bool:
        """当前会话是否启用 SMR：会话覆盖优先于进程级默认。"""
        if self._session_override is not None:
            return self._session_override
        return self._resolve_process_enabled()

    # ── 会话内语言指令热切换 ──────────────────────────────────
    def maybe_toggle(self, user_message: str) -> Optional[str]:
        """
        检测会话内开关指令。命中返回提示语（供调用方展示），否则返回 None。
        仅匹配"整条消息基本就是该指令"的场景，避免误伤正常对话。
        """
        if not isinstance(user_message, str):
            return None
        msg = user_message.strip().lower()
        if len(msg) > 20:  # 指令很短，长消息不视为开关指令
            return None
        for p in _DISABLE_PHRASES:
            if p in msg:
                self._session_override = False
                _cur = getattr(getattr(self, "agent", None), "model", None)
                _lock = f"，当前会话固定使用 {_cur}" if _cur else ""
                return f"已在当前会话关闭 SMR 模型自动切换{_lock}（新开 CLI 不受影响）。"
        for p in _ENABLE_PHRASES:
            if p in msg:
                self._session_override = True
                return "已在当前会话恢复 SMR 模型自动切换。"
        return None

    # ── config 模型映射 ───────────────────────────────────────
    def _load_model_map(self) -> dict:
        """
        从 config.yaml custom_providers 构建 model -> 凭证映射。
        {model_id: {"base_url", "api_key", "provider", "api_mode"}}
        """
        if self._model_map is not None:
            return self._model_map

        model_map: dict = {}
        try:
            import yaml  # type: ignore

            if _CONFIG_PATH.exists():
                with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                for entry in cfg.get("custom_providers", []) or []:
                    if not isinstance(entry, dict):
                        continue
                    model_id = entry.get("model")
                    if not model_id:
                        continue
                    model_map[model_id] = {
                        "base_url": entry.get("base_url", ""),
                        "api_key": entry.get("api_key", ""),
                        "provider": entry.get("provider_key") or entry.get("name", ""),
                        "api_mode": entry.get("api_mode", ""),
                    }
        except Exception as exc:
            logger.debug("加载 config 模型映射失败: %s", exc)

        self._model_map = model_map
        return model_map

    # ── 核心：路由 + 切换 ─────────────────────────────────────
    def route_and_switch(self, agent: Any, user_message: str) -> Optional[dict]:
        """
        评估当前消息的最优模型，必要时对 agent 执行 switch_model。

        返回切换信息 dict（已切换时）或 None（未切换/禁用/降级）。
        任何异常都会被吞掉，绝不影响主对话。
        """
        try:
            if not self._is_enabled():
                return None
            if not user_message or not str(user_message).strip():
                return None

            # 惰性加载 SMR 模块
            if self._router is None:
                mods = _import_smr()
                if mods is None:
                    return None
                self._router, self._feedback = mods

            # 1. 路由决策
            decision = self._router.route(str(user_message))
            self.last_decision = decision.to_dict()

            target_model = decision.model
            current_model = getattr(agent, "model", "") or ""

            # 2. 已经是目标模型 → 无需切换
            if target_model == current_model:
                self._last_task_type = decision.task_type
                self._last_routed_model = target_model
                return None

            # 3. 惰性阈值：同一 task_type 且上次已路由过 → 不重复切换
            if (
                decision.task_type == self._last_task_type
                and self._last_routed_model == target_model
            ):
                return None

            # 4. 分数优势阈值：候选须显著优于当前模型才切换
            if not self._exceeds_margin(decision, current_model):
                self._last_task_type = decision.task_type
                return None

            # 5. 目标模型必须在 config 中（有可用凭证）
            model_map = self._load_model_map()
            creds = model_map.get(target_model)
            if not creds:
                logger.debug("SMR 目标模型 %s 不在 config，跳过切换", target_model)
                return None

            # 6. 执行切换
            agent.switch_model(
                new_model=target_model,
                new_provider=creds["provider"],
                api_key=creds["api_key"],
                base_url=creds["base_url"],
                api_mode=creds["api_mode"],
            )
            self._last_task_type = decision.task_type
            self._last_routed_model = target_model

            info = {
                "from": current_model,
                "to": target_model,
                "task_type": decision.task_type,
                "score": decision.score,
                "reason": decision.reason,
                "session_id": decision.session_id,
            }
            logger.info(
                "SMR 已切换模型 %s -> %s (task=%s score=%.4f)",
                current_model, target_model, decision.task_type, decision.score,
            )
            return info

        except Exception as exc:  # 绝不影响主流程
            logger.debug("SMR route_and_switch 异常（已降级）: %s", exc)
            return None

    def _exceeds_margin(self, decision: Any, current_model: str) -> bool:
        """候选得分是否比当前模型在同任务下的得分高出 _SWITCH_MARGIN。"""
        try:
            profiles = getattr(self._router, "MODEL_PROFILES", {})
            cur = profiles.get(current_model)
            if not cur:
                # 当前模型不在 profile（未知）→ 允许切到已知的更优模型
                return True
            # 用与 router 同源的公式近似估算当前模型分数（忽略延迟归一化差异）
            q = float(cur.get("quality", 0.5))
            c = float(cur.get("cost_norm", 0.5))
            aff = float(cur.get("task_affinity", {}).get(decision.task_type, 0.0))
            cur_score = q * 0.6 + (1 - c) * 0.3 + aff  # 省略 latency 项，做保守估计
            return (decision.score - cur_score) >= self._read_config_margin()
        except Exception:
            return True

    # ── 反馈闭环 ──────────────────────────────────────────────
    def record_turn_feedback(self, result: dict) -> None:
        """
        turn 结束时根据 result 推导 reward 类型并记录反馈。
        result 来自 run_conversation 返回的 dict。
        """
        try:
            if self._feedback is None or self.last_decision is None:
                return

            model = self.last_decision.get("model")
            task_type = self.last_decision.get("task_type")
            session_id = self.last_decision.get("session_id")
            if not (model and task_type and session_id):
                return

            RewardType = self._feedback.RewardType
            completed = result.get("completed", False)
            interrupted = result.get("interrupted", False)
            api_calls = result.get("api_calls", 0)
            cost_status = str(result.get("cost_status", "") or "").lower()

            # 推导 reward 类型
            if interrupted:
                reward = RewardType.API_ERROR_TIMEOUT
            elif not completed:
                reward = RewardType.SELF_AUDIT_ERROR
            elif api_calls and api_calls > 6:
                # 多轮工具调用后完成 → 视为有重试
                reward = RewardType.TASK_COMPLETED_WITH_RETRY
            else:
                reward = RewardType.TASK_COMPLETED_CLEAN

            self._feedback.record_feedback(
                session_id=session_id,
                model=model,
                task_type=task_type,
                reward_type=reward,
                extra={"api_calls": api_calls, "cost_status": cost_status},
            )
            logger.debug("SMR 反馈已记录: %s / %s / %s", model, task_type, reward.value)
        except Exception as exc:
            logger.debug("SMR record_turn_feedback 异常（已降级）: %s", exc)
