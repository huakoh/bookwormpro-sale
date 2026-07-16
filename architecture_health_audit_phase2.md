# BookwormPRO Architecture Health Audit Report
## Phase 2 — Deep Architecture Review (module coupling / dependency chains / technical debt / extensibility / architectural risk)

**审查日期**: 2026-05-06
**代码库**: C:\Users\leesu\BookwormPRO\
**审查范围**: agent/ (65 py), gateway/ (平台适配器), run_agent.py, cli.py, bwm_cli/
**方法论**: architect-expert + Phase 1 发现基线 (auxiliary_client 15 WARNING, credential pool 43 WARNING, circuit_breakers 集成缺口)

---

# ============================================================================
#  CRITICAL — 必须在上线前或下次主要版本中修复
# ============================================================================

## [C-1] run_agent.py: 13,155 行 God Class — 核心架构风险
**文件**: C:\Users\leesu\BookwormPRO\run_agent.py
**严重程度**: CRITICAL
**架构风险**:
- AIAgent 类接收 ~60 个参数（凭证、路由、回调、会话上下文、预算、凭证池等），违反单一职责原则。
- 将对话循环、工具编排、模型路由、显示格式化、上下文压缩、成本跟踪、错误处理、prompt 构建全部塞入一个文件。
- 修改任何子系统（例如添加新的 LLM 提供商）都需要触碰此文件 —— 爆炸半径极大。
- 所有 agent/ 模块最终都汇入此文件（65 个模块中 20+ 个被导入），形成中心辐射式依赖图，中心节点是阻塞点。
- 由于持续增长，无法进行单元测试。
**重构建议**:
1. 将 AIAgent 拆分为组合服务：`ConversationLoop`、`ToolOrchestrator`、`ProviderRouter`、`ResponseHandler`、`ContextManager`
2. 将 provider-specific 逻辑提取到策略类中（已部分完成，有 codex_responses_adapter 等，但主循环仍然知晓所有提供商的细节）。
3. 将 `build_*_prompt` 函数移到专用的 PromptEngine 中。
4. 使用依赖注入而非 ~60 个 __init__ 参数。
**预估工作量**: 15-25 人天 | **风险**: 每次变更都可能引入回归 | **优先级**: 下一个主要发布版本之前

## [C-2] circuit_breaker 存在但在辅助路径中未使用 — 级联故障风险
**文件**: 
  - C:\Users\leesu\BookwormPRO\agent\circuit_breaker.py (660 行 —— 良好实现)
  - C:\Users\leesu\BookwormPRO\agent\auxiliary_client.py (6,823 行 —— 零 circuit_breaker 引用)
  - C:\Users\leesu\BookwormPRO\agent\aux_vision.py (8,709 行 —— 零 circuit_breaker 引用)
**严重程度**: CRITICAL
**架构风险**:
- circuit_breaker.py 存在且设计合理（CLOSED/OPEN/HALF_OPEN，文件共享状态），但仅由 run_agent.py（主对话循环）和 provider_health.py 使用。
- auxiliary_client.py 实现了自己的 7 级回退链（OpenRouter → BookwormPRO → 自定义 → Codex → Anthropic → 直接 API 密钥 → 无），但没有熔断保护。
- 这意味着辅助任务（上下文压缩、网页提取、视觉分析、会话搜索）如果提供商降级，将逐个尝试每个提供商，无限次失败，没有熔断。
- aux_vision.py 存在同样的缺口（8,709 行，零 circuit_breaker 导入）。
- 在 402/429 风暴期间，辅助客户端可能通过回退链触发过多的故障，在主循环自身的 circuit_breaker 跳闸后很久才停止。
**重构建议**:
1. 在每个 `_try_*()` 调用之前，向 auxiliary_client 的 `_resolve_auto()` 和 `call_llm()` 注入 `circuit_breaker.allow()` 检查。
2. 在成功/失败时添加 `report_success`/`report_failure` 调用。
3. 当 circuit_breaker 跳闸时，跳过该提供商并进入链中的下一个。
4. 由于 auxiliary_client 按提供商而非每个提供商进行重试，因此需要为辅助路径提供特定于提供商的熔断键（例如 `aux_openrouter`、`aux_codex`）。
**预估工作量**: 3-5 人天 | **风险**: 高 —— 辅助任务在提供商中断期间导致级联故障 | **优先级**: 本月

