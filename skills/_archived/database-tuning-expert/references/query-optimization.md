# 查询优化模式与实战

> 本文档是 database-tuning-expert 技能的参考资料，覆盖常见查询优化场景的最佳实践。

---

## 1. N+1 查询修复

### 1.1 问题说明

N+1 查询是 ORM 中最常见的性能杀手：先查 1 次主表，再对每条结果分别查关联表 N 次。

```
-- 伪代码：获取 100 个订单及其用户
SELECT * FROM orders LIMIT 100;         -- 1 次查询
SELECT * FROM users WHERE id = 1;       -- +N 次查询
SELECT * FROM users WHERE id = 2;
...
SELECT * FROM users WHERE id = 100;     -- 共 101 次查询
```

### 1.2 Prisma (TypeScript) 修复

```typescript
// 错误：N+1
const orders = await prisma.order.findMany();
for (const order of orders) {
  const user = await prisma.user.findUnique({ where: { id: order.userId } });
}

// 正确：使用 include 预加载
const orders = await prisma.order.findMany({
  include: { user: true },  // 自动 JOIN 或批量查询
});

// 正确：手动批量查询
const orders = await prisma.order.findMany();
const userIds = [...new Set(orders.map(o => o.userId))];
const users = await prisma.user.findMany({
  where: { id: { in: userIds } },
});
```

### 1.3 SQLAlchemy (Python) 修复

```python
# 错误：懒加载触发 N+1
orders = session.query(Order).all()
for order in orders:
    print(order.user.name)  # 每次访问触发查询

# 正确：joinedload（单次 JOIN 查询）
from sqlalchemy.orm import joinedload
orders = session.query(Order).options(joinedload(Order.user)).all()

# 正确：subqueryload（两次查询，适合一对多）
from sqlalchemy.orm import subqueryload
orders = session.query(Order).options(subqueryload(Order.items)).all()

# 正确：selectinload（IN 查询，推荐）
from sqlalchemy.orm import selectinload
orders = session.query(Order).options(selectinload(Order.items)).all()
```

### 1.4 GORM (Go) 修复

```go
// 错误：未预加载
var orders []Order
db.Find(&orders)
for _, order := range orders {
    db.First(&order.User, order.UserID)  // N+1
}

// 正确：Preload 预加载
db.Preload("User").Find(&orders)

// 正确：多级预加载
db.Preload("User").Preload("Items.Product").Find(&orders)

// 正确：条件预加载
db.Preload("Items", "price > ?", 100).Find(&orders)
```

---

## 2. 高效分页

### 2.1 OFFSET 的问题

```sql
-- 当 OFFSET 很大时性能极差（需扫描并丢弃前 N 行）
SELECT * FROM orders ORDER BY id DESC LIMIT 20 OFFSET 100000;
-- PostgreSQL 必须先排序前 100020 行，再丢弃前 100000 行
```

### 2.2 Keyset 分页（游标分页，推荐）

```sql
-- 第一页
SELECT * FROM orders ORDER BY id DESC LIMIT 20;

-- 下一页（使用上一页最后一条的 id）
SELECT * FROM orders WHERE id < :last_id ORDER BY id DESC LIMIT 20;

-- 多列排序的 Keyset 分页
SELECT * FROM orders
WHERE (created_at, id) < (:last_created_at, :last_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

### 2.3 Cursor 分页（GraphQL 风格）

```typescript
// 编码游标
function encodeCursor(id: number, createdAt: Date): string {
  return Buffer.from(JSON.stringify({ id, createdAt })).toString('base64');
}

// 解码游标
function decodeCursor(cursor: string): { id: number; createdAt: Date } {
  return JSON.parse(Buffer.from(cursor, 'base64').toString('utf-8'));
}

// 查询实现
async function getOrders(after?: string, first: number = 20) {
  const where = after ? decodeCursor(after) : null;
  const orders = await prisma.order.findMany({
    where: where ? {
      OR: [
        { createdAt: { lt: where.createdAt } },
        { createdAt: where.createdAt, id: { lt: where.id } },
      ],
    } : undefined,
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: first + 1,  // 多取一条判断 hasNextPage
  });
  const hasNextPage = orders.length > first;
  const edges = orders.slice(0, first);
  return {
    edges: edges.map(o => ({ node: o, cursor: encodeCursor(o.id, o.createdAt) })),
    pageInfo: {
      hasNextPage,
      endCursor: edges.length > 0 ? encodeCursor(edges[edges.length - 1].id, edges[edges.length - 1].createdAt) : null,
    },
  };
}
```

---

## 3. 全文搜索

### 3.1 tsvector / tsquery 基础

```sql
-- 创建全文搜索列
ALTER TABLE articles ADD COLUMN search_vector tsvector;

