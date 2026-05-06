# P2-1: run_agent.py God Class 拆分方案

> 创建日期: 2026-05-06
> 目标文件: `run_agent.py` (26,306 行, 712KB)
> 核心对象: `AIAgent` class (~24,000 行, 150+ methods)
> 预计工期: 15 个工作日
> 依赖: Phase 1 审计已完成 (见 `docs/code-quality-audit-phase2.md`)

---

## 执行摘要

`run_agent.py` 是 BookwormPRO 的核心入口文件，`AIAgent` 类承载了对话循环、工具编排、Provider 路由、上下文压缩、Session 持久化、记忆管理、响应格式化、流式处理、API 调用、凭证刷新、中断控制等全部功能。本方案将其拆分为 6 个新模块 + 保留精简后的 `AIAgent` 外壳，总计新建 ~8,000 行、移出 ~18,000 行、保留 ~8,000 行。

| 指标 | 拆分前 | 拆分后 |
|------|--------|--------|
| run_agent.py 行数 | 26,306 | ~6,000 |
| AIAgent 方法数 | ~150 | ~35 |
| 新增模块 | 0 | 6 |
| 新增测试文件 | 0 | 6+ |

---

## 1. 模块清单

### 1.1 模块级函数/类 (行 1-1704, 保留在 run_agent.py)

| 类别 | 符号 | 行号 | 行数 | 处理方式 |
|------|------|------|------|----------|
| Stdio 安全 | `_SafeWriter` | 255-350 | 95 | 保留 |
| Stdio 安全 | `_install_safe_stdio` | 419-433 | 15 | 保留 |
| 代理 | `_get_proxy_from_env` | 353-379 | 27 | 保留 |
| 代理 | `_get_proxy_for_base_url` | 381-417 | 37 | 保留 |
| 预算 | `IterationBudget` | 435-607 | 173 | 保留 |
| 工具并行 | `_is_destructive_command` | 609-629 | 21 | **移入 ToolOrchestrator** |
| 工具并行 | `_should_parallelize_tool_batch` | 631-717 | 87 | **移入 ToolOrchestrator** |
| 工具并行 | `_extract_parallel_scope_path` | 719-751 | 33 | **移入 ToolOrchestrator** |
| 工具并行 | `_paths_overlap` | 753-785 | 33 | **移入 ToolOrchestrator** |
| Unicode 清理 | `_sanitize_surrogates` | 787-815 | 29 | **移入 agent/sanitize.py** (新建) |
| Unicode 清理 | `_sanitize_structure_surrogates` | 817-881 | 65 | **移入 agent/sanitize.py** |
| Unicode 清理 | `_sanitize_messages_surrogates` | 883-1017 | 135 | **移入 agent/sanitize.py** |
| JSON 修复 | `_escape_invalid_chars_in_json_strings` | 1019-1101 | 83 | **移入 agent/sanitize.py** |
| JSON 修复 | `_repair_tool_call_arguments` | 1103-1295 | 193 | **移入 agent/sanitize.py** |
| Emoji 清理 | `_strip_non_ascii` | 1297-1339 | 43 | **移入 agent/sanitize.py** |
| Emoji 清理 | `_strip_emoji_keep_codeblocks` | 1341-1367 | 27 | **移入 agent/sanitize.py** |
| Unicode 清理 | `_sanitize_messages_non_ascii` | 1369-1485 | 117 | **移入 agent/sanitize.py** |
| Unicode 清理 | `_sanitize_tools_non_ascii` | 1487-1495 | 9 | **移入 agent/sanitize.py** |
| Unicode 清理 | `_sanitize_structure_non_ascii` | 1497-1585 | 89 | **移入 agent/sanitize.py** |
| Provider Headers | `_routermint_headers` | 1587-1603 | 17 | **移入 ProviderRouter** |
| Provider Headers | `_pool_may_recover_from_rate_limit` | 1605-1653 | 49 | **移入 ProviderRouter** |
| Provider Headers | `_qwen_portal_headers` | 1655-1703 | 49 | **移入 ProviderRouter** |
| CLI Entry | `main()` | 25875-26306 | 432 | 保留 |

### 1.2 AIAgent 方法分类 (行 1705-25874)

#### 类别 A: ConversationLoop — 对话编排 (核心循环)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `run_conversation()` | 18903-25801 | 6,898 | 主对话循环 (最大单体方法) |
| `chat()` | 25803-25869 | 67 | 简易接口 |

> `run_conversation()` 本身需要在拆分过程中逐步削减 — 其体内的大段逻辑（构建 api_kwargs、调用 API、执行工具、压缩上下文、持久化）将变为对新模块的委托调用。

#### 类别 B: PromptEngine — 提示词构建

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_build_system_prompt()` | 8855-9197 | 343 | 系统提示词组装 (SOUL.md + memory + skills + tools + platform hints) |
| `_format_tools_for_system_message()` | 6793-6839 | 47 | 工具列表格式化 |
| `_invalidate_system_prompt()` | 9597-9619 | 23 | 使缓存失效 |

#### 类别 C: ProviderRouter — Provider 路由与 Fallback

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_try_activate_fallback()` | 13695-14073 | 379 | 激活下一个 fallback provider |
| `_restore_primary_runtime()` | 14075-14243 | 169 | 恢复主 provider |
| `_try_recover_primary_transport()` | 14245-14409 | 165 | 恢复主 transport |
| `switch_model()` | 4195-4531 | 337 | 运行时切换模型 (含 client 重建) |
| `_is_openrouter_url()` | 5221-5227 | 7 | OpenRouter 判断 |
| `_is_direct_openai_url()` | 5085-5103 | 19 | OpenAI 直连判断 |
| `_model_requires_responses_api()` | 5379-5407 | 29 | (静态) Responses API 判断 |
| `_provider_model_requires_responses_api()` | 5409-5441 | 33 | Provider+Model 级判断 |
| `_qwen_prepare_chat_messages()` | 14799-14863 | 65 | Qwen 消息格式转换 |
| `_qwen_prepare_chat_messages_inplace()` | 14865-14919 | 55 | Qwen 原地转换 |
| `_is_qwen_portal()` | 14791-14797 | 7 | Qwen 网关判断 |
| `_anthropic_preserve_dots()` | 14729-14789 | 61 | Anthropic 点号保留策略 |