## [C-3] credential_pool.py ↔ bwm_cli.auth 双向耦合 — 层级违规
**文件**:
  - C:\Users\leesu\BookwormPRO\agent\credential_pool.py (1,480 行)
  - C:\Users\leesu\BookwormPRO\bwm_cli\auth.py (3,200+ 行，由 agent/ 反向导入)
**严重程度**: CRITICAL
**架构风险**:
- credential_pool.py（在 agent/ 层）从 bwm_cli.auth（CLI 层）导入 15 个私有符号：`CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS`、`DEFAULT_AGENT_KEY_MIN_TTL_SECONDS`、`PROVIDER_REGISTRY`、`_auth_store_lock`、`_codex_access_token_is_expiring`、`_decode_jwt_claims`、`_load_auth_store`、`_load_provider_state`、`_resolve_kimi_base_url`、`_resolve_zai_base_url`、`_save_auth_store`、`_save_provider_state`、`read_credential_pool`、`write_credential_pool`。
- bwm_cli.auth 同时从 agent.credential_pool 导入 `load_pool` —— 创建双向依赖。
- agent/ 层知道 CLI 层的内部存储细节（auth.json 格式、_auth_store_lock、提供商状态持久化）。
- 无法在没有 CLI 层的情况下独立测试 agent 层。
- 凭证池使用来源抑制、提供商注册表和 CLI 特定的提供商解析逻辑进行播种 —— 这些关注点应该被反转。
**重构建议**:
1. 定义一个 `CredentialStore` 抽象接口（协议）在 agent/ 层。
2. 将 auth.json 读/写逻辑移到实现该协议的 bwm_cli 中。
3. 通过依赖注入将存储实现注入 credential_pool。
4. 将 `_resolve_kimi_base_url`、`_resolve_zai_base_url` 等提供商解析函数移到共享常量/工具模块中。
5. 使用抽象层打破双向导入循环。
**预估工作量**: 5-8 人天 | **风险**: 高 —— 更改 auth 存储格式会破坏两个层 | **优先级**: 下一个主要发布版本之前

# ============================================================================
#  HIGH — 应在下个 sprint 中修复
# ============================================================================

## [H-1] gateway/run.py: 11,382 行单体 — 平台网关不可扩展
**文件**: C:\Users\leesu\BookwormPRO\gateway\run.py
**严重程度**: HIGH
**架构风险**:
- 单体模块混合了：SSL 证书检测、.env 加载、config.yaml 桥接、终端环境变量桥接、辅助配置桥接、代理缓存管理、会话到期监视、平台适配器初始化、请求路由、webhook 设置、OAuth 回调、健康检查端点和 Docker 卷解析。
- 添加新的消息平台需要理解 ~300 行的配置桥接逻辑。
- config.yaml → 环境变量桥接模式被逐字重复用于 terminal、auxiliary.vision、auxiliary.web_extract 和 auxiliary.approval —— 应该是一个泛型函数。
- _AGENT_CACHE_MAX_SIZE、_AGENT_CACHE_IDLE_TTL_SECS 是硬编码常量，应可配置。
- 系统路径操作（`sys.path.insert(0, ...)`）在模块顶层执行 —— 这是脆弱的。
**重构建议**:
1. 将配置桥接提取到 `gateway/config_bridge.py` 中。
2. 将平台生命周期管理移到 `gateway/platform_runner.py` 中。
3. 将 SSL 检测移到 `gateway/ssl_detect.py` 中（模块级）。
4. 将代理缓存管理移到 `gateway/agent_cache.py` 中。
5. 将 env 加载移到引导模块中，在任何导入之前运行。
6. 从 config.yaml 使 _AGENT_CACHE_* 可配置。
**预估工作量**: 4-6 人天 | **风险**: 中等 —— 更改影响所有平台适配器 | **优先级**: 下个 sprint

