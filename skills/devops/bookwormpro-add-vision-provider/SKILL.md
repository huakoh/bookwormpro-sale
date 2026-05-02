---
name: bookwormpro-add-vision-provider
description: 为 BookwormPRO 新增多模态视觉提供商。当用户需要添加支持视觉（多模态）的 API 提供商（如 Qwen-VL、Gemini、Claude Vision）时使用。覆盖模型注册、vision 自动检测链、API 端点配置。
category: devops
---

# 为 BookwormPRO 新增视觉提供商

## 触发条件
- 用户要添加支持图片/多模态的 API（Qwen-VL、Gemini Vision、Claude Vision 等）
- 用户报告 `vision_analyze` 不工作
- 用户说"加个多模态 API"

## 集成步骤

### 1. 确认 API 端点格式
先用 `OpenAI` 客户端直接测试：
```python
from openai import OpenAI
client = OpenAI(api_key="sk-xxx", base_url="https://api.example.com/v1")
r = client.chat.completions.create(
    model="model-name",
    messages=[{"role":"user", "content":[
        {"type":"text", "text":"What color?"},
        {"type":"image_url", "image_url":{"url":"data:image/png;base64,..."}}
    ]}]
)
```
确认 `image_url` 格式被接受（失败则试其他格式如 `image`）。

### 2. 注册模型到目录
编辑 `bwm_cli/models.py`，在对应 provider 的列表中加模型名：
```python
"alibaba": [
    "qwen-vl-max",       # 新增
    "qwen-vl-plus",      # 新增
    ...
],
```

### 3. 注册到 Vision 自动检测链
编辑 `agent/auxiliary_client.py`：

**a. 添加模型映射** (`_PROVIDER_VISION_MODELS`)：
```python
_PROVIDER_VISION_MODELS: Dict[str, str] = {
    "alibaba": "qwen-vl-max",   # provider → default vision model
    ...
}
```

**b. 加入自动检测顺序** (`_VISION_AUTO_PROVIDER_ORDER`)：
```python
_VISION_AUTO_PROVIDER_ORDER = (
    "alibaba",          # 新增，优先级可调
    "openrouter",
    "bookwormpro",
)
```

**c. 添加后端处理函数** (在 `_resolve_strict_vision_backend` 中)：
```python
if provider == "alibaba":
    _model = resolved_model.replace("alibaba/", "") if resolved_model else "qwen-vl-max"
    return _try_alibaba_vision(model_override=_model)
```

**d. 实现 `_try_<provider>_vision()` 函数**：
```python
def _try_alibaba_vision(model_override: str = None):
    _model = model_override or "qwen-vl-max"
    client, model = resolve_provider_client("alibaba", _model)
    if client is None:
        return None, None
    return client, model
```

**e. ⚠️ 关键修复：`_finalize` 的 model 优先级**：在 `resolve_vision_provider_client` 的 `_finalize` 闭包中，**必须**将：
```python
final_model = resolved_model or default_model
```
改为：
```python
final_model = default_model or resolved_model
```
原因：`resolved_model` 来自调用者（可能带 `alibaba/qwen-vl-max` 前缀），`default_model` 来自 `_try_*_vision()`（已剥离前缀的 canonical 名如 `qwen-vl-max`）。如果 `resolved_model` 优先，前缀 model 会直接传给 DashScope → 404 model_not_found。**这是最常见的静默失败根因**。

### 4. 添加 Provider 推断
编辑 `tools/vision_tools.py`，在 model 设置后提取 provider：
```python
if model:
    call_kwargs["model"] = model
    if "/" in model and not model.startswith("openrouter/"):
        call_kwargs["provider"] = model.split("/")[0]
```

### 5. 配置 API Key + 端点
用户 `~/.bookwormpro/.env`：
```bash
PROVIDER_API_KEY=sk-xxx
PROVIDER_BASE_URL=https://api.example.com/v1
```

## 常见陷阱

### 1. Model 前缀剥离
BookwormPRO 用 `provider/model` 前缀（如 `alibaba/qwen-vl-max`），但直接 provider API 不接受前缀。三步修复：
1. `_try_alibaba_vision()` 接收 `model_override` 参数，用 `.replace("alibaba/", "")` 剥离
2. `_resolve_strict_vision_backend` 签名加 `resolved_model` 参数并传递给 `_try_*`
3. **关键**：`_finalize()` 中 `final_model = resolved_model or default_model` 必须改为 `final_model = default_model or resolved_model`，否则前缀 model 永远覆盖后端返回的正确 model 名

### 2. China vs 国际端点
阿里云 DashScope：国内 key 用 `dashscope.aliyuncs.com`，国际 key 用 `dashscope-intl.aliyuncs.com`。先分别测试确认。设置 `DASHSCOPE_BASE_URL` env var。

