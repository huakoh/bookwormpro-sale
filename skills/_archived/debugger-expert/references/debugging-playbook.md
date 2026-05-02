# 系统化调试方法论与工具链 (Debugging Playbook)

> 本文档为 debugger-expert 技能的核心参考，涵盖调试方法论、心智模型和主流语言工具链。

---

## 一、科学调试方法论

### 1.1 假设-验证循环 (Scientific Debugging)

调试的本质是科学实验：观察现象 -> 形成假设 -> 设计实验 -> 验证结果。

```
┌─────────────┐
│  观察现象     │  收集错误信息、日志、堆栈
└──────┬──────┘
       ▼
┌─────────────┐
│  形成假设     │  基于经验和证据提出可能原因
└──────┬──────┘
       ▼
┌─────────────┐
│  设计实验     │  构造能验证或推翻假设的测试
└──────┬──────┘
       ▼
┌─────────────┐
│  验证结果     │  假设成立 → 修复；假设失败 → 新假设
└──────┬──────┘
       ▼
┌─────────────┐
│  根因分析     │  找到根本原因，而非表面症状
└─────────────┘
```

**关键原则**：
- 每次只改一个变量，否则无法确定哪个改动有效
- 记录每次尝试和结果，避免重复无用操作
- 不要猜测，用证据说话

### 1.2 二分法定位 (Binary Search Debugging)

适用于"某处出错但不知道在哪"的场景：

```bash
# Git bisect 自动定位引入 Bug 的 commit
git bisect start
git bisect bad                  # 当前版本有问题
git bisect good v1.2.0          # 这个版本没问题
# Git 会自动 checkout 中间的 commit，你只需测试并标记
git bisect good                 # 或 git bisect bad
# 最终定位到引入 Bug 的精确 commit
git bisect reset                # 结束 bisect
```

**代码中的二分法**：
- 在代码中间插入日志，确认上半段还是下半段出问题
- 注释掉一半代码，逐步缩小范围
- 对于数据问题，检查中间步骤的数据是否正确

### 1.3 最小复现用例 (Minimal Reproduction)

```
完整应用 → 剥离无关模块 → 剥离无关依赖 → 最小可复现代码
```

**构建步骤**：
1. 在全新环境中尝试复现
2. 逐步去除无关代码，直到去掉任何一行都无法复现
3. 记录精确的复现步骤（环境、输入、操作序列）

---

## 二、调试心智模型

### 2.1 自上而下 (Top-Down)

从用户可见的症状出发，沿调用链向下追踪：

```
用户看到的错误
  → 前端组件
    → API 调用
      → 后端 Handler
        → Service 层
          → 数据库查询
```

**适用场景**：错误信息明确，能清晰追踪调用链。

### 2.2 自下而上 (Bottom-Up)

从底层日志或异常出发，向上追溯调用者：

```
数据库报错 connection refused
  → ORM 连接池状态
    → 服务配置
      → 环境变量
        → Docker Compose 配置
```

**适用场景**：底层有明确的报错日志，需要理解为什么被触发。

### 2.3 差异对比法 (Differential Debugging)

比较"正常"和"异常"两种情况的差异：

```bash
# 对比两个环境的配置差异
diff <(ssh prod "env | sort") <(ssh staging "env | sort")

# 对比两个请求的差异
diff response_good.json response_bad.json

# 对比两个 commit 的代码差异
git diff abc123 def456 -- src/
```

### 2.4 回退法 (Rollback Debugging)

当问题突然出现时，回退到已知正常状态：

```bash
# 回退到上一个正常的 commit
git stash               # 保存当前改动
git checkout <good-commit>
# 测试是否正常
# 然后逐个引入改动，找到引入问题的变更
```

---

## 三、JavaScript/TypeScript 调试工具链

### 3.1 Chrome DevTools