## [H-2] auxiliary_client.py: 6,823 行，7 个提供商适配器合并在一个文件中
**文件**: C:\Users\leesu\BookwormPRO\agent\auxiliary_client.py
**严重程度**: HIGH
**架构风险**:
- 一个文件包含：Codex 适配器（_CodexCompletionsAdapter）、Anthropic 适配器（_AnthropicCompletionsAdapter）、它们各自的异步版本、Gemini 本地客户端路由、BookwormPRO Portal 集成、OpenRouter 集成、自定义端点解析、Kimi/Moonshot 温度管理、Cloudflare 头构建、提供商别名规范化、付款回退逻辑和 7 级提供商解析链。
- 50 个函数/类在一个文件中 —— 无法仅理解一个提供商适配器而不浏览其他 6 个。
- 使用 20+ 惰性导入（在函数内部导入）来避免循环依赖 —— 这是模块边界不良的症状。
- 如果只更改一个提供商（例如 Anthropic），没有测试边界可言。
- aux_vision.py（8,709 行）以几乎相同的结构反映了此模式 —— 大量代码重复。
**重构建议**:
1. 将每个提供商适配器提取到 `agent/auxiliary/providers/{codex,anthropic,gemini,openrouter,nous,custom,api_key}.py` 中。
2. 创建一个 `agent/auxiliary/resolver.py`，其中包含提供商链逻辑。
3. 将共享工具（_normalize_aux_provider、_is_payment_error、_is_auth_error）提取到 `agent/auxiliary/common.py` 中。
4. 从 aux_vision.py 中消除重复 —— 视觉辅助工具应该重用相同的提供商适配器，并带有特定于视觉的覆盖。
5. 将惰性导入转换为顶层导入（一旦打破循环）。
**预估工作量**: 5-7 人天 | **风险**: 中等 —— 涉及大量代码移动 | **优先级**: 下个 sprint

## [H-3] 无架构分层 —— 扁平 agent/ 包结构
**文件**: C:\Users\leesu\BookwormPRO\agent/ (65 个文件, 0 个子目录除了 transports/)
**严重程度**: HIGH
**架构风险**:
- 所有 65 个 agent/ 模块存在于一个扁平命名空间中，关注点没有分离。
- transports/ 子包存在（好的），但这是唯一的逻辑分组。
- 按关注点分类的当前模块：
  - **提供商适配器** (9): anthropic_adapter, bedrock_adapter, codex_responses_adapter, gemini_native_adapter, gemini_schema, gemini_cloudcode_adapter, copilot_acp_client, google_code_assist, moonshot_schema
  - **凭证/认证** (3): credential_pool, credential_sources, google_oauth
  - **上下文/内存** (5): context_compressor, context_engine, context_references, memory_manager, memory_provider, memory_temporal, memory_integration
  - **成本/使用量** (5): cost_tracker, account_usage, usage_pricing, rate_limit_tracker, nous_rate_guard
  - **健康/弹性** (6): circuit_breaker, provider_health, health, error_classifier, retry_utils, response_validator
  - **辅助客户端** (3): auxiliary_client, aux_clients, aux_vision
  - **杂项** (34): 其余所有内容
- 新开发人员需要理解 65 个模块，每个模块都可能导入其他任何模块。
- 没有领域边界 —— 任何模块都可以导入任何其他模块（并且许多确实如此）。
**重构建议**:
1. 重组为逻辑子包：
   ```
   agent/
     providers/       # 所有提供商适配器
     credentials/     # credential_pool, credential_sources, google_oauth
     context/         # context_compressor, context_engine, memory_*
     cost/            # cost_tracker, account_usage, usage_pricing
     resilience/      # circuit_breaker, provider_health, retry_utils, error_classifier
     auxiliary/       # auxiliary_client, aux_vision, aux_clients
     prompt/          # prompt_builder, prompt_caching
     skills/          # skill_commands, skill_preprocessing, skill_utils, skill_usage_tracker
   ```
