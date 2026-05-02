# 代码审查清单 (Code Review Checklist)

> 按语言和框架分类的审查要点，以及 PR 审查流程 SOP。

---

## TypeScript/JavaScript 审查清单

### 类型安全

- [ ] **禁止裸 `any`**：所有 `any` 必须有注释说明原因，或替换为具体类型 / `unknown`
- [ ] **类型断言最小化**：`as` 断言需要注释理由；优先使用类型守卫 (type guard)
- [ ] **泛型正确性**：泛型参数有约束 (`extends`)，不使用无约束的 `<T>`
- [ ] **严格模式兼容**：`strictNullChecks` 下无隐式 `undefined` 访问
- [ ] **联合类型穷举**：`switch` 对联合类型使用 `exhaustive check`（never 兜底）
- [ ] **外部数据验证**：API 响应、用户输入使用 Zod / io-ts 运行时校验

```typescript
// ❌ 裸 any，无校验
function handleResponse(data: any) {
  return data.user.name;
}

// ✅ 运行时校验 + 类型推导
const ResponseSchema = z.object({
  user: z.object({ name: z.string() }),
});
function handleResponse(raw: unknown) {
  const data = ResponseSchema.parse(raw);
  return data.user.name; // 类型安全
}
```

### 异步安全

- [ ] **Promise 错误处理**：每个 `await` 都在 `try-catch` 中，或链式 `.catch()`
- [ ] **竞态条件**：组件卸载后不更新 state（AbortController / cleanup function）
- [ ] **并发控制**：批量请求使用 `Promise.allSettled` 而非 `Promise.all`（避免一个失败全部丢弃）
- [ ] **超时处理**：网络请求设置合理的 timeout
- [ ] **重试机制**：幂等操作配备指数退避 (exponential backoff)

```typescript
// ❌ 竞态条件：组件卸载后仍设置 state
useEffect(() => {
  fetchData().then(data => setData(data));
}, [id]);

// ✅ 使用 AbortController 取消
useEffect(() => {
  const controller = new AbortController();
  fetchData(id, { signal: controller.signal })
    .then(data => setData(data))
    .catch(err => {
      if (!controller.signal.aborted) reportError(err);
    });
  return () => controller.abort();
}, [id]);
```

### React 特定

- [ ] **Hooks 依赖数组**：`useEffect` / `useMemo` / `useCallback` 依赖完整且无多余项
- [ ] **key 属性**：列表渲染使用稳定唯一 key，禁止用 index 作 key（排序/删除场景）
- [ ] **不必要的 re-render**：大组件拆分，使用 `React.memo` / `useMemo` 防止子树重渲染
- [ ] **状态提升 vs 下沉**：state 放在最近的共同祖先，不过度提升到顶层
- [ ] **Context 粒度**：避免巨大 Context 导致不相关组件重渲染
- [ ] **受控 vs 非受控**：表单组件模式一致，不混用

### Next.js 特定

- [ ] **Server / Client 边界**：`'use client'` 声明仅在必要时添加，Server Component 优先
- [ ] **数据获取位置**：Server Component 中直接 fetch，不在 Client Component 中请求可在服务端获取的数据
- [ ] **缓存策略**：`fetch` 的 `cache` / `revalidate` 选项合理；理解 ISR vs SSR vs SSG
- [ ] **Metadata**：页面导出 `metadata` 或 `generateMetadata` 以支持 SEO
- [ ] **Loading / Error 边界**：`loading.tsx` 和 `error.tsx` 文件完整
- [ ] **Route Handler 安全**：API route 有鉴权中间件，参数经过校验

---

## Python 审查清单

### 类型标注

- [ ] **typing 模块使用**：函数签名完整标注参数和返回值类型
- [ ] **Pydantic model 验证**：API 入参使用 Pydantic BaseModel，字段有 `Field` 约束
- [ ] **Optional 显式标注**：可为 None 的字段使用 `Optional[T]` 或 `T | None`
- [ ] **泛型容器**：使用 `list[str]` 而非 `List`（Python 3.9+）
- [ ] **TypeAlias**：复杂类型定义使用 `TypeAlias` 提高可读性

```python
# ❌ 无类型标注，无验证
def create_user(data):
    return db.execute(f"INSERT INTO users VALUES ({data['name']})")

# ✅ Pydantic 验证 + 类型标注
class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr

async def create_user(request: CreateUserRequest) -> UserResponse:
    return await user_service.create(request)
```

### FastAPI 特定

- [ ] **依赖注入**：数据库 session、当前用户等通过 `Depends()` 注入
- [ ] **错误处理**：使用 `HTTPException` 返回合适状态码；全局异常处理器兜底
- [ ] **中间件链**：CORS、日志、限流中间件顺序正确
- [ ] **路由组织**：使用 `APIRouter` 按模块分组；路径命名 RESTful
- [ ] **响应模型**：`response_model` 显式声明，避免泄露内部字段
- [ ] **后台任务**：耗时操作使用 `BackgroundTasks` 或 Celery

### 异步安全

- [ ] **asyncio 使用**：不在 async 函数中调用同步阻塞 I/O（使用 `run_in_executor`）
- [ ] **连接池管理**：数据库连接池大小合理；async session 正确关闭
- [ ] **并发限制**：使用 `asyncio.Semaphore` 控制并发数
- [ ] **上下文变量**：使用 `contextvars` 而非全局变量传递请求级数据

---

## Go 审查清单

### 错误处理