#### 类别 D: ToolOrchestrator — 工具调用编排

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_execute_tool_calls()` | 16865-16909 | 45 | 工具调用调度 (并行 vs 串行) |
| `_execute_tool_calls_concurrent()` | 17165-17769 | 605 | 并发执行 |
| `_execute_tool_calls_sequential()` | 17771-18547 | 777 | 串行执行 |
| `_invoke_tool()` | 16949-17115 | 167 | 单个工具调用 |
| `_dispatch_delegate_task()` | 16911-16947 | 37 | delegate_task 分发 |
| `_wrap_verbose()` | 17117-17163 | 47 | (静态) 日志格式化 |
| `_cap_delegate_task_calls()` | 9357-9417 | 61 | (静态) delegate 数量限制 |
| `_deduplicate_tool_calls()` | 9419-9451 | 33 | (静态) 工具去重 |
| `_repair_tool_call()` | 9453-9595 | 143 | 工具名修复 |
| `_handle_max_iterations()` | 18549-18901 | 353 | 达到最大迭代后的处理 |

#### 类别 E: ContextManager — 上下文压缩与记忆

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_compress_context()` | 16633-16863 | 231 | 调用 ContextCompressor 压缩 |
| `_check_compression_model_feasibility()` | 4805-5049 | 245 | 压缩模型可行性检查 |
| `_replay_compression_warning()` | 5051-5083 | 33 | 重放压缩警告 |
| `flush_memories()` | 16143-16631 | 489 | 刷新记忆到存储 |
| `_sync_external_memory_for_turn()` | 8427-8511 | 85 | 外部记忆同步 |
| `commit_memory_session()` | 8403-8425 | 23 | 提交记忆会话 |
| `shutdown_memory_provider()` | 8349-8401 | 53 | 关闭记忆提供者 |
| `_hydrate_todo_store()` | 8763-8827 | 65 | 从历史重建 TODO |

#### 类别 F: ResponseHandler — 响应处理与格式化

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_build_assistant_message()` | 15389-15735 | 347 | 构建 assistant 消息 dict |
| `_extract_reasoning()` | 5949-6081 | 133 | 提取推理内容 |
| `_has_content_after_think_block()` | 5465-5509 | 45 | 检查 think 块后有内容 |
| `_strip_think_blocks()` | 5511-5699 | 189 | 剥离 think 块 |
| `_has_natural_response_ending()` | 5701-5721 | 21 | (静态) 自然结束检测 |
| `_is_ollama_glm_backend()` | 5723-5741 | 19 | Ollama GLM 检测 |
| `_should_treat_stop_as_truncated()` | 5743-5803 | 61 | 截断判断 |
| `_looks_like_codex_intermediate_ack()` | 5805-5947 | 143 | Codex 中间 ACK 检测 |
| `_summarize_background_review_actions()` | 6221-6343 | 123 | 后台审查摘要 |
| `_spawn_background_review()` | 6345-6517 | 173 | 启动后台审查 |
| `_build_memory_write_metadata()` | 6519-6569 | 51 | 记忆写入元数据 |
| `_cleanup_task_resources()` | 6083-6219 | 137 | 清理任务资源 |

#### 类别 G: API 调用 (在 run_agent.py 保留)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_interruptible_api_call()` | 11521-11815 | 295 | 可中断非流式 API 调用 |
| `_interruptible_streaming_api_call()` | 12005-13693 | 1,689 | 可中断流式 API 调用 |
| `_build_api_kwargs()` | 14921-15249 | 329 | 构建 API kwargs (按 api_mode 分支) |
| `_anthropic_messages_create()` | 11471-11479 | 9 | Anthropic 消息创建 |
| `_rebuild_anthropic_client()` | 11481-11519 | 39 | 重建 Anthropic 客户端 |
| `_run_codex_stream()` | 10501-10745 | 245 | Codex 流式调用 |
| `_run_codex_create_stream_fallback()` | 10747-10901 | 155 | Codex fallback 流 |

> API 调用方法属于横切关注点，暂时保留在 AIAgent 中，后续可通过 transport 抽象层进一步解耦。

#### 类别 H: Client/Connection Management (在 run_agent.py 保留)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_ensure_primary_openai_client()` | 10303-10333 | 31 | 确保主客户端存在 |
| `_create_openai_client()` | 9915-10109 | 195 | 创建 OpenAI 客户端 |
| `_close_openai_client()` | 10227-10267 | 41 | 关闭客户端 |
| `_replace_primary_openai_client()` | 10269-10301 | 33 | 替换主客户端 |
| `_create_request_openai_client()` | 10475-10493 | 19 | 创建请求级客户端 |
| `_close_request_openai_client()` | 10495-10499 | 5 | 关闭请求级客户端 |
| `_build_keepalive_http_client()` | 9767-9823 | 57 | 构建 Keepalive HTTP |
| `_get_or_create_pooled_http_client()` | 9825-9875 | 51 | HTTP 连接池 |
| `_sweep_idle_pool_connections()` | 9877-9913 | 37 | 清理空闲连接 |
| `_cleanup_dead_connections()` | 10335-10473 | 139 | 清理死连接 |
| `_force_close_tcp_sockets()` | 10111-10225 | 115 | (静态) 强制关闭 TCP |
| `_is_openai_client_closed()` | 9707-9765 | 59 | (静态) 客户端关闭检测 |
| `_openai_client_lock()` | 9691-9705 | 15 | 客户端锁 |