2. 对每个子包强制实施 `__init__.py` 公共 API（通过代码审查）。
3. 将跨包子包导入限制为仅通过公共 API。
**预估工作量**: 3-4 人天（主要是文件移动 + 导入更新）| **风险**: 低（机械重构）| **优先级**: 下个 sprint

## [H-4] cost_tracker 缺少与 circuit_breaker 的集成 —— 无成本门控
**文件**:
  - C:\Users\leesu\BookwormPRO\agent\cost_tracker.py (373 行)
  - C:\Users\leesu\BookwormPRO\agent\circuit_breaker.py (660 行)
**严重程度**: HIGH
**架构风险**:
- cost_tracker.py 有每日 5/10 美元的阈值警告，但仅记录警告 —— 它不会阻止进一步的 API 调用。
- circuit_breaker.py 跳闸是基于连续的故障，而不是基于积累的成本。
- 可能发生的情况：一个行为异常的代理循环在一个会话中花费 50 美元以上，因为没有断路器监控成本。
- 每日聚合是追加到 JSON 文件，没有原子保证 —— 如果两个进程同时写入，`daily.json` 可能损坏。
**重构建议**:
1. 向 circuit_breaker 添加 `CostCircuitBreaker` 子类，在每日成本超过可配置限制时跳闸。
2. 在 `record_cost()` 中，检查每日运行总数；如果超过限制，调用 `circuit_breaker.report_failure(provider, reason="cost_limit")`。
3. 对 `daily.json` 更新使用原子写入（tmpfile + os.replace）。
4. 为成本断路器添加与现有文件共享模式相同的 provider-health 集成。
**预估工作量**: 2-3 人天 | **风险**: 中等 —— 财务风险 | **优先级**: 本月

# ============================================================================
#  MEDIUM — 应在当前季度内修复
# ============================================================================

## [M-1] auxiliary_client 中的惰性导入隐藏依赖关系并阻止静态分析
**文件**: C:\Users\leesu\BookwormPRO\agent\auxiliary_client.py (20+ 惰性导入)
**严重程度**: MEDIUM
**架构风险**:
- 在函数内部有 20+ 个 `from agent.xxx import ...` 的实例 —— 静态分析工具（mypy、pylint、import-linter）无法看到这些依赖关系。
- 循环依赖通过惰性导入解决，而不是通过适当的接口隔离解决。
- 示例：`from agent.anthropic_adapter import build_anthropic_kwargs` 在第 1,217 行（在函数内部），而不是在顶部。
- 如果 anthropic_adapter 更改其签名，auxiliary_client 仍然会在运行时导入并崩溃，没有类型检查警告。
- aux_vision.py 有相同的模式，具有相同的导入（更多重复）。
**重构建议**:
1. 将提供商适配器提取到子包后（参见 H-2），在顶层导入它们。
2. 对于真正的条件依赖（例如仅限 Windows 的），使用 `TYPE_CHECKING` 块或显式接口。
3. 添加 `import-linter` 合同以强制执行：`agent/auxiliary/` 可以导入 `agent/providers/`，但不能反向导入。
**预估工作量**: 1-2 人天（提取到子包后）| **风险**: 低 | **优先级**: 本季度

## [M-2] credential_pool.py 混合业务逻辑与持久化
**文件**: C:\Users\leesu\BookwormPRO\agent\credential_pool.py
**严重程度**: MEDIUM
**架构风险**:
- CredentialPool 类（第 363 行）直接调用 `write_credential_pool()` 和 `read_credential_pool()`（来自 bwm_cli.auth 的私有函数）。
- OAuth 刷新逻辑（`_refresh_entry`）、令牌同步（`_sync_nous_entry_from_auth_store`）和持久化（`_persist`）全部交织在同一个类中。
- `_sync_device_code_entry_to_auth_store` 方法知道 auth.json 的内部结构（provider keys、token dicts）。
- 添加新的凭证存储后端（例如数据库）需要重写整个类。
- OAuth 刷新与持久化耦合 —— 无法单独测试刷新而不需要文件系统。
**重构建议**:
1. 将持久化提取到 `CredentialStore` 协议（参见 C-3）。
2. 将 OAuth 刷新移到 `CredentialRefresher` 服务中。
3. 使 `CredentialPool` 成为纯粹的内存选择/耗尽/租约管理器。
4. 在测试中使用依赖注入模拟存储。
**预估工作量**: 2-3 人天 | **风险**: 低 | **优先级**: 本季度