-- 更新搜索向量
UPDATE articles SET search_vector =
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'B');

-- 创建 GIN 索引
CREATE INDEX idx_articles_search ON articles USING gin(search_vector);

-- 查询
SELECT title, ts_rank(search_vector, query) AS rank
FROM articles, to_tsquery('english', 'database & optimization') query
WHERE search_vector @@ query
ORDER BY rank DESC;
```

### 3.2 中文分词 zhparser

```sql
-- 安装 zhparser 扩展
CREATE EXTENSION zhparser;

-- 创建中文分词配置
CREATE TEXT SEARCH CONFIGURATION chinese (PARSER = zhparser);
ALTER TEXT SEARCH CONFIGURATION chinese
    ADD MAPPING FOR n,v,a,i,e,l WITH simple;  -- 名词/动词/形容词等

-- 使用中文分词
SELECT to_tsvector('chinese', '冷链物流温度监控系统');
-- 结果：'冷链':1 '物流':2 '温度':3 '监控':4 '系统':5

-- 中文全文搜索查询
SELECT * FROM articles
WHERE to_tsvector('chinese', title || ' ' || content) @@ to_tsquery('chinese', '冷链 & 监控');
```

### 3.3 自动更新搜索向量（触发器）

```sql
CREATE OR REPLACE FUNCTION articles_search_trigger() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('chinese', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('chinese', coalesce(NEW.content, '')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_articles_search
    BEFORE INSERT OR UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION articles_search_trigger();
```

---

## 4. JSONB 操作

### 4.1 查询语法速查

```sql
-- 提取字段值
SELECT metadata->>'name' AS name FROM products;                  -- 文本
SELECT metadata->'address'->>'city' FROM products;               -- 嵌套
SELECT metadata#>>'{address,city}' FROM products;                -- 路径提取

-- 包含查询（GIN 索引可加速）
SELECT * FROM products WHERE metadata @> '{"color": "red"}';

-- 存在性查询
SELECT * FROM products WHERE metadata ? 'discount';              -- key 存在
SELECT * FROM products WHERE metadata ?| array['a', 'b'];       -- 任一 key 存在
SELECT * FROM products WHERE metadata ?& array['a', 'b'];       -- 所有 key 存在

-- JSONB 路径查询 (PostgreSQL 12+)
SELECT * FROM products
WHERE jsonb_path_exists(metadata, '$.tags[*] ? (@ == "sale")');
```

### 4.2 GIN 索引策略

```sql
-- 通用 GIN 索引（支持 @>, ?, ?|, ?& 操作符）
CREATE INDEX idx_products_meta ON products USING gin(metadata);

-- jsonb_path_ops（更小、更快，只支持 @>）
CREATE INDEX idx_products_meta_path ON products USING gin(metadata jsonb_path_ops);

-- 表达式索引（只索引特定字段）
CREATE INDEX idx_products_color ON products ((metadata->>'color'));
```

---

## 5. 物化视图

### 5.1 创建与使用

```sql
-- 创建物化视图
CREATE MATERIALIZED VIEW mv_daily_sales AS
SELECT date_trunc('day', created_at) AS day,
       product_id,
       SUM(quantity) AS total_qty,
       SUM(amount) AS total_amount
FROM orders
GROUP BY 1, 2;

-- 创建索引（物化视图可以加索引）
CREATE INDEX idx_mv_daily_sales_day ON mv_daily_sales(day);

-- 查询（像普通表一样使用）
SELECT * FROM mv_daily_sales WHERE day >= '2025-01-01';
```

### 5.2 刷新策略

```sql
-- 普通刷新（锁定视图，查询阻塞）
REFRESH MATERIALIZED VIEW mv_daily_sales;

-- 并发刷新（不锁定，但需要唯一索引）
CREATE UNIQUE INDEX idx_mv_daily_sales_uniq ON mv_daily_sales(day, product_id);
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales;
```

### 5.3 自动化刷新（pg_cron）

```sql
-- 安装 pg_cron
CREATE EXTENSION pg_cron;

-- 每小时自动刷新
SELECT cron.schedule('refresh_daily_sales', '0 * * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales');

-- 查看调度任务
SELECT * FROM cron.job;
```

---

## 6. CTE 与窗口函数

### 6.1 WITH 表达式（CTE）

```sql
-- 基础 CTE
WITH active_users AS (
    SELECT user_id, COUNT(*) AS order_count
    FROM orders
    WHERE created_at > now() - interval '30 days'
    GROUP BY user_id
)
SELECT u.name, au.order_count
FROM users u
JOIN active_users au ON au.user_id = u.id
WHERE au.order_count > 5;

-- 递归 CTE（树形结构遍历）
WITH RECURSIVE category_tree AS (
    -- 基础查询：根节点
    SELECT id, name, parent_id, 1 AS depth, name::text AS path
    FROM categories WHERE parent_id IS NULL
    UNION ALL
    -- 递归查询：子节点
    SELECT c.id, c.name, c.parent_id, ct.depth + 1,
           ct.path || ' > ' || c.name
    FROM categories c
    JOIN category_tree ct ON ct.id = c.parent_id
)
SELECT * FROM category_tree ORDER BY path;
```

**注意**: PostgreSQL 12+ 中，非递归 CTE 默认会被内联优化（不再强制物化）。如需强制物化，使用 `WITH cte AS MATERIALIZED (...)`。

### 6.2 窗口函数实用模式

```sql
-- ROW_NUMBER：分组排名（取每组 Top N）
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY sales DESC) AS rn
    FROM products
) t WHERE rn <= 3;  -- 每个分类销量前 3