#### 类别 I: Credential/Auth Refresh (在 run_agent.py 保留)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_try_refresh_codex_client_credentials()` | 10903-10959 | 57 | Codex 凭证刷新 |
| `_try_refresh_nous_client_credentials()` | 10961-11029 | 69 | Nous 凭证刷新 |
| `_try_refresh_copilot_client_credentials()` | 11031-11099 | 69 | Copilot 凭证刷新 |
| `_try_refresh_anthropic_client_credentials()` | 11101-11191 | 91 | Anthropic 凭证刷新 |
| `_apply_client_headers_for_base_url()` | 11193-11241 | 49 | 客户端 Headers |
| `_swap_credential()` | 11243-11301 | 59 | 凭证热切换 |
| `_recover_with_credential_pool()` | 11303-11469 | 167 | 凭证池恢复 |

#### 类别 J: Session/Persistence (在 run_agent.py 保留)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_persist_session()` | 6607-6631 | 25 | 持久化入口 |
| `_flush_messages_to_session_db()` | 6633-6729 | 97 | SQLite 写入 |
| `_save_session_log()` | 7693-7823 | 131 | JSON 日志写入 |
| `_get_messages_up_to_last_assistant()` | 6731-6791 | 61 | 消息截断 |
| `_apply_persist_user_message_override()` | 6571-6605 | 35 | 用户消息覆盖 |
| `_convert_to_trajectory_format()` | 6841-7169 | 329 | 轨迹格式转换 |
| `_save_trajectory()` | 7171-7201 | 31 | 保存轨迹 |
| `_clean_session_content()` | 7675-7691 | 17 | (静态) 清理会话内容 |
| `reset_session_state()` | 4117-4193 | 77 | 重置会话状态 |

#### 类别 K: Interrupt/Steer/Activity (在 run_agent.py 保留)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `interrupt()` | 7825-7959 | 135 | 中断请求 |
| `clear_interrupt()` | 7961-8025 | 65 | 清除中断 |
| `steer()` | 8027-8097 | 71 | 引导注入 |
| `_drain_pending_steer()` | 8099-8129 | 31 | 排出待处理引导 |
| `_apply_pending_steer_to_tool_results()` | 8131-8255 | 125 | 引导应用到工具结果 |
| `_touch_activity()` | 8257-8265 | 9 | 活动心跳 |
| `_capture_rate_limits()` | 8267-8303 | 37 | 限速捕获 |
| `get_rate_limit_state()` | 8305-8311 | 7 | 限速状态查询 |
| `get_activity_summary()` | 8313-8347 | 35 | 活动摘要 |
| `is_interrupted()` | 8829-8853 | 25 | 中断状态检查 |

#### 类别 L: Stream/Display (在 run_agent.py 保留)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_reset_stream_delivery_tracking()` | 11817-11823 | 7 | 重置流追踪 |
| `_record_streamed_assistant_text()` | 11825-11839 | 15 | 记录流文本 |
| `_normalize_interim_visible_text()` | 11841-11849 | 9 | (静态) 标准化可见文本 |
| `_interim_content_was_streamed()` | 11851-11871 | 21 | 检查是否已流式传输 |
| `_emit_interim_assistant_message()` | 11873-11901 | 29 | 发送中间 assistant 消息 |
| `_fire_stream_delta()` | 11903-11941 | 39 | 触发流 delta 回调 |
| `_fire_reasoning_delta()` | 11943-11959 | 17 | 触发推理 delta |
| `_fire_tool_gen_started()` | 11961-11989 | 29 | 触发工具生成开始 |
| `_has_stream_consumers()` | 11991-12003 | 13 | 是否有流消费者 |
| `_safe_print()` | 4533-4567 | 35 | 安全打印 |
| `_vprint()` | 4569-4621 | 53 | 详细打印 |
| `_should_start_quiet_spinner()` | 4623-4659 | 37 | 安静模式 spinner |
| `_should_emit_quiet_tool_messages()` | 4661-4687 | 27 | 安静模式工具消息 |
| `_emit_status()` | 4689-4727 | 39 | 状态通知 |
| `_emit_warning()` | 4729-4761 | 33 | 警告通知 |
| `_emit_auxiliary_failure()` | 4763-4783 | 21 | 辅助失败通知 |
| `_current_main_runtime()` | 4785-4803 | 19 | 当前主运行时信息 |

#### 类别 M: Utility/Static (在 run_agent.py 保留)

