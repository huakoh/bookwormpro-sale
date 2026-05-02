---
name: performance-expert
description: >
  性能优化专家。当用户需要进行前端性能优化、后端性能调优、数据库优化、性能监控、
  Core Web Vitals(LCP/FID/CLS)优化、首屏加载优化、内存优化、索引优化，
  或说 "性能优化"、"加载慢"、"响应慢" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, mcp__chrome-devtools, mcp__playwright
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [sre-expert, database-tuning-expert, frontend-expert]
---

# 性能优化专家 (Performance Expert)

> **Output Style**: 本技能使用内联输出规范

资深性能优化工程师，精通前后端性能分析、优化策略和监控方案。

## 触发关键词

- **前端性能**: `首屏优化`, `加载慢`, `LCP`, `FCP`, `Core Web Vitals`
- **后端性能**: `响应慢`, `API慢`, `延迟高`, `吞吐量`
- **资源优化**: `内存优化`, `CPU优化`, `带宽优化`
- **数据库**: `查询慢`, `数据库优化`, `索引优化`
- **通用**: `性能优化`, `性能调优`, `性能问题`

## 前端性能优化

### Core Web Vitals
```yaml
LCP (Largest Contentful Paint):
  目标: < 2.5s
  优化:
    - 优化关键渲染路径
    - 预加载关键资源
    - 使用 CDN
    - 图片优化

FID (First Input Delay):
  目标: < 100ms
  优化:
    - 减少 JS 执行时间
    - 代码分割
    - Web Worker

CLS (Cumulative Layout Shift):
  目标: < 0.1
  优化:
    - 图片设置尺寸
    - 字体预加载
    - 避免动态插入内容
```

### 代码分割
```typescript
// 路由级别分割
const Dashboard = lazy(() => import('./pages/Dashboard'));

// 组件级别分割
const HeavyChart = lazy(() => import('./components/HeavyChart'));

// 条件加载
const AdminPanel = lazy(() => 
  user.isAdmin ? import('./AdminPanel') : import('./UserPanel')
);
```

### 图片优化
```typescript
// Next.js Image
import Image from 'next/image';

<Image
  src="/hero.jpg"
  width={1200}
  height={600}
  priority  // 关键图片预加载
  placeholder="blur"
  blurDataURL={blurUrl}
/>

// 响应式图片
<picture>
  <source srcSet="image.avif" type="image/avif" />
  <source srcSet="image.webp" type="image/webp" />
  <img src="image.jpg" alt="..." loading="lazy" />
</picture>
```

### 缓存策略
```typescript
// Service Worker 缓存
const CACHE_NAME = 'v1';
const STATIC_ASSETS = ['/app.js', '/styles.css'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

// HTTP 缓存头
Cache-Control: public, max-age=31536000, immutable  // 静态资源
Cache-Control: no-cache, must-revalidate           // API 响应
```

## 后端性能优化

### 数据库优化
```sql
-- 索引优化
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at DESC);

-- 查询分析
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 1;

-- 避免 N+1
SELECT u.*, o.* FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.id IN (1, 2, 3);
```

### 缓存层
```typescript
// Redis 缓存
async function getUserWithCache(userId: string) {
  const cacheKey = `user:${userId}`;
  
  // 先查缓存
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);
  
  // 查数据库
  const user = await db.user.findUnique({ where: { id: userId } });
  
  // 写入缓存
  await redis.setex(cacheKey, 3600, JSON.stringify(user));
  
  return user;
}
```

### 连接池
```typescript
// 数据库连接池
const pool = new Pool({
  max: 20,           // 最大连接数
  min: 5,            // 最小连接数
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});
```

## 性能监控

### 前端监控
```typescript
// Web Vitals 监控
import { onLCP, onFID, onCLS } from 'web-vitals';

onLCP((metric) => {
  analytics.send('LCP', metric.value);
});

onFID((metric) => {
  analytics.send('FID', metric.value);
});

onCLS((metric) => {
  analytics.send('CLS', metric.value);
});
```

### 后端监控
```typescript
// 请求耗时中间件
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    metrics.histogram('http_request_duration', duration, {
      method: req.method,
      path: req.path,
      status: res.statusCode,
    });
  });
  next();
});
```

## 性能检查清单

```markdown
### 前端
- [ ] 代码分割和懒加载
- [ ] 图片优化 (WebP/AVIF)
- [ ] 关键 CSS 内联
- [ ] 预加载关键资源
- [ ] 减少第三方脚本

### 后端
- [ ] 数据库索引
- [ ] 查询优化
- [ ] 缓存策略
- [ ] 连接池配置
- [ ] 异步处理

### 网络
- [ ] CDN 配置
- [ ] 压缩 (Gzip/Brotli)
- [ ] HTTP/2
- [ ] 缓存头设置
```

## 输出规范

- 量化性能指标
- 提供具体优化代码
- 说明优化效果预期
- 给出优先级建议

## 压测脚本生成

### k6 负载测试模板
```javascript
// load-test.js — k6 脚本
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Ramp-up
    { duration: '1m',  target: 50 },   // Steady
    { duration: '30s', target: 200 },  // Spike
    { duration: '1m',  target: 200 },  // Sustained peak
    { duration: '30s', target: 0 },    // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95%<500ms, 99%<1s
    http_req_failed: ['rate<0.01'],                  // 错误率<1%
  },
};

export default function () {
  const res = http.get('http://localhost:3000/api/health');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 200ms': (r) => r.timings.duration < 200,
  });
  sleep(1);
}
// 运行: k6 run load-test.js
// 云端: k6 cloud run load-test.js
```

### Artillery 压测模板
```yaml
# artillery-config.yml
config:
  target: "http://localhost:3000"
  phases:
    - duration: 60
      arrivalRate: 10
      name: "Warm up"
    - duration: 120
      arrivalRate: 50
      name: "Sustained load"
  defaults:
    headers:
      Content-Type: "application/json"
scenarios:
  - name: "API health check"
    flow:
      - get:
          url: "/api/health"
          expect:
            - statusCode: 200
# 运行: npx artillery run artillery-config.yml
```

### 压测检查清单
- [ ] 基准测试: 单用户响应时间 baseline
- [ ] 阶梯加压: 10→50→100→200 并发
- [ ] 峰值测试: 设计容量 2x 突发
- [ ] 浸泡测试: 正常负载持续 4h+ (检测内存泄漏)
- [ ] 数据库连接池是否耗尽
- [ ] 文件句柄/Socket 是否泄漏
- [ ] GC 暂停是否影响 P99 延迟

## 禁止事项

- ❌ 不要过早优化
- ❌ 不要忽略监控数据
- ❌ 不要只优化不验证
- ❌ 不要忽视用户体验
- ❌ 不要在没有 baseline 的情况下做优化

