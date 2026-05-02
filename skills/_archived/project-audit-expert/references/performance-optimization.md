# 性能优化与修复参考

## 数据库性能

```python
# ============================================
# 问题: N+1 查询
# 来源: 多个项目中均出现
# ============================================

# ❌ N+1: 循环内单独查询
for user in users:
    orders = db.query(Order).filter(Order.user_id == user.id).all()

# ✅ 批量查询 + 内存关联
user_ids = [u.id for u in users]
orders = db.query(Order).filter(Order.user_id.in_(user_ids)).all()
order_map = defaultdict(list)
for order in orders:
    order_map[order.user_id].append(order)

# ✅ 或使用 ORM 预加载
users = db.query(User).options(selectinload(User.orders)).all()
```

```sql
-- 索引优化检查
-- 检查慢查询是否缺少索引
EXPLAIN ANALYZE SELECT * FROM messages
WHERE conversation_id = 123 AND created_at > '2026-01-01';

-- 建议: 复合索引
CREATE INDEX ix_msg_conv_created ON messages(conversation_id, created_at);
```

## 前端性能

```typescript
// ============================================
// 问题: 大量组件未做 lazy 加载
// 来源: novo 项目 31 个页面组件改为 React.lazy()
// ============================================

// ❌ 同步导入所有页面
import DashboardPage from './pages/Dashboard';
import SettingsPage from './pages/Settings';

// ✅ 路由级别懒加载
const DashboardPage = React.lazy(() => import('./pages/Dashboard'));
const SettingsPage = React.lazy(() => import('./pages/Settings'));

// ✅ Next.js App Router 已自动路由级分割
// 但动态组件仍需手动:
import dynamic from 'next/dynamic';
const HeavyChart = dynamic(() => import('@/components/HeavyChart'), {
  loading: () => <Skeleton />,
  ssr: false,
});
```

## 内存与运行时

```yaml
检查项:
  - PM2 Heap 使用率: >90% 需要排查内存泄漏
  - 重启次数: 频繁重启说明有未捕获异常
  - Event Listener 泄漏: useEffect 清理函数是否完整
  - WebSocket 连接: 断线重连是否正确释放旧连接
  - 定时器: setInterval/setTimeout 是否在组件卸载时清理
```

## Docker/部署优化

```yaml
检查项:
  - 镜像大小: 是否使用多阶段构建
  - 构建缓存: Dockerfile 指令顺序是否利于缓存
  - 健康检查: HEALTHCHECK 是否配置
  - 日志轮转: 容器日志是否有大小限制
  - 资源限制: deploy.resources.limits 是否配置
```