| 方法 | 行号 | 行数 | 说明 |
|------|------|------|------|
| `_summarize_api_error()` | 7203-7279 | 77 | (静态) API 错误摘要 |
| `_mask_api_key_for_logs()` | 7281-7293 | 13 | 密钥掩码 |
| `_clean_error_message()` | 7295-7347 | 53 | 清理错误消息 |
| `_extract_api_error_context()` | 7349-7475 | 127 | (静态) 提取 API 错误上下文 |
| `_usage_summary_for_api_request_hook()` | 7477-7507 | 31 | API 使用摘要 |
| `_dump_api_request_debug()` | 7509-7673 | 165 | API 请求调试 dump |
| `_get_tool_call_id_static()` | 9199-9215 | 17 | (静态) 工具调用 ID |
| `_sanitize_api_messages()` | 9217-9355 | 139 | (静态) API 消息清理 |
| `_deterministic_call_id()` | 9621-9639 | 19 | (静态) 确定性调用 ID |
| `_split_responses_tool_id()` | 9641-9647 | 7 | (静态) 分割 Responses 工具 ID |
| `_derive_responses_function_call_id()` | 9649-9663 | 15 | (静态) 派生函数调用 ID |
| `_thread_identity()` | 9665-9671 | 7 | 线程标识 |
| `_client_log_context()` | 9673-9689 | 17 | 客户端日志上下文 |
| `_resolved_api_call_timeout()` | 5105-5143 | 39 | API 超时计算 |
| `_resolved_api_call_stale_timeout_base()` | 5145-5191 | 47 | 过期超时基准 |
| `_compute_non_stream_stale_timeout()` | 5193-5219 | 27 | 非流式过期超时 |
| `_anthropic_prompt_cache_policy()` | 5229-5377 | 149 | Anthropic 缓存策略 |
| `_max_tokens_param()` | 5443-5463 | 21 | max_tokens 参数 |
| `_content_has_image_parts()` | 14411-14427 | 17 | (静态) 图片检测 |
| `_materialize_data_url_for_vision()` | 14429-14467 | 39 | (静态) Data URL 物化 |
| `_describe_image_for_anthropic_fallback()` | 14469-14569 | 101 | (静态) 图片描述 |
| `_preprocess_anthropic_content()` | 14571-14657 | 87 | Anthropic 内容预处理 |
| `_get_transport()` | 14659-14693 | 35 | 获取 transport |
| `_prepare_anthropic_messages_for_api()` | 14695-14727 | 33 | Anthropic 消息准备 |
| `_supports_reasoning_extra_body()` | 15251-15323 | 73 | 推理额外 body 支持 |
| `_github_models_reasoning_extra_body()` | 15325-15387 | 63 | GitHub Models 推理 body |
| `_needs_kimi_tool_reasoning()` | 15737-15763 | 27 | Kimi 推理需求 |
| `_needs_deepseek_tool_reasoning()` | 15765-15793 | 29 | DeepSeek 推理需求 |
| `_copy_reasoning_content_for_api()` | 15795-15843 | 49 | 推理内容复制 |
| `_sanitize_tool_calls_for_strict_api()` | 15845-15899 | 55 | (静态) 严格 API 清理 |
| `_sanitize_tool_call_arguments()` | 15901-16115 | 215 | 工具参数清理 |
| `_should_sanitize_tool_calls()` | 16117-16141 | 25 | 是否需要清理工具调用 |
| `release_clients()` | 8513-8605 | 93 | 释放所有客户端 |
| `drain()` | 8607-8637 | 31 | 排空 |
| `close()` | 8639-8761 | 123 | 关闭 agent |

---

## 2. 拆分目标模块

### 2.1 agent/conversation_loop.py — ConversationLoop (新建)

**职责**: 对话循环编排 — 驱动 `while` 循环，协调 API 调用、工具执行、上下文压缩的调度。

```
agent/conversation_loop.py
├── class ConversationLoop
│   ├── __init__(agent_ref)          # 持有 AIAgent 引用
│   ├── run(user_message, ...)        # 主循环入口 (~2000 行，从 run_conversation 提取核心 while 循环)
│   │   ├── _preflight_checks()       # 中断检查、预算消耗、pre-API steer drain
│   │   ├── _prepare_api_messages()   # 构建 api_messages (含 plugin context 注入)
│   │   ├── _normalize_api_messages() # JSON 规范化、Unicode 清理
│   │   └── _post_response_cleanup()  # 压缩检查、持久化、错误处理
│   └── _build_turn_context()         # 构建当轮上下文
```

**从 run_agent.py 移入**:
- `run_conversation()` 的 while 循环体 (~5,000 行) → `ConversationLoop.run()`
- 循环内的消息构建、规范化、响应处理逻辑

**保留在 AIAgent**:
- `run_conversation()` 变为薄封装: 初始化状态 + 创建 `ConversationLoop` + 调用 `.run()`
- `chat()` 不变

**估算行数**: ~2,500 行

---

### 2.2 agent/tool_orchestrator.py — ToolOrchestrator (新建)

**职责**: 工具调用编排 — 管理工具调度的并行/串行决策、工具执行、结果处理。

```
agent/tool_orchestrator.py
├── class ToolOrchestrator
│   ├── __init__(agent_ref)
│   ├── execute(assistant_message, messages, task_id, api_call_count)
│   │   ├── _execute_concurrent()     # 并行执行
│   │   ├── _execute_sequential()     # 串行执行
│   │   ├── _invoke_tool()            # 单个工具调用
│   │   └── _dispatch_delegate_task() # delegate_task 特殊处理
│   ├── _build_tool_result_message()  # 构建 tool result message
│   ├── _apply_pending_steer()        # 应用 /steer 到工具结果
│   └── _handle_max_iterations()      # 达到上限后的处理
│
├── # 模块级函数
├── _is_destructive_command(cmd)
├── _should_parallelize_tool_batch(tool_calls)
├── _extract_parallel_scope_path(tool_name, function_args)
├── _paths_overlap(left, right)
├── _cap_delegate_task_calls(tool_calls)
├── _deduplicate_tool_calls(tool_calls)
├── _repair_tool_call(tool_name)
└── _wrap_verbose(label, text, indent)
```

