# 常见错误速查与修复方案 (Common Errors Reference)

> 格式：错误信息 -> 常见原因 -> 修复命令/代码

---

## 一、CORS 错误

### 错误信息
```
Access to fetch at 'http://api.example.com' from origin 'http://localhost:3000'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
```

### 常见原因
- 后端未配置 CORS 响应头
- 预检请求 (OPTIONS) 未正确处理
- 允许的 Origin 列表遗漏了前端地址
- Nginx 反代层未透传 CORS 头

### 修复方案

**Nginx 配置**：
```nginx
server {
    location /api/ {
        # 处理预检请求
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '$http_origin';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type';
            add_header 'Access-Control-Allow-Credentials' 'true';
            add_header 'Access-Control-Max-Age' 86400;
            return 204;
        }
        add_header 'Access-Control-Allow-Origin' '$http_origin' always;
        add_header 'Access-Control-Allow-Credentials' 'true' always;
        proxy_pass http://backend:8000;
    }
}
```

**Express 配置**：
```typescript
import cors from 'cors';
app.use(cors({
  origin: ['http://localhost:3000', 'https://yourdomain.com'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));
```

**FastAPI 配置**：
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 二、React Hydration 错误

### 错误信息
```
Hydration failed because the initial UI does not match what was rendered on the server.
```

### 常见触发场景
- 使用 `Date.now()` 或 `Math.random()` 等在服务端和客户端产生不同值的表达式
- 根据 `window` / `localStorage` 条件渲染内容
- 嵌套了无效的 HTML 结构（如 `<p>` 内嵌 `<div>`）
- 浏览器扩展注入了额外的 DOM 节点

### 修复方案

```tsx
// 方案1：使用 useEffect 延迟客户端渲染
function ClientOnlyTime() {
  const [time, setTime] = useState<string>('');
  useEffect(() => {
    setTime(new Date().toLocaleString());
  }, []);
  return <span>{time || '--'}</span>;  // 服务端渲染占位符
}

// 方案2：使用 suppressHydrationWarning
<time dateTime={dateString} suppressHydrationWarning>
  {formattedDate}
</time>

// 方案3：使用 next/dynamic 禁用 SSR
import dynamic from 'next/dynamic';
const BrowserOnlyChart = dynamic(() => import('./Chart'), { ssr: false });
```

---

## 三、Next.js 常见错误

### 3.1 "use client" 边界错误

```
Error: You're importing a component that needs useState. It only works in a
Client Component but none of its parents are marked with "use client".
```

**修复**：在使用 React hooks 的组件文件顶部添加 `"use client";`

```tsx
"use client";  // 必须是文件的第一行
import { useState } from 'react';
export default function Counter() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

### 3.2 Server/Client 组件混用

```
Error: Functions cannot be passed directly to Client Components unless you
explicitly expose it by marking it with "use server".
```

**修复**：不要将函数 prop 从 Server Component 传给 Client Component，改用 Server Actions：

```tsx
// app/actions.ts
"use server";
export async function submitForm(data: FormData) {
  // 服务端逻辑
}

// app/page.tsx (Server Component)
import { submitForm } from './actions';
import ClientForm from './ClientForm';
export default function Page() {
  return <ClientForm action={submitForm} />;
}
```

### 3.3 Dynamic Import 问题

```
Error: Element type is invalid: expected a string or a class/function but got: undefined
```

**修复**：确认 dynamic import 的组件使用了 default export：

```tsx
// 确保组件使用 default export
const DynamicComponent = dynamic(() => import('./MyComponent'), {
  loading: () => <p>加载中...</p>,
  ssr: false,  // 如果组件依赖浏览器 API
});
```

---

## 四、Prisma/ORM 错误

### 4.1 Connection Pool Exhaustion

```
Error: Timed out fetching a new connection from the connection pool.
```

**修复**：
```prisma
// schema.prisma - 调整连接池
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// 连接字符串中设置池大小
// DATABASE_URL="postgresql://user:pass@host:5432/db?connection_limit=20&pool_timeout=10"
```

```typescript
// 确保 Prisma Client 为单例
// lib/prisma.ts
import { PrismaClient } from '@prisma/client';
const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };
export const prisma = globalForPrisma.prisma || new PrismaClient();
if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
```

### 4.2 Migration Drift

```
Error: The current database is not managed by Prisma Migrate.
```

**修复**：
```bash
# 重置迁移历史（开发环境）
npx prisma migrate reset

# 将现有数据库与 schema 对齐
npx prisma db pull          # 从数据库生成 schema
npx prisma migrate dev      # 生成新迁移
```

### 4.3 类型不匹配

```
Error: Argument of type 'string' is not assignable to parameter of type 'number'.
```

**修复**：运行 `npx prisma generate` 重新生成类型，确保 schema 和代码类型一致。

---

## 五、PostgreSQL 错误

### 5.1 连接超时

```
Error: connect ETIMEDOUT / Connection refused
```

**排查步骤**：
```bash
# 检查 PostgreSQL 是否在运行
sudo systemctl status postgresql
# 或 Docker 环境
docker ps | grep postgres