- [ ] **error wrapping**：使用 `fmt.Errorf("context: %w", err)` 包装错误，保留链路
- [ ] **sentinel errors**：预定义错误使用 `errors.New` 并以 `Err` 前缀命名
- [ ] **自定义 error**：复杂错误实现 `Error()` 接口，携带结构化上下文
- [ ] **errors.Is / As**：错误判断使用 `errors.Is` 而非 `==`
- [ ] **不忽略错误**：`_ = someFunc()` 必须有注释说明原因

```go
// ❌ 错误被忽略，无上下文
data, _ := json.Marshal(user)
db.Exec("INSERT INTO users VALUES (?)", data)

// ✅ 错误包装，逐层传递
data, err := json.Marshal(user)
if err != nil {
    return fmt.Errorf("序列化用户数据失败: %w", err)
}
if _, err := db.Exec("INSERT INTO users VALUES (?)", data); err != nil {
    return fmt.Errorf("插入用户记录失败: %w", err)
}
```

### 并发安全

- [ ] **goroutine 泄漏**：每个 goroutine 有明确退出条件（context cancel / done channel）
- [ ] **mutex 使用**：共享数据用 `sync.Mutex` 或 `sync.RWMutex` 保护；锁粒度合理
- [ ] **channel 模式**：有缓冲 vs 无缓冲选择合理；`select` 配 `default` 或 `context.Done()`
- [ ] **sync.WaitGroup**：`Add` 在 goroutine 外调用；`Done` 使用 `defer`
- [ ] **data race**：运行 `go test -race` 检测竞态

### Gin 特定

- [ ] **中间件**：鉴权、日志、Recovery 中间件顺序正确
- [ ] **参数绑定**：使用 `ShouldBindJSON` / `ShouldBindQuery` 而非手动取值
- [ ] **响应格式**：统一使用 `c.JSON()` 返回标准格式 `{ code, message, data }`
- [ ] **路由分组**：`v1 := r.Group("/api/v1")` 按版本和模块分组
- [ ] **优雅关停**：使用 `signal.Notify` + `srv.Shutdown(ctx)` 处理退出

---

## PR 审查流程 SOP

### 审查前准备

1. **理解上下文**：阅读 PR 描述和关联 issue，明确变更目的
2. **检查 CI 状态**：确认自动化测试通过、lint 无报错
3. **浏览变更范围**：先看 file changes 概览，判断影响面
4. **本地检出**（可选）：复杂变更建议本地运行验证

### 审查步骤（按优先级）

```
Step 1: 架构审查
  - 变更是否符合系统架构设计？
  - 模块职责划分是否合理？
  - 依赖方向是否正确（不反向依赖）？

Step 2: 逻辑正确性
  - 业务逻辑是否正确？边界条件是否覆盖？
  - 数据流转是否完整？状态管理是否一致？

Step 3: 安全检查
  - 输入是否经过验证和清理？
  - 是否存在注入、XSS、CSRF 风险？
  - 敏感数据是否加密 / 脱敏？

Step 4: 性能评估
  - 是否引入 N+1 查询、大数据量循环？
  - 缓存策略是否合理？
  - 数据库索引是否匹配新查询？

Step 5: 代码风格
  - 命名是否清晰、符合团队约定？
  - 代码组织是否合理？是否过度抽象？
```

### 反馈规范

- **区分严重度**：每条反馈标注级别（Blocker / Warning / Suggestion / Nit）
- **提供替代方案**：指出问题的同时给出建议的修改代码
- **解释原因**：说明为什么需要修改，而不是只说"改一下"
- **肯定优点**：发现好的设计和实现也要给予正面反馈
- **对事不对人**：审查代码而非审查人，使用"这段代码"而非"你的代码"

---

## 严重度分类标准

| 级别 | 标记 | 定义 | 示例 | 处理要求 |
|------|------|------|------|----------|
| **Critical** | `[BLOCKER]` | 必须修复才能合并。存在正确性、安全性或数据完整性问题 | SQL 注入漏洞；竞态条件导致数据不一致；未处理的空指针异常 | 必须修复后重新审查 |
| **Warning** | `[WARNING]` | 强烈建议修复。存在性能隐患、可维护性问题或潜在 Bug | N+1 查询问题；缺少错误处理；过大的函数需要拆分 | 应当修复，可协商延期 |
| **Suggestion** | `[SUGGESTION]` | 改进建议。提升代码质量但不影响功能 | 可以使用更清晰的命名；建议提取公共方法；增加类型约束 | 可选，鼓励采纳 |
| **Nit** | `[NIT]` | 细微问题。风格偏好或微小优化 | 空行数量；import 排序；注释措辞 | 可选，不阻塞合并 |

### 审查反馈模板

```markdown
**[BLOCKER]** SQL 注入风险
- 文件: `src/services/user.ts:42`
- 问题: 用户输入直接拼接到 SQL 查询字符串
- 建议:
  ```typescript
  // 使用参数化查询
  const user = await db.query('SELECT * FROM users WHERE id = $1', [userId]);
  ```

**[SUGGESTION]** 建议提取复用函数
- 文件: `src/utils/format.ts:15-28`
- 问题: 格式化逻辑在多处重复
- 建议: 提取为 `formatCurrency()` 工具函数
```

---

## 审查自检清单（审查者使用）

### 提交审查前自检

- [ ] 是否审查了所有变更文件？
- [ ] 是否理解了变更的业务目的？
- [ ] Critical 问题是否都已标注？
- [ ] 反馈是否具有可操作性（有建议、有代码）？
- [ ] 是否检查了测试覆盖？
- [ ] 是否有正面反馈？