**从 run_agent.py 移入**:
- `_execute_tool_calls()`, `_execute_tool_calls_concurrent()`, `_execute_tool_calls_sequential()`
- `_invoke_tool()`, `_dispatch_delegate_task()`
- `_handle_max_iterations()`
- 所有模块级工具并行判断函数

**保留在 AIAgent**:
- 工具列表 (`self.tools`, `self.valid_tool_names`) 作为属性
- `enforce_turn_budget` 调用 (作为横切关注点在 orchestrator 中通过 agent_ref 访问)

**估算行数**: ~2,800 行

---

### 2.3 agent/provider_router.py — ProviderRouter (新建)

**职责**: Provider 路由、Fallback 链管理、模型切换。

```
agent/provider_router.py
├── class ProviderRouter
│   ├── __init__(agent_ref)
│   ├── try_activate_fallback(reason)    # 激活 fallback
│   ├── restore_primary_runtime()        # 恢复主 provider
│   ├── try_recover_primary_transport()  # 恢复 transport
│   ├── switch_model(new_model, ...)     # 热切换模型
│   ├── build_api_kwargs(api_messages)   # 按 api_mode 构建 kwargs
│   └── get_transport(api_mode)          # 获取 transport
│
├── # Provider 适配器
├── class AnthropicAdapter
│   ├── prepare_messages(messages)
│   ├── preserve_dots()
│   └── build_kwargs(model, messages, ...)
│
├── class QwenAdapter
│   ├── prepare_chat_messages(messages)
│   ├── prepare_chat_messages_inplace(messages)
│   └── headers()
│
├── # 模块级
├── _routermint_headers()
├── _pool_may_recover_from_rate_limit(pool)
├── _qwen_portal_headers()
├── _is_openrouter_url(url)
├── _is_direct_openai_url(url)
├── _model_requires_responses_api(model)
└── _provider_model_requires_responses_api(model, provider)
```

**从 run_agent.py 移入**:
- `_try_activate_fallback()`, `_restore_primary_runtime()`, `_try_recover_primary_transport()`
- `switch_model()`
- `_build_api_kwargs()` (provider dispatch 部分)
- `_get_transport()`
- Qwen 适配器方法
- Anthropic 适配器方法
- Provider 判断辅助函数

**保留在 AIAgent**:
- `self.provider`, `self.model`, `self.api_mode`, `self.base_url`
- `self._primary_runtime`, `self._fallback_chain`, `self._fallback_index`
- API 调用本身 (`_interruptible_api_call`, `_interruptible_streaming_api_call`)
- Client 管理方法

**估算行数**: ~3,500 行

---

### 2.4 agent/response_handler.py — ResponseHandler (新建)

**职责**: API 响应解析、assistant 消息构建、推理提取、内容格式化。

```
agent/response_handler.py
├── class ResponseHandler
│   ├── __init__(agent_ref)
│   ├── build_assistant_message(response, finish_reason)  # OpenAI/Codex 响应 → dict
│   ├── extract_reasoning(assistant_message)              # 提取 reasoning
│   ├── strip_think_blocks(content)                       # <think> 剥离
│   ├── has_content_after_think_block(content)
│   ├── should_treat_stop_as_truncated(response, model)
│   ├── looks_like_codex_intermediate_ack(content, tool_calls)
│   └── has_natural_response_ending(content)
│
├── # 模块级
├── _is_ollama_glm_backend(model)
├── _needs_kimi_tool_reasoning(provider, model)
├── _needs_deepseek_tool_reasoning(provider, model)
└── _copy_reasoning_content_for_api(source_msg, api_msg)
```

**从 run_agent.py 移入**:
- `_build_assistant_message()`
- `_extract_reasoning()`
- `_strip_think_blocks()`, `_has_content_after_think_block()`
- `_should_treat_stop_as_truncated()`, `_looks_like_codex_intermediate_ack()`
- `_has_natural_response_ending()`, `_is_ollama_glm_backend()`
- `_needs_kimi_tool_reasoning()`, `_needs_deepseek_tool_reasoning()`
- `_copy_reasoning_content_for_api()`

**保留在 AIAgent**:
- `_summarize_background_review_actions()`, `_spawn_background_review()` (与工具执行耦合)
- `_build_memory_write_metadata()` (与记忆耦合)
- `_cleanup_task_resources()` (与 VM 资源耦合)

**估算行数**: ~1,500 行

---

### 2.5 agent/context_manager.py — ContextManager (新建)

**职责**: 上下文压缩编排、记忆刷新、TODO 状态恢复。

```
agent/context_manager.py
├── class ContextManager
│   ├── __init__(agent_ref)
│   ├── compress(messages, system_message, ...)  # 调用 ContextCompressor
│   ├── flush_memories(messages, min_turns)
│   ├── sync_external_memory_for_turn(...)
│   ├── commit_memory_session(messages)
│   ├── shutdown_memory_provider(messages)
│   ├── hydrate_todo_store(history)
│   ├── check_compression_model_feasibility()
│   └── replay_compression_warning()
└── # 注意: 实际压缩逻辑在 agent/context_compressor.py (已存在)
```

**从 run_agent.py 移入**:
- `_compress_context()`
- `flush_memories()`
- `_sync_external_memory_for_turn()`
- `commit_memory_session()`, `shutdown_memory_provider()`
- `_hydrate_todo_store()`
- `_check_compression_model_feasibility()`, `_replay_compression_warning()`