#### Sources 面板
```javascript
// 代码中插入断点
debugger;  // 浏览器会在此暂停

// 条件断点（在 DevTools 中右键行号设置）
// 条件示例：item.id === 42

// Logpoints（不暂停，只输出日志）
// 右键行号 → Add logpoint → 输入: "value is", myVar
```

#### Network 面板
```
关键检查项：
- Status: 检查 HTTP 状态码
- Timing: 查看各阶段耗时（DNS, TCP, TTFB, Content Download）
- Headers: 验证请求头/响应头（Content-Type, Authorization, CORS headers）
- Preview/Response: 检查实际响应数据
- 右键 → Copy as cURL: 在终端中重现请求
```

#### Performance 面板
```
录制步骤：
1. 点击录制按钮
2. 执行要分析的操作
3. 停止录制
4. 检查 Main 线程火焰图
5. 关注长任务（超过 50ms 的红色标记）
```

#### Memory 面板
```
内存泄漏排查：
1. 拍摄 Heap Snapshot（快照1）
2. 执行可疑操作
3. 拍摄 Heap Snapshot（快照2）
4. 选择 "Comparison" 视图，对比两个快照
5. 按 "Size Delta" 排序，查看增长最多的对象
```

### 3.2 VS Code 调试配置

```jsonc
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    // Node.js 应用调试
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Node App",
      "program": "${workspaceFolder}/src/index.ts",
      "preLaunchTask": "tsc: build",
      "outFiles": ["${workspaceFolder}/dist/**/*.js"],
      "console": "integratedTerminal"
    },
    // Next.js 全栈调试
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Next.js",
      "runtimeExecutable": "pnpm",
      "runtimeArgs": ["dev"],
      "port": 9230,
      "console": "integratedTerminal",
      "serverReadyAction": {
        "pattern": "- Local:.+(https?://.+)",
        "uriFormat": "%s",
        "action": "debugWithChrome"
      }
    },
    // 附加到已运行的进程
    {
      "type": "node",
      "request": "attach",
      "name": "Attach to Process",
      "port": 9229,
      "restart": true
    }
  ]
}
```

#### 条件断点与 Logpoints
```
VS Code 中：
- 条件断点：右键行号 → Add Conditional Breakpoint → 输入条件表达式
- Hit Count 断点：右键 → Add Conditional Breakpoint → Hit Count → 输入次数
- Logpoints：右键行号 → Add Logpoint → 使用 {} 插入表达式
  示例: "User {user.name} logged in, role: {user.role}"
```

### 3.3 Node.js 调试

```bash
# 启动调试模式
node --inspect src/server.js          # 默认 9229 端口
node --inspect-brk src/server.js      # 在第一行暂停

# 使用 ndb（更好的 Node 调试器）
npx ndb node src/server.js

# 内存快照对比
node --expose-gc -e "
  global.gc();
  const before = process.memoryUsage();
  // ... 执行操作 ...
  global.gc();
  const after = process.memoryUsage();
  console.log('Heap used delta:', after.heapUsed - before.heapUsed);
"

# 生成 Heap Snapshot
node -e "
  const v8 = require('v8');
  const fs = require('fs');
  const snapshot = v8.writeHeapSnapshot();
  console.log('Snapshot written to:', snapshot);
"
```

---

## 四、Python 调试工具链

### 4.1 pdb/ipdb 常用命令速查

```python
# 在代码中设置断点
import pdb; pdb.set_trace()      # 标准 pdb
import ipdb; ipdb.set_trace()    # 增强版（支持语法高亮、Tab 补全）
breakpoint()                      # Python 3.7+ 推荐写法
```