## [M-3] provider_health.py 和 health.py 职责重叠
**文件**:
  - C:\Users\leesu\BookwormPRO\agent\provider_health.py (约 950 行)
  - C:\Users\leesu\BookwormPRO\agent\health.py (284 行)
**严重程度**: MEDIUM
**架构风险**:
- `health.py::check_health()` 导入 `provider_health.probe_all_providers()` 用于提供商检查，但也有自己的回退提供商检查。
- `provider_health.py` 在 provider_health_probe.py 和 commands.py 中被独立使用。
- 两个模块都实现了提供商状态检查，逻辑重复。
- `health.py` 是较新的抽象（ComponentStatus 数据类，分组件报告），但 `provider_health.py` 有自己的结果格式。
- 不清楚哪个是提供商健康检查的规范接口。
**重构建议**:
1. 将 provider_health.py 设为 provider-specific 健康探针的唯一来源。
2. 让 health.py 仅作为编排器，将 provider_health 作为组件调用。
3. 标准化返回值以使用 ComponentStatus 数据类。
4. 移除 health.py 中的回退提供商检查（仅使用 provider_health 或返回 UNKNOWN）。
**预估工作量**: 1 人天 | **风险**: 低 | **优先级**: 本季度

## [M-4] 包含多个适配器文件的相似模式表明缺少抽象
**文件**:
  - C:\Users\leesu\BookwormPRO\agent\anthropic_adapter.py (1,714 行)
  - C:\Users\leesu\BookwormPRO\agent\bedrock_adapter.py (1,226 行)
  - C:\Users\leesu\BookwormPRO\agent\gemini_native_adapter.py (951 行)
  - C:\Users\leesu\BookwormPRO\agent\codex_responses_adapter.py (793 行)
  - C:\Users\leesu\BookwormPRO\agent\gemini_cloudcode_adapter.py (545 行)
  - C:\Users\leesu\BookwormPRO\agent\copilot_acp_client.py (351 行)
  - C:\Users\leesu\BookwormPRO\agent\google_code_assist.py (214 行)
**严重程度**: MEDIUM
**架构风险**:
- 7 个提供商适配器文件，没有共享的 `ProviderAdapter` 抽象。
- 每个适配器都有自己的 OAuth 刷新、令牌解析和客户端构建模式。
- 添加第 8 个提供商意味着复制粘贴其中一个适配器，并希望找到所有特定于提供商的部分。
- `transports/` 子包部分解决了这个问题（base.py、anthropic.py、bedrock.py、chat_completions.py、codex.py），但适配器仍然直接暴露。
- 没有用于适配器注册/发现的提供商标识符 —— 每个适配器都是手动导入的。
**重构建议**:
1. 定义一个 `ProviderAdapter` 协议，包含：`build_client()`, `refresh_token()`, `get_models()`, `supports_vision()`。
2. 创建一个适配器注册表，提供商在其中自我注册。
3. 将 transports/ 概念与 adapters/ 概念统一（它们重叠）。
4. 将适配器移到 `agent/providers/` 下，并带有公共 API。
**预估工作量**: 3-4 人天 | **风险**: 中等 —— 触及所有提供商集成 | **优先级**: 本季度

# ============================================================================
#  LOW — 在 tech-debt backlog 中跟踪
# ============================================================================