**保留在 AIAgent**:
- `self.context_compressor` 引用
- `self._memory_store`, `self._memory_manager` 引用

**估算行数**: ~1,600 行

---

### 2.6 agent/sanitize.py — 消息/Unicode/JSON 清理 (新建, 纯函数模块)

**职责**: 所有消息清理、Unicode 规范化、JSON 修复函数。

```
agent/sanitize.py
├── # Unicode 清理
├── _sanitize_surrogates(text)
├── _sanitize_structure_surrogates(payload)
├── _sanitize_messages_surrogates(messages)
├── _strip_non_ascii(text)
├── _strip_emoji_keep_codeblocks(text)
├── _sanitize_messages_non_ascii(messages)
├── _sanitize_tools_non_ascii(tools)
├── _sanitize_structure_non_ascii(payload)
│
├── # JSON 修复
├── _escape_invalid_chars_in_json_strings(raw)
├── _repair_tool_call_arguments(raw_args, tool_name)
│
├── # API 消息清理 (从 AIAgent 移入)
├── _sanitize_api_messages(messages)
├── _sanitize_tool_calls_for_strict_api(api_msg)
├── _sanitize_tool_call_arguments(messages, logger, session_id)
├── _should_sanitize_tool_calls(provider, base_url)
│
├── # Tool Call ID
├── _deterministic_call_id(fn_name, arguments, index)
├── _split_responses_tool_id(raw_id)
└── _derive_responses_function_call_id(tool_name, arguments, index)
```

**从 run_agent.py 移入**:
- 所有模块级 sanitize 函数 (10 个)
- `_sanitize_api_messages()`, `_sanitize_tool_calls_for_strict_api()`, `_sanitize_tool_call_arguments()`
- `_deterministic_call_id()`, `_split_responses_tool_id()`, `_derive_responses_function_call_id()`

**这个模块无类 — 纯函数集合，零依赖。**

**估算行数**: ~1,200 行

---

## 3. 提取顺序与依赖关系

```
Phase 0: agent/sanitize.py       (零依赖, 纯函数)
    |
Phase 1: agent/response_handler.py  (依赖 sanitize)
    |
Phase 2: agent/tool_orchestrator.py (依赖 sanitize, response_handler)
    |
Phase 3: agent/context_manager.py   (依赖 agent/context_compressor [已存在])
    |
Phase 4: agent/provider_router.py   (依赖 sanitize, agent/auxiliary_client)
    |
Phase 5: agent/conversation_loop.py (依赖 1-4 全部)
```

**依赖图**:
```
sanitize (Phase 0)
    ^--- response_handler (Phase 1)
    ^--- tool_orchestrator (Phase 2)
    ^--- provider_router (Phase 4)
    
context_manager (Phase 3) ---> context_compressor (已存在)

conversation_loop (Phase 5) ---> 1 + 2 + 3 + 4 + AIAgent (self 引用)
```

---

## 4. 各阶段详细计划

### Phase 0: sanitize.py (2 天)

**移出内容**:
- 所有模块级清理函数 (17 个函数, ~1,200 行)
- `AIAgent._sanitize_api_messages()` → `sanitize.sanitize_api_messages()`
- `AIAgent._sanitize_tool_calls_for_strict_api()` → `sanitize.sanitize_tool_calls_for_strict_api()`
- `AIAgent._sanitize_tool_call_arguments()` → `sanitize.sanitize_tool_call_arguments()`
- `AIAgent._deterministic_call_id()` → `sanitize.deterministic_call_id()`
- `AIAgent._split_responses_tool_id()` → `sanitize.split_responses_tool_id()`
- `AIAgent._derive_responses_function_call_id()` → `sanitize.derive_responses_function_call_id()`

**向后兼容**:
```python
# 在 AIAgent 中保留代理方法 (delegate to new module)
def _sanitize_api_messages(self, messages):
    return sanitize.sanitize_api_messages(messages)

def _deterministic_call_id(self, fn_name, arguments, index=0):
    return sanitize.deterministic_call_id(fn_name, arguments, index)
```

**测试策略**:
1. 新增 `tests/agent/test_sanitize.py`
2. 覆盖所有 17 个函数: surrogate cleaning, JSON repair edge cases, emoji stripping
3. 与现有 API 错误日志对比验证

---

### Phase 1: response_handler.py (2 天)

**移出内容**:
- `_build_assistant_message()` → `ResponseHandler.build_assistant_message()`
- `_extract_reasoning()` → `ResponseHandler.extract_reasoning()`
- `_strip_think_blocks()` → `ResponseHandler.strip_think_blocks()`
- 其他 5 个响应处理方法

**向后兼容**:
```python
# AIAgent.__init__ 中初始化
self._response_handler = ResponseHandler(self)

# 代理方法
def _build_assistant_message(self, *args, **kwargs):
    return self._response_handler.build_assistant_message(*args, **kwargs)
```

**测试策略**:
1. `tests/agent/test_response_handler.py`
2. 测试 think block 剥离的各种边界情况
3. 测试 Codex vs OpenAI response 格式差异
4. 测试 reasoning 提取的准确性

---

### Phase 2: tool_orchestrator.py (3 天)

**移出内容**: 所有工具执行逻辑 (~2,800 行)

**关键改动**:
- `_execute_tool_calls()` 变为 `ToolOrchestrator.execute()`
- 工具并行判断逻辑从 AIAgent 移到 ToolOrchestrator
- 保留 `handle_function_call` 在 `model_tools.py` (已存在)