```
常用命令：
  n (next)        - 执行下一行（不进入函数）
  s (step)        - 单步执行（进入函数）
  c (continue)    - 继续执行到下一个断点
  r (return)      - 执行到当前函数返回
  l (list)        - 显示当前代码上下文
  ll (longlist)   - 显示整个函数代码
  p expr          - 打印表达式值
  pp expr         - 美观打印表达式值
  w (where)       - 显示调用堆栈
  u (up)          - 向上移动堆栈帧
  d (down)        - 向下移动堆栈帧
  b 42            - 在第 42 行设置断点
  b func_name     - 在函数入口设置断点
  b 42, x > 10   - 条件断点：仅当 x > 10 时触发
  cl (clear)      - 清除所有断点
  q (quit)        - 退出调试器
```

### 4.2 debugpy (VS Code 远程调试)

```python
# 在代码中嵌入调试服务器
import debugpy
debugpy.listen(("0.0.0.0", 5678))
print("等待调试器连接...")
debugpy.wait_for_client()  # 阻塞直到 VS Code 连接
```

```jsonc
// .vscode/launch.json - 远程附加
{
  "type": "debugpy",
  "request": "attach",
  "name": "Attach to Remote Python",
  "connect": { "host": "localhost", "port": 5678 },
  "pathMappings": [
    {
      "localRoot": "${workspaceFolder}",
      "remoteRoot": "/app"       // Docker 容器中的路径
    }
  ]
}
```

### 4.3 内存分析

```python
# tracemalloc - 内置内存跟踪
import tracemalloc
tracemalloc.start()

# ... 执行可疑代码 ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
print("[ 内存分配 Top 10 ]")
for stat in top_stats[:10]:
    print(stat)

# objgraph - 对象引用图
import objgraph
objgraph.show_most_common_types(limit=20)    # 最多的对象类型
objgraph.show_growth(limit=10)                # 对象增长情况
objgraph.show_backrefs(obj, max_depth=5,      # 谁引用了这个对象
                       filename='refs.png')
```

---

## 五、Go 调试工具链

### 5.1 Delve (dlv) 常用命令

```bash
# 启动调试
dlv debug ./cmd/server                # 编译并调试
dlv debug ./cmd/server -- --port 8080 # 带参数
dlv attach <pid>                      # 附加到运行中的进程
dlv test ./pkg/service                # 调试测试

# 远程调试（服务器端）
dlv debug --headless --listen=:2345 --api-version=2 ./cmd/server
# 本地连接
dlv connect localhost:2345
```

```
常用命令：
  break (b) main.go:42      - 设置断点
  break funcName             - 在函数入口设置断点
  condition <id> i == 5      - 条件断点
  continue (c)               - 继续执行
  next (n)                   - 下一行
  step (s)                   - 单步进入
  stepout (so)               - 跳出当前函数
  print (p) variable         - 打印变量
  locals                     - 显示所有局部变量
  goroutines (grs)           - 列出所有 goroutine
  goroutine <id>             - 切换到指定 goroutine
  stack (bt)                 - 显示调用堆栈
```

```jsonc
// .vscode/launch.json - Go 调试
{
  "type": "go",
  "request": "launch",
  "name": "Debug Go Server",
  "program": "${workspaceFolder}/cmd/server",
  "args": ["--config", "config.dev.yaml"],
  "env": { "GO_ENV": "development" }
}
```

### 5.2 pprof 性能分析

```go
// 在应用中启用 pprof
import _ "net/http/pprof"
// 确保有 HTTP 服务在运行，pprof 会注册到 DefaultServeMux

// 或手动注册到自定义 mux
import "net/http/pprof"
mux.HandleFunc("/debug/pprof/", pprof.Index)
mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
mux.HandleFunc("/debug/pprof/heap", pprof.Handler("heap").ServeHTTP)
```

```bash
# CPU 分析（采集 30 秒）
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# 内存分析
go tool pprof http://localhost:6060/debug/pprof/heap

# Goroutine 分析（排查泄漏）
go tool pprof http://localhost:6060/debug/pprof/goroutine

# 交互式命令
(pprof) top 20          # 热点函数 Top 20
(pprof) list funcName   # 查看函数逐行消耗
(pprof) web             # 生成调用图并在浏览器打开
(pprof) flame           # 生成火焰图
```