# 检查监听端口
ss -tlnp | grep 5432

# 检查 pg_hba.conf 是否允许远程连接
# host  all  all  0.0.0.0/0  md5

# 检查 postgresql.conf
# listen_addresses = '*'

# 测试连接
psql -h localhost -U myuser -d mydb -c "SELECT 1;"
```

### 5.2 死锁检测

```
ERROR: deadlock detected
DETAIL: Process 1234 waits for ShareLock on transaction 5678;
blocked by process 9012.
```

**排查与修复**：
```sql
-- 查看当前锁等待
SELECT pid, usename, query, state, wait_event_type, wait_event
FROM pg_stat_activity
WHERE state = 'active' AND wait_event IS NOT NULL;

-- 查看锁冲突
SELECT blocked.pid AS blocked_pid,
       blocking.pid AS blocking_pid,
       blocked.query AS blocked_query
FROM pg_catalog.pg_locks blocked
JOIN pg_catalog.pg_locks blocking
  ON blocking.locktype = blocked.locktype
  AND blocking.relation = blocked.relation
  AND blocking.pid != blocked.pid
WHERE NOT blocked.granted;

-- 终止阻塞进程（谨慎使用）
SELECT pg_terminate_backend(<blocking_pid>);
```

### 5.3 索引失效

**常见原因**：对列使用了函数、隐式类型转换、LIKE '%前缀'

```sql
-- 错误：函数导致索引失效
SELECT * FROM users WHERE LOWER(email) = 'test@example.com';

-- 修复：创建表达式索引
CREATE INDEX idx_users_email_lower ON users (LOWER(email));

-- 检查查询是否使用了索引
EXPLAIN ANALYZE SELECT * FROM users WHERE LOWER(email) = 'test@example.com';
```

---

## 六、Docker 错误

### 6.1 端口冲突

```
Error: Bind for 0.0.0.0:3000 failed: port is already allocated
```

**修复**：
```bash
# 查找占用端口的进程
# Linux/Mac
lsof -i :3000
# Windows
netstat -ano | findstr :3000

# 停止占用端口的容器
docker ps | grep 3000
docker stop <container_id>

# 或更换端口映射
docker run -p 3001:3000 myapp
```

### 6.2 权限问题

```
Error: EACCES: permission denied
```

**修复**：
```dockerfile
# Dockerfile 中设置正确的用户
RUN addgroup --system app && adduser --system --ingroup app app
RUN chown -R app:app /app
USER app
```

### 6.3 网络不通

```
Error: Could not resolve host / Connection refused between containers
```

**修复**：
```yaml
# docker-compose.yml - 确保服务在同一网络
services:
  app:
    networks:
      - backend
    depends_on:
      - db
  db:
    networks:
      - backend
networks:
  backend:
    driver: bridge

# 容器间使用服务名访问，不要使用 localhost
# DATABASE_URL=postgresql://user:pass@db:5432/mydb
```

### 6.4 构建缓存失效

```bash
# 强制重新构建（不使用缓存）
docker compose build --no-cache

# 清理悬空镜像和构建缓存
docker system prune -f
docker builder prune -f

# 优化 Dockerfile 层顺序以利用缓存
# 把不常变化的放前面（安装依赖），常变化的放后面（复制代码）
```

---

## 七、Git 错误

### 7.1 Merge Conflict

```
CONFLICT (content): Merge conflict in src/app.ts
Automatic merge failed; fix conflicts and then commit the result.
```

**修复**：
```bash
# 查看冲突文件
git status

# 手动编辑冲突文件，选择保留的代码
# 删除 <<<<<<<, =======, >>>>>>> 标记

# 标记为已解决
git add src/app.ts
git commit -m "resolve merge conflict in app.ts"

# 或放弃合并
git merge --abort
```

### 7.2 Detached HEAD

```
You are in 'detached HEAD' state.
```

**修复**：
```bash
# 查看当前位置
git log --oneline -5

# 创建新分支保存当前改动
git checkout -b my-fix-branch

# 或回到原来的分支
git checkout main
```

### 7.3 大文件推送失败

```
remote: error: File large-file.zip is 150.00 MB; this exceeds the 100 MB limit.
```

**修复**：
```bash
# 从历史中移除大文件
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch large-file.zip' HEAD

# 使用 Git LFS 管理大文件
git lfs install
git lfs track "*.zip"
git add .gitattributes
git add large-file.zip
git commit -m "track large files with LFS"

# 添加 .gitignore 防止再次提交
echo "*.zip" >> .gitignore
```