**向后兼容**:
```python
self._tool_orchestrator = ToolOrchestrator(self)

def _execute_tool_calls(self, assistant_message, messages, effective_task_id, api_call_count=0):
    self._tool_orchestrator.execute(assistant_message, messages, effective_task_id, api_call_count)
```

**测试策略**:
1. `tests/agent/test_tool_orchestrator.py`
2. 测试并行/串行调度决策逻辑
3. 测试 delegate_task 分发
4. 测试 max_iterations 处理

---

### Phase 3: context_manager.py (2 天)

**移出内容**: `_compress_context()`, `flush_memories()`, 记忆相关方法 (~1,600 行)

**向后兼容**:
```python
self._context_manager = ContextManager(self)

def _compress_context(self, *args, **kwargs):
    return self._context_manager.compress(*args, **kwargs)
```

**测试策略**:
1. `tests/agent/test_context_manager.py`
2. 测试压缩阈值判断
3. 测试记忆刷新逻辑

---

### Phase 4: provider_router.py (3 天)

**移出内容**: Provider 路由、fallback 链、模型切换、API kwargs 构建 (~3,500 行)

**关键改动**:
- `_try_activate_fallback()` → `ProviderRouter.try_activate_fallback()`
- `switch_model()` → `ProviderRouter.switch_model()`
- `_build_api_kwargs()` → `ProviderRouter.build_api_kwargs()`
- Qwen/Anthropic 适配器独立出来

**向后兼容**:
```python
self._provider_router = ProviderRouter(self)

def _try_activate_fallback(self, *args, **kwargs):
    return self._provider_router.try_activate_fallback(*args, **kwargs)
```

**测试策略**:
1. `tests/agent/test_provider_router.py`
2. 测试 fallback 链遍历
3. 测试 model switch 状态一致性
4. 测试 Qwen/Anthropic 消息转换

---

### Phase 5: conversation_loop.py (3 天)

**移出内容**: `run_conversation()` 的 while 循环体 (~5,000 行)

**关键改动**:
- `run_conversation()` 变为薄封装
- `ConversationLoop` 持有 `AIAgent` 引用，调用其委托方法
- while 循环从 AIAgent 移出到 ConversationLoop

**最终 run_agent.py 结构**:
```python
class AIAgent:
    def __init__(self, ...):
        # 初始化所有子模块
        self._response_handler = ResponseHandler(self)
        self._tool_orchestrator = ToolOrchestrator(self)
        self._context_manager = ContextManager(self)
        self._provider_router = ProviderRouter(self)
        self._conversation_loop = ConversationLoop(self)
    
    def run_conversation(self, user_message, ...):
        # 初始化 + 前置处理
        # 委托给 ConversationLoop.run()
        return self._conversation_loop.run(user_message, ...)
    
    def chat(self, message, ...):
        # 不变
```

**测试策略**:
1. `tests/agent/test_conversation_loop.py`
2. 集成测试: 完整对话流程 (mock API 响应)
3. 测试中断、预算耗尽、fallback 触发等边界场景

---

## 5. 测试策略

### 5.1 分层测试

| 层级 | 测试类型 | 目标覆盖率 | 文件 |
|------|----------|-----------|------|
| L0: 纯函数 | 单元测试 | >90% | `test_sanitize.py` |
| L1: 子模块 | 单元测试 + mock | >80% | `test_response_handler.py`, `test_tool_orchestrator.py`, etc. |
| L2: 集成 | 场景测试 | >60% | `test_conversation_loop.py`, `test_provider_router.py` |
| L3: E2E | 端到端 | 关键路径 | `test_run_agent.py` (更新现有) |

### 5.2 回归测试

- 每次 Phase 完成后运行全量测试: `scripts/run_tests.sh`
- 重点监控: 现有 700+ 测试文件中引用 `run_agent.AIAgent` 的测试
- 对 `from run_agent import AIAgent` 的导入保持不变

### 5.3 性能对比

在每次 Phase 完成后:
```bash
# 基准: run_conversation 延迟
time python -c "from run_agent import AIAgent; ..."

# 内存: 模块导入开销
python -m memory_profiler run_agent.py
```

---

## 6. 回滚方案

### 6.1 每 Phase 的 Git 策略

```
main
  ├── feature/p2-1-phase0-sanitize    (可独立合并)
  ├── feature/p2-1-phase1-response    (基于 phase0)
  ├── feature/p2-1-phase2-tool-orch   (基于 phase1)
  ├── feature/p2-1-phase3-context     (基于 phase2)
  ├── feature/p2-1-phase4-provider    (基于 phase3)
  └── feature/p2-1-phase5-loop        (基于 phase4)
```

### 6.2 回滚触发条件

| 条件 | 动作 |
|------|------|
| 任何 Phase 导致测试失败 >5 个 | revert 该 Phase，修复后重试 |
| 性能退化 >10% (延迟/内存) | 暂停推进，profiling 分析 |
| 生产环境报错 (通过 canary 部署) | 立即回滚到上一稳定版本 |

### 6.3 回滚操作

```bash
# 回滚单个 Phase
git revert <phase_merge_commit>

# 紧急回滚到拆分前
git checkout v<PRE_SPLIT_TAG> -- run_agent.py
```

### 6.4 向后兼容保证

每个被移出的方法在 AIAgent 中保留代理:
```python
# Forwarder pattern: 零破坏性
def _legacy_method(self, *args, **kwargs):
    return self._new_module.renamed_method(*args, **kwargs)
```

所有 `from run_agent import AIAgent` 的导入路径不变。AIAgent 公开 API 不变。

---