### 3. Async vs Sync 路径分离调试
遇到"sync 通 async 不通"时，分离测试每一步：
```python
# Step 1: 直接 sync client（最底层）
client.chat.completions.create(model=..., messages=...)

# Step 2: resolve_vision_provider_client(async_mode=False) + sync call

# Step 3: resolve_vision_provider_client(async_mode=True) + async call

# Step 4: async_call_llm(task='vision', provider='alibaba', ...) + async call

# Step 5: vision_analyze_tool（顶层）
```
每一步通过才进下一步。不要 jump 到结论。

### 4. Auto 检测优先走主 Provider（最常见根因）
`vision_analyze_tool` 不传 `provider` 时，auto 路径先尝试 `_read_main_provider()`（如 DeepSeek）。DeepSeek 无 `_PROVIDER_VISION_MODELS` 映射，但 `resolve_provider_client` 仍成功创建 client → 返回 → 实际 API 调用失败（`image_url` 不支持）。**解决**：
1. `vision_analyze_tool` 从 model 前缀推断 provider：`call_kwargs["provider"] = model.split("/")[0]`
2. `_handle_vision_analyze` 默认 model 设为 `alibaba/qwen-vl-max`（而非 None）

### 5. .env 加载时机
`python -c` 测试时 .env 不自动加载，手动 `load_dotenv(get_env_path())`。

### 6. Windows CRLF 导致 patch 失败
用 `patch` 工具修改 `.py` 文件后验证失败 → 用 `sed -i` 或 `write_file` 绕过。Git Bash heredoc `<< 'EOF'` 被 shell 解释为后台 `&` → 写 `.py` 脚本文件再执行。

### 8. 非主 Provider 需加入 Aggregator 链（易遗漏）
当用户主 provider（如 deepseek）不支持 vision，需要 fallback 到别的 provider（如 alibaba）时，
仅在 `_PROVIDER_VISION_MODELS` 中添加映射**不够**。必须同时：
1. 将 provider 加入 `_VISION_AUTO_PROVIDER_ORDER`（作为 aggregator 候选）
2. 在 `_resolve_strict_vision_backend` 中添加对应 case
3. 实现 `_try_<provider>_vision()` 函数
4. 更新 config.yaml 的 `auxiliary.vision.model` 为该 provider 的正确 prefix model

**完整链路**: main provider(deepseek) → skip(non-vision) → aggregator 链(alibaba→openrouter→bookwormpro)

### 9. config.yaml 配合修改
`auxiliary.vision.model` 必须设置为正确的 provider-prefix 模型名，如 `alibaba/qwen-vl-max`。
旧值如 `qwen/qwen3.6-plus` 是非 vision 模型，会导致静默失败。

### 10. E2E 验证图片最小尺寸
DashScope `qwen-vl-max` 要求图片 ≥ 10x10 px。测试时用 16x16 以上 PNG。

### 11. `_` 变量名冲突（i18n 相关）
文件 import `from bwm_cli.i18n import _` 后，如果函数内有 `_, unused = func()` 的丢弃变量，会遮蔽翻译函数 → `TypeError: 'list' object is not callable`。修复：重命名丢弃变量为 `_avail`。

### 8. Windows heredoc `<< 'EOF'` 被 shell 误解释
Git Bash 把 `<< 'EOF'` 解释为后台 `&` 符导致命令挂起。**解决**：用 `write_file` 写 `.py` 脚本文件再 `python script.py` 执行，或直接用 `python -c` 单行。

### 9. .po 文件 `left_content = "\n"` 换行符混乱
用 Python 写含 `\n` 转义序列的文件时，`"\\n"` 在 Python 字符串中变成 `\n`（换行符），写入 .py 文件时导致源码字符串字面量断裂。**解决**：用二进制替换 `bytes([0x22, 0x0a, 0x22])` → `bytes([0x22, 0x5c, 0x6e, 0x22])`。
- [ ] 同步客户端能识别颜色：`resolve_vision_provider_client(provider='alibaba', async_mode=False)` → 直接 call
- [ ] `_build_call_kwargs` 输出 kwargs 检查 model 名无前缀
- [ ] 异步客户端能识别颜色：`async_mode=True` → 直接 async call
- [ ] `async_call_llm(task='vision', provider='alibaba', model=...)` 端到端通过
- [ ] `_handle_vision_analyze` 不传 model 时能自动回退到 `alibaba/qwen-vl-max`
- [ ] `vision_analyze_tool` 端到端通过（带 `model=alibaba/qwen-vl-max`）
- [ ] 中文回复正常（Qwen 系列天然支持）
- [ ] `py_compile.compile` 语法检查：`agent/auxiliary_client.py` + `tools/vision_tools.py` + `bwm_cli/models.py`
- [ ] git diff 确认无意外改动；Windows CRLF warning 可忽略
- [ ] 跑 `test_auxiliary_named_custom_providers.py`（26 tests）确认无回归
- [ ] **注意**：`test_vision_tools.py` 中 `test_tilde_path_expanded_to_local_file` 和 `test_check_requirements_accepts_codex_auth` 在 Windows 上预失败——非本次引入，可忽略