## [L-1] model_metadata.py: 1,417 行混合关注点
**文件**: C:\Users\leesu\BookwormPRO\agent\model_metadata.py
**严重程度**: LOW
**架构风险**:
- 混合了：模型元数据获取、令牌估计、上下文长度管理、Ollama 本地端点检测、错误解析。
- 函数如 `estimate_tokens_rough()`、`parse_context_limit_from_error()` 和 `query_ollama_num_ctx()` 服务于完全不同的关注点。
- 令牌估计是独立的，可以被多个模块重用，但当前与获取逻辑耦合。
**重构建议**: 拆分为 `agent/models/metadata.py`、`agent/models/token_estimator.py`、`agent/models/context_limits.py`
**预估工作量**: 0.5-1 人天 | **优先级**: 积压

## [L-2] context_compressor.py 与 auxiliary_client.py 紧密耦合
**文件**: C:\Users\leesu\BookwormPRO\agent\context_compressor.py
**严重程度**: LOW
**架构风险**:
- 依赖于 `auxiliary_client.call_llm()` —— 如果 auxiliary_client 被重构，context_compressor 会中断。
- 上下文压缩应能工作于任何 LLM 客户端，而不仅仅是辅助路由。
- 抽象是 `call_llm(messages, model, ...)` —— 这是一个通用接口，但当前命名的导入将其耦合到辅助模块。
**重构建议**: 通过依赖注入接受 `call_llm` 回调，而不是硬编码导入。
**预估工作量**: 0.5 人天 | **优先级**: 积压

## [L-3] 整个 agent/ 中的硬编码默认值蔓延
**文件**: 多个 (auxiliary_client.py, credential_pool.py, cost_tracker.py, health.py)
**严重程度**: LOW
**架构风险**:
- `_DEFAULT_THRESHOLD = 5`（circuit_breaker）、`EXHAUSTED_TTL_429_SECONDS = 3600`（credential_pool）、`WARN_THRESHOLD_DAILY_USD = 5.0`（cost_tracker）、`_AGENT_CACHE_MAX_SIZE = 128`（gateway/run.py）。
- 这些分散在代码中，没有统一配置。
- 更改断路器阈值需要 grep 代码库。
- 其中一些应从 config.yaml 读取，但没有模式。
**重构建议**: 创建一个 `agent/config.py`，其中包含带有 env-var 覆盖的 dataclass，从 config.yaml 读取。使用此单一入口点处理所有可调参数。
**预估工作量**: 1-2 人天 | **优先级**: 积压

## [L-4] image_gen_provider.py / image_gen_registry.py —— 隔离但脆弱
**文件**:
  - C:\Users\leesu\BookwormPRO\agent\image_gen_provider.py
  - C:\Users\leesu\BookwormPRO\agent\image_gen_registry.py
**严重程度**: LOW
**架构风险**:
- 图片生成模块与核心代理循环隔离 —— 好的。
- 但注册表模式（image_gen_registry）没有在 provider_health 或 circuit_breaker 中反映。
- 将新的图片提供商与 LLM 提供商不同地添加 —— 不一致的扩展模式。
- 如果主代码库转向适配器注册表模式，此模块需要重写。
**重构建议**: 当主提供商适配器被重构时（M-4），将图片生成提供商统一到同一注册模式中。
**预估工作量**: 包含在 M-4 中 | **优先级**: 积压

## [L-5] shell_hooks.py / text_filter.py—— 与核心循环紧密耦合
**文件**:
  - C:\Users\leesu\BookwormPRO\agent\shell_hooks.py
  - C:\Users\leesu\BookwormPRO\agent\text_filter.py
**严重程度**: LOW
**架构风险**:
- 从 run_agent.py 直接导入和调用 —— 如果 AIAgent 被拆分为组合（C-1），需要修改。
- 钩子系统是临时的 —— 添加新钩子需要修改 run_agent.py。
**重构建议**: 创建一个具有注册/调度模式的 `HookRegistry`，独立于 AIAgent。
**预估工作量**: 包含在 C-1 中 | **优先级**: 积压

# ============================================================================
#  摘要矩阵
# ============================================================================