## 7. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 隐式状态耦合导致拆分后行为不同 | 中 | 高 | 每 Phase 后完整的集成测试 |
| `self` 引用链过长 (AIAgent → Module → AIAgent) | 中 | 中 | 严格控制子模块只通过 agent_ref 访问 AIAgent |
| 循环导入 | 低 | 高 | 子模块使用 TYPE_CHECKING + 延迟导入 |
| 第三方代码依赖内部私有方法 `_xxx` | 低 | 中 | grep 全仓库检查 `_xxx` 调用者 |
| Phase 间合并冲突 | 中 | 低 | 每 Phase 是独立分支，合并到 main 时 squash |

---

## 8. 成功指标

- [ ] `run_agent.py` 从 26,306 行缩减到 <8,000 行
- [ ] AIAgent 公开方法数从 ~150 减少到 <40
- [ ] 新增 6 个模块，每个 <4,000 行
- [ ] 全量测试通过率 100%
- [ ] `from run_agent import AIAgent` 导入行为不变
- [ ] `chat()` 和 `run_conversation()` 公开 API 签名不变
- [ ] 无性能退化 (P50 延迟变化 <5%)

---

## 附录: run_agent.py 完整方法索引

### AIAgent 方法字母序 (共 ~150 个)

```
_anthropic_messages_create        _anthropic_preserve_dots
_anthropic_prompt_cache_policy    _apply_client_headers_for_base_url
_apply_pending_steer_to_tool_results  _apply_persist_user_message_override
_build_api_kwargs                 _build_assistant_message
_build_keepalive_http_client      _build_memory_write_metadata
_build_system_prompt              _cap_delegate_task_calls
_capture_rate_limits              _check_compression_model_feasibility
_clean_error_message              _clean_session_content
_cleanup_dead_connections         _cleanup_task_resources
_client_log_context               _close_openai_client
_close_request_openai_client      _commit_memory_session (→ commit_memory_session)
_compress_context                 _compute_non_stream_stale_timeout
_content_has_image_parts          _convert_to_trajectory_format
_copy_reasoning_content_for_api   _create_openai_client
_create_request_openai_client     _current_main_runtime
_deduplicate_tool_calls           _derive_responses_function_call_id
_describe_image_for_anthropic_fallback  _deterministic_call_id
_dispatch_delegate_task           _drain_pending_steer
_dump_api_request_debug           _emit_auxiliary_failure
_emit_interim_assistant_message   _emit_status
_emit_warning                     _ensure_primary_openai_client
_execute_tool_calls               _execute_tool_calls_concurrent
_execute_tool_calls_sequential    _extract_api_error_context
_extract_reasoning                _fire_reasoning_delta
_fire_stream_delta                _fire_tool_gen_started
_flush_messages_to_session_db     _force_close_tcp_sockets
_format_tools_for_system_message  _get_messages_up_to_last_assistant
_get_or_create_pooled_http_client  _get_tool_call_id_static
_get_transport                    _github_models_reasoning_extra_body
_handle_max_iterations            _has_content_after_think_block
_has_natural_response_ending      _has_stream_consumers
_hydrate_todo_store               _interim_content_was_streamed
_interruptible_api_call           _interruptible_streaming_api_call
_invalidate_system_prompt         _invoke_tool
_is_direct_openai_url             _is_ollama_glm_backend
_is_openai_client_closed          _is_openrouter_url
_is_qwen_portal                   _looks_like_codex_intermediate_ack
_mask_api_key_for_logs            _materialize_data_url_for_vision
_max_tokens_param                 _model_requires_responses_api
_needs_deepseek_tool_reasoning    _needs_kimi_tool_reasoning
_normalize_interim_visible_text   _openai_client_lock
_persist_session                  _prepare_anthropic_messages_for_api
_preprocess_anthropic_content     _provider_model_requires_responses_api
_qwen_prepare_chat_messages       _qwen_prepare_chat_messages_inplace
_rebuild_anthropic_client         _record_streamed_assistant_text
_recover_with_credential_pool     _repair_tool_call
_replay_compression_warning       _replace_primary_openai_client
_reset_stream_delivery_tracking   _resolved_api_call_stale_timeout_base
_resolved_api_call_timeout        _restore_primary_runtime
_run_codex_create_stream_fallback  _run_codex_stream
_safe_print                       _sanitize_api_messages
_sanitize_tool_call_arguments     _sanitize_tool_calls_for_strict_api
_save_session_log                 _save_trajectory
_should_emit_quiet_tool_messages  _should_sanitize_tool_calls
_should_start_quiet_spinner       _should_treat_stop_as_truncated
_spawn_background_review          _split_responses_tool_id
_strip_think_blocks               _summarize_api_error
_summarize_background_review_actions  _supports_reasoning_extra_body
_swap_credential                  _sweep_idle_pool_connections
_sync_external_memory_for_turn    _thread_identity
_touch_activity                   _try_activate_fallback
_try_recover_primary_transport    _try_refresh_anthropic_client_credentials
_try_refresh_codex_client_credentials  _try_refresh_copilot_client_credentials
_try_refresh_nous_client_credentials   _usage_summary_for_api_request_hook
_vprint                           _wrap_verbose

# Public
base_url (property)               chat
clear_interrupt                   close
commit_memory_session             drain
flush_memories                    get_activity_summary
get_rate_limit_state              interrupt
is_interrupted                    release_clients
reset_session_state               run_conversation
shutdown_memory_provider          steer
switch_model
```

---

*方案版本: 1.0 | 作者: BookwormPRO Project | 审查状态: 待审查*
