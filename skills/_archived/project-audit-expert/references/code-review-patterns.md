# 深度代码审查模式库

基于多个生产项目（Next.js/FastAPI/Go 全栈）实战总结的常见问题与修复方案。

## TypeScript/JavaScript 专项

### 类型安全 (来自实际项目教训)

```typescript
// ============================================
// 问题 1: useState<any> 泛滥
// 来源: ai-stats/page.tsx 中发现 6 处 useState<any>
// ============================================

// ❌ 实际项目中的坏代码
const [data, setData] = useState<any>(null);
const [report, setReport] = useState<any>({});
// eslint-disable @typescript-eslint/no-explicit-any  // 更糟: 直接禁用规则

// ✅ 修复: 定义完整接口类型
interface AiStatsData {
  totalReplies: number;
  avgQualityScore: number;
  channels: ChannelStatusData[];
}
const [data, setData] = useState<AiStatsData | null>(null);

// ============================================
// 问题 2: JSON.parse 无类型验证
// 来源: auth-store.ts 中 atob(token) 后直接 parse
// ============================================

// ❌ 危险: 解析后未验证结构
const payload = JSON.parse(atob(parts[1]));
return payload.role; // 可能 undefined

// ✅ 使用 Zod 进行运行时验证
import { z } from 'zod';
const TokenPayload = z.object({
  sub: z.string(),
  role: z.enum(['admin', 'user']),
  exp: z.number(),
});
const result = TokenPayload.safeParse(JSON.parse(atob(parts[1])));
if (!result.success) throw new Error('Invalid token payload');
```

### 重复代码消除 (DRY)

```typescript
// ============================================
// 问题 3: 工具函数在多处重复定义
// 来源: golden/page.tsx 和 customer/[id]/page.tsx 各自定义 formatRelativeTime
// ============================================

// ❌ 多个文件各自实现相同逻辑
// golden/page.tsx:  function formatRelativeTime(date) { ... }
// customer/page.tsx: function formatRelativeTime(date) { ... }

// ✅ 提取到共享模块
// lib/format.ts
export function formatRelativeTime(date: string | Date | null): string {
  if (!date) return '-';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '-';
  // ... 统一实现
}
```

### 错误处理

```typescript
// ============================================
// 问题 4: fetch 后未检查 response.ok
// 来源: mybioweb 项目 lib/api.ts
// ============================================

// ❌ 缺少响应状态检查
const data = await fetch(url);

// ✅ 完整错误处理链
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.code, error.message);
    }
    return response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'NETWORK_ERROR', '网络错误');
  }
}
```

## Python/FastAPI 专项

### 异常处理收窄

```python
# ============================================
# 问题 5: except Exception 吞掉所有错误
# 来源: auto_delivery_service.py:184
# ============================================

# ❌ 过宽的异常捕获
try:
    result = process_delivery(data)
except Exception:
    return None  # 数据库错误也被静默吞掉

# ✅ 分类处理异常
from sqlalchemy.exc import SQLAlchemyError

try:
    result = process_delivery(data)
except (ValueError, KeyError) as e:
    logger.warning(f"数据格式异常: {e}")
    return None
except SQLAlchemyError as e:
    logger.error(f"数据库错误: {e}", exc_info=True)
    raise  # DB 错误必须向上传播
```

### 数据库字段持久化

```python
# ============================================
# 问题 6: 内存中修改字段但从未持久化到 DB
# 来源: example_selector.py:337 设置 last_used_at 但 batch update 只更新 times_used
# ============================================

# ❌ 字段赋值但未包含在 batch update 中
golden.last_used_at = now_cst()  # 内存中修改
# batch update 只更新 times_used, last_used_at 被遗漏

# ✅ batch update 必须包含所有修改字段
stmt = (
    sa_update(GoldenExample)
    .where(GoldenExample.id == golden.id)
    .values(
        times_used=golden.times_used + 1,
        last_used_at=now_cst(),  # 同步持久化
    )
)
await session.execute(stmt)
```

### 数据库约束完整性

```python
# ============================================
# 问题 7: 缺少唯一约束，依赖应用层去重
# 来源: models/example_usage.py
# ============================================

# ❌ 无数据库层面约束
class ExampleUsage(Base):
    conversation_id = Column(Integer)
    golden_example_id = Column(Integer)

# ✅ 添加唯一约束 + 复合索引
class ExampleUsage(Base):
    conversation_id = Column(Integer, nullable=False)
    golden_example_id = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('conversation_id', 'golden_example_id',
                         name='uq_conv_golden'),
        Index('ix_conv_golden', 'conversation_id', 'golden_example_id'),
    )
```

## Go/Gin 专项

```go
// 检查清单:
// - [ ] error 是否全部处理（不允许 _ 忽略 error）
// - [ ] goroutine 是否有 recover 保护
// - [ ] 数据库连接是否使用连接池
// - [ ] GORM 查询是否避免了 N+1
// - [ ] context 是否正确传递和取消
```