-- RANK / DENSE_RANK：允许并列排名
SELECT name, score,
       RANK() OVER (ORDER BY score DESC) AS rank,          -- 1,2,2,4（跳号）
       DENSE_RANK() OVER (ORDER BY score DESC) AS dense_rank  -- 1,2,2,3（不跳号）
FROM students;

-- LAG / LEAD：同比环比计算
SELECT month,
       revenue,
       LAG(revenue, 1) OVER (ORDER BY month) AS prev_month,
       revenue - LAG(revenue, 1) OVER (ORDER BY month) AS mom_change,  -- 环比变化
       LAG(revenue, 12) OVER (ORDER BY month) AS prev_year,
       revenue - LAG(revenue, 12) OVER (ORDER BY month) AS yoy_change  -- 同比变化
FROM monthly_revenue;

-- SUM OVER：累计求和
SELECT date, amount,
       SUM(amount) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM daily_sales;
```

---

## 7. 批量操作

### 7.1 COPY vs INSERT 性能对比

| 方式 | 10万行耗时 | 适用场景 |
|------|-----------|----------|
| 逐行 INSERT | ~60s | 不推荐 |
| 批量 INSERT (1000行/批) | ~3s | 应用层批量插入 |
| COPY | ~0.5s | 数据导入/ETL |

```sql
-- COPY 从文件导入
COPY orders(user_id, product_id, amount)
FROM '/tmp/orders.csv' WITH (FORMAT csv, HEADER true);

-- COPY 从 stdin（应用层流式写入）
COPY orders(user_id, product_id, amount) FROM STDIN WITH (FORMAT csv);
```

### 7.2 unnest 批量插入

```sql
-- 使用 unnest 实现参数化批量插入
INSERT INTO orders (user_id, product_id, amount)
SELECT * FROM unnest(
    ARRAY[1, 2, 3]::bigint[],           -- user_id 数组
    ARRAY[101, 102, 103]::bigint[],      -- product_id 数组
    ARRAY[99.9, 199.9, 299.9]::numeric[] -- amount 数组
);
```

Python 中使用 psycopg2 实现：

```python
import psycopg2
from psycopg2.extras import execute_values

# execute_values 比 executemany 快 10 倍+
data = [(1, 101, 99.9), (2, 102, 199.9), (3, 103, 299.9)]
execute_values(
    cursor,
    "INSERT INTO orders (user_id, product_id, amount) VALUES %s",
    data,
    page_size=1000  # 每批 1000 行
)
```

### 7.3 ON CONFLICT (UPSERT)

```sql
-- 单行 UPSERT
INSERT INTO products (sku, name, price)
VALUES ('SKU-001', '温度传感器', 299.00)
ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    price = EXCLUDED.price,
    updated_at = now();

-- 批量 UPSERT
INSERT INTO inventory (warehouse_id, product_id, quantity)
SELECT * FROM unnest(
    ARRAY[1, 1, 2]::int[],
    ARRAY[101, 102, 101]::int[],
    ARRAY[50, 30, 80]::int[]
)
ON CONFLICT (warehouse_id, product_id) DO UPDATE SET
    quantity = inventory.quantity + EXCLUDED.quantity,
    updated_at = now();

-- DO NOTHING（忽略冲突，仅插入新行）
INSERT INTO tags (name)
SELECT unnest(ARRAY['冷链', '物流', '监控'])
ON CONFLICT (name) DO NOTHING;
```