| ID  | 严重程度 | 文件                          | 问题                           | 工作量 | 优先级          |
|-----|----------|-------------------------------|--------------------------------|--------|-----------------|
| C-1 | CRITICAL | run_agent.py                  | 13,155 行 God Class            | 15-25d | 下个主要版本    |
| C-2 | CRITICAL | auxiliary_client, aux_vision  | 辅助路径中无断路器              | 3-5d   | 本月            |
| C-3 | CRITICAL | credential_pool ↔ bwm_cli     | 双向层违规                      | 5-8d   | 下个主要版本    |
| H-1 | HIGH     | gateway/run.py                | 11,382 行单体                  | 4-6d   | 下个 sprint     |
| H-2 | HIGH     | auxiliary_client.py           | 单个文件中 7 个提供商           | 5-7d   | 下个 sprint     |
| H-3 | HIGH     | agent/ (扁平包)               | 无架构分层                      | 3-4d   | 下个 sprint     |
| H-4 | HIGH     | cost_tracker + circuit_breaker| 无成本门控断路器                | 2-3d   | 本月            |
| M-1 | MEDIUM   | auxiliary_client.py           | 20+ 惰性导入                    | 1-2d   | 本季度          |
| M-2 | MEDIUM   | credential_pool.py            | 混合业务逻辑 + 持久化           | 2-3d   | 本季度          |
| M-3 | MEDIUM   | provider_health + health      | 职责重叠                        | 1d     | 本季度          |
| M-4 | MEDIUM   | *adapter.py (7 个文件)        | 缺少提供商抽象                  | 3-4d   | 本季度          |
| L-1 | LOW      | model_metadata.py             | 混合关注点                      | 0.5-1d | 积压            |
| L-2 | LOW      | context_compressor.py         | 与 auxiliary 紧密耦合           | 0.5d   | 积压            |
| L-3 | LOW      | 多个                          | 硬编码默认值蔓延                | 1-2d   | 积压            |
| L-4 | LOW      | image_gen_*.py                | 不一致的扩展模式                | *      | 积压            |
| L-5 | LOW      | shell_hooks, text_filter      | 与 AIAgent 紧密耦合             | *      | 积压            |

**总预估**: CRITICAL 23-38 人天 | HIGH 14-20 人天 | MEDIUM 7-10 人天 | LOW 3-5 人天

# ============================================================================
#  架构依赖图（当前 vs 目标）
# ============================================================================

## 当前状态（中心辐射式）
```
                    run_agent.py (13k)
                   /    |    |    \    \
                  /     |    |     \    \
    credential_pool  aux_client  health  cost_tracker  context_compressor
         |              |    \       |         |
    bwm_cli.auth    anthropic  gemini  provider  circuit_breaker
    (双向耦合!)     adapter   adapter  health   (辅助中未使用!)
```

## 目标状态（分层）
```
  run_agent.py (精简，~3k)
       |
  AgentOrchestrator
       |
  +-----+------+------+------+
  |     |      |      |      |
  Conv  Tool   Prov  Context
  Loop  Orch   Route Mgr
                |
         ProviderRegistry
                |
    +-----------+-----------+
    |     |     |     |     |
   anth  gem   codex bedr  cust
   ropic  ini          ock   om

  credential_pool  ←  CredentialStore 接口  ←  bwm_cli.auth (实现)
  circuit_breaker  ←  在所有路径中一致使用
  cost_tracker     ←  CostCircuitBreaker (成本门控)
```

# ============================================================================
#  关键架构决策记录（建议的 ADR）
# ============================================================================

1. **ADR-001**: 将 AIAgent 拆分为组合服务（run_agent.py 拆分）
2. **ADR-002**: 对所有提供商适配器采用 ProviderAdapter 协议
3. **ADR-003**: 反转凭证存储依赖关系（agent/ 定义接口，bwm_cli/ 实现）
4. **ADR-004**: 在所有 LLM 调用路径中标准化 circuit_breaker 集成（主循环 + 辅助）
5. **ADR-005**: 从硬编码常量迁移到集中式 config dataclass