### 5.3 Race Detector

```bash
# 编译和运行时检测数据竞争
go run -race ./cmd/server
go test -race ./...
go build -race -o server ./cmd/server

# 输出示例：
# WARNING: DATA RACE
# Goroutine 7 (running) at:
#   main.go:42 +0x1a8
# Previous write at:
#   main.go:38 +0x130
# Goroutine 6 (running) at:
#   main.go:38 +0x130
```

**常见修复方式**：
- 使用 `sync.Mutex` 或 `sync.RWMutex` 保护共享数据
- 使用 `channel` 代替共享内存
- 使用 `sync/atomic` 处理简单的计数器
- 使用 `sync.Map` 代替普通 map 的并发读写

---

## 六、日志分析技巧

### 6.1 结构化日志

```typescript
// Node.js - 使用 pino 结构化日志
import pino from 'pino';
const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
});

logger.info({ userId: 123, action: 'login', ip: '10.0.0.1' }, '用户登录成功');
// 输出: {"level":"info","userId":123,"action":"login","ip":"10.0.0.1","msg":"用户登录成功"}
```

```python
# Python - 使用 structlog 结构化日志
import structlog
logger = structlog.get_logger()
logger.info("用户登录", user_id=123, action="login", ip="10.0.0.1")
```

### 6.2 日志级别策略

```
ERROR  - 需要立即处理的错误（数据库挂了、支付失败）
WARN   - 可恢复但异常的情况（重试成功、降级处理）
INFO   - 重要业务事件（用户注册、订单创建）
DEBUG  - 开发调试信息（函数入参、中间状态）
TRACE  - 极细粒度追踪（循环内每步状态）
```

### 6.3 关联 ID 追踪 (Correlation ID)

```typescript
// Express 中间件 - 为每个请求生成关联 ID
import { randomUUID } from 'crypto';

app.use((req, res, next) => {
  req.correlationId = req.headers['x-correlation-id'] || randomUUID();
  res.setHeader('x-correlation-id', req.correlationId);
  // 注入到日志上下文
  req.logger = logger.child({ correlationId: req.correlationId });
  next();
});

// 在所有后续日志中自动携带 correlationId
req.logger.info({ userId: user.id }, '处理用户请求');
```

---

## 七、生产环境调试

### 7.1 只读调试原则

```
生产环境调试铁律：
1. 绝不修改生产数据
2. 绝不在生产环境执行写操作
3. 使用只读副本进行数据查询
4. 优先分析日志和监控数据
5. 必要时使用 feature flag 控制变更
```

### 7.2 Feature Flag 回退

```typescript
// 使用 feature flag 安全回退
if (featureFlags.isEnabled('new-payment-flow')) {
  return newPaymentHandler(req);
} else {
  return legacyPaymentHandler(req);  // 随时可回退
}

// 关闭 flag 不需要部署，立即生效
```

### 7.3 蓝绿切换排查

```bash
# 检查当前活跃环境
kubectl get service myapp -o jsonpath='{.spec.selector.version}'

# 流量切换到旧版本
kubectl patch service myapp -p '{"spec":{"selector":{"version":"blue"}}}'

# 确认切换成功
kubectl get endpoints myapp
```

### 7.4 生产日志快速过滤

```bash
# 按错误级别过滤
kubectl logs deploy/myapp --since=1h | jq 'select(.level == "error")'

# 按关联 ID 追踪一个请求的完整链路
kubectl logs deploy/myapp --since=1h | jq 'select(.correlationId == "abc-123")'

# 按用户 ID 过滤
kubectl logs deploy/myapp --since=1h | jq 'select(.userId == 42)'

# Docker Compose 环境
docker compose logs --since=1h app | grep "ERROR"
docker compose logs -f app 2>&1 | jq 'select(.level == "error")'
```
