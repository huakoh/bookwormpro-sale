# PostgreSQL 深度调优指南

> 本文档是 database-tuning-expert 技能的参考资料，涵盖 PostgreSQL 核心调优领域。

---

## 1. EXPLAIN ANALYZE 深度解读

### 1.1 基本用法

```sql
-- 完整的执行计划分析（推荐格式）
EXPLAIN (ANALYZE, BUFFERS, COSTS, TIMING, FORMAT TEXT)
SELECT o.id, o.total, u.name
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.status = 'active' AND o.created_at > '2025-01-01';
```

- `ANALYZE`: 实际执行查询并返回真实耗时（注意：会真正执行 DML，生产环境用 `BEGIN; EXPLAIN ANALYZE ...; ROLLBACK;`）
- `BUFFERS`: 显示缓冲区命中/读取情况
- `COSTS`: 显示估算成本（默认开启）
- `TIMING`: 显示每个节点的实际耗时

### 1.2 执行计划节点类型

| 节点类型 | 说明 | 优化建议 |
|----------|------|----------|
| Seq Scan | 全表顺序扫描 | 表小(< 几百行)可接受；大表应添加索引 |
| Index Scan | 通过索引定位后回表取数据 | 理想的访问方式 |
| Index Only Scan | 仅访问索引，不回表 | 最优，需确保 visibility map 足够新 |
| Bitmap Index Scan | 构建位图后批量回表 | 多条件 OR / 低选择性索引查询常见 |
| Bitmap Heap Scan | 配合 Bitmap Index Scan 回表 | 注意 Recheck Cond 是否过滤大量行 |
| Nested Loop | 对外表每行扫描内表 | 内表需有索引，适合小结果集 |
| Hash Join | 构建哈希表后探测匹配 | 大表等值连接的优选 |
| Merge Join | 两表排序后归并 | 两表已按连接键排序时高效 |
| Sort | 排序操作 | 注意是否溢出到磁盘（Sort Method: external merge） |
| HashAggregate | 哈希分组聚合 | GROUP BY 基数大时使用 |
| GroupAggregate | 排序后分组聚合 | 数据已有序时使用 |

### 1.3 成本估算与实际执行对比

```
Seq Scan on orders  (cost=0.00..1520.00 rows=500 width=40)
                     (actual time=0.015..12.340 rows=487 loops=1)
```

- `cost=启动成本..总成本`: 优化器估算的相对成本
- `rows=500`: 优化器估算返回行数
- `actual time=首行耗时..末行耗时(ms)`: 实际执行时间
- `rows=487`: 实际返回行数
- `loops=1`: 该节点执行次数

**关键排查点**: 若 `rows` 估算值与实际值偏差 > 10 倍，说明统计信息过时，需执行 `ANALYZE` 更新。

### 1.4 常见慢查询模式

| 模式 | 特征 | 解决方案 |
|------|------|----------|
| 大表全扫描 | Seq Scan + rows 很大 | 添加 WHERE 条件对应索引 |
| 估算偏差 | estimated rows 与 actual rows 差 10x+ | `ANALYZE table_name` 更新统计 |
| 排序溢出 | Sort Method: external merge Disk | 增大 `work_mem` 或添加排序索引 |
| 嵌套循环爆炸 | Nested Loop + loops=100000 | 改用 Hash Join 或添加索引 |
| 索引失效 | 有索引但 Seq Scan | 检查隐式类型转换、函数包裹、LIKE '%前缀' |
| 锁等待 | 查询本身快但总耗时长 | 检查 `pg_stat_activity` 中的 `wait_event` |

---

## 2. 索引类型详解

### 2.1 B-tree (默认)

最常用的索引类型，支持等值、范围、排序、IS NULL 查询。

```sql
-- 创建单列索引
CREATE INDEX idx_orders_user_id ON orders(user_id);

-- 创建联合索引（遵循最左前缀原则）
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- 创建唯一索引
CREATE UNIQUE INDEX idx_users_email ON users(email);

-- 创建部分索引（只索引满足条件的行）
CREATE INDEX idx_orders_active ON orders(user_id)
WHERE status = 'active';

-- 创建覆盖索引（INCLUDE 避免回表）
CREATE INDEX idx_orders_cover ON orders(user_id)
INCLUDE (total, created_at);
```

### 2.2 Hash 索引

仅支持等值查询，PostgreSQL 10+ 支持 WAL 日志（可靠）。

```sql
CREATE INDEX idx_sessions_token ON sessions USING hash(token);
-- 适合：token 精确查找，不需要范围查询
```

### 2.3 GIN (Generalized Inverted Index)

适合多值类型：全文搜索、JSONB、数组。

```sql
-- JSONB 字段索引
CREATE INDEX idx_metadata_gin ON products USING gin(metadata);
-- 查询：SELECT * FROM products WHERE metadata @> '{"color": "red"}';

-- 全文搜索索引
CREATE INDEX idx_articles_fts ON articles USING gin(to_tsvector('chinese', title || ' ' || content));

-- 数组字段索引
CREATE INDEX idx_tags_gin ON posts USING gin(tags);
-- 查询：SELECT * FROM posts WHERE tags @> ARRAY['postgresql'];
```

### 2.4 GiST (Generalized Search Tree)

适合几何类型、范围类型、全文搜索（支持模糊匹配权重）。

```sql
-- PostGIS 空间索引
CREATE INDEX idx_locations_geom ON locations USING gist(geom);

-- 范围类型索引
CREATE INDEX idx_events_during ON events USING gist(during);
-- 查询：SELECT * FROM events WHERE during && '[2025-01-01, 2025-06-01)';

-- pg_trgm 模糊搜索
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_users_name_trgm ON users USING gist(name gist_trgm_ops);
-- 查询：SELECT * FROM users WHERE name % '张三';
```

### 2.5 BRIN (Block Range Index)

极小的索引体积，适合物理有序的大表（如时序数据）。

```sql
-- 时序数据时间戳索引
CREATE INDEX idx_logs_created_brin ON logs USING brin(created_at)
WITH (pages_per_range = 128);

-- 适合场景：数据按 created_at 自然递增写入
-- 不适合：随机插入或频繁更新的表
```

### 2.6 索引维护命令

```sql
-- 查看索引使用情况
SELECT schemaname, relname, indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- 查看索引大小
SELECT pg_size_pretty(pg_relation_size('idx_orders_user_id'));

-- 重建索引（不锁表，推荐）
REINDEX INDEX CONCURRENTLY idx_orders_user_id;

-- 删除未使用的索引（idx_scan = 0 持续数周）
DROP INDEX CONCURRENTLY idx_unused;
```

---

## 3. 分区表

### 3.1 Range 分区（最常用）

```sql
-- 创建分区父表
CREATE TABLE logs (
    id         bigserial,
    message    text,
    created_at timestamptz NOT NULL
) PARTITION BY RANGE (created_at);

-- 创建月度分区
CREATE TABLE logs_2025_01 PARTITION OF logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE logs_2025_02 PARTITION OF logs
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- 创建默认分区（兜底）
CREATE TABLE logs_default PARTITION OF logs DEFAULT;
```

### 3.2 List 分区

```sql
CREATE TABLE orders (
    id       bigserial,
    region   text NOT NULL,
    total    numeric
) PARTITION BY LIST (region);

CREATE TABLE orders_cn PARTITION OF orders FOR VALUES IN ('cn', 'hk', 'tw');
CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('us', 'ca');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('de', 'fr', 'uk');
```

### 3.3 Hash 分区

```sql
CREATE TABLE sessions (
    id      bigserial,
    user_id bigint NOT NULL,
    data    jsonb
) PARTITION BY HASH (user_id);

CREATE TABLE sessions_0 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE sessions_1 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE sessions_2 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE sessions_3 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

### 3.4 分区裁剪验证

```sql
-- 确认分区裁剪生效（Constraint Exclusion / Partition Pruning）
SET enable_partition_pruning = on;  -- 默认开启
EXPLAIN SELECT * FROM logs WHERE created_at = '2025-03-15';
-- 应只扫描 logs_2025_03，不扫描其他分区
```

### 3.5 自动分区管理（pg_partman）

```sql
-- 安装 pg_partman 扩展
CREATE EXTENSION pg_partman;

-- 配置自动分区
SELECT create_parent(
    p_parent_table := 'public.logs',
    p_control := 'created_at',
    p_type := 'native',
    p_interval := '1 month',
    p_premake := 3  -- 预创建未来 3 个分区
);

-- 定期维护（cron 每天执行）
SELECT run_maintenance();
```

---

## 4. VACUUM 与 ANALYZE

### 4.1 VACUUM 基础

PostgreSQL 使用 MVCC（多版本并发控制），UPDATE/DELETE 不会立即物理删除旧行，而是标记为"死元组"(dead tuples)。VACUUM 负责回收这些空间。

```sql
-- 手动 VACUUM（不锁表，可并发读写）
VACUUM orders;

-- VACUUM FULL（重写整表，会锁表，慎用）
VACUUM FULL orders;

-- VACUUM + ANALYZE（清理 + 更新统计）
VACUUM ANALYZE orders;
```

### 4.2 autovacuum 配置优化

```ini
# postgresql.conf 关键参数
autovacuum = on                          # 必须开启
autovacuum_max_workers = 3               # 并发 worker 数
autovacuum_naptime = 60                  # 检查间隔(秒)

# 触发阈值
autovacuum_vacuum_threshold = 50         # 基础行数
autovacuum_vacuum_scale_factor = 0.1     # 表大小比例（10%变更触发）
# 实际触发 = threshold + scale_factor * 表行数

# 大表单独调优
ALTER TABLE huge_table SET (
    autovacuum_vacuum_scale_factor = 0.01,  # 1% 变更就触发
    autovacuum_vacuum_threshold = 1000
);
```

### 4.3 监控死元组

```sql
-- 查看各表死元组情况
SELECT relname, n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 2) AS dead_ratio,
       last_vacuum, last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

---

## 5. PgBouncer 连接池

### 5.1 三种 pool_mode 对比

| 模式 | 连接复用粒度 | 兼容性 | 推荐场景 |
|------|-------------|--------|----------|
| session | 会话结束才释放 | 完全兼容 | 需要 PREPARE/SET/临时表 |
| transaction | 事务结束即释放 | 大部分兼容 | Web 应用（推荐） |
| statement | 每条语句后释放 | 只支持 autocommit | 简单查询负载 |

### 5.2 完整配置模板

```ini
[databases]
mydb = host=127.0.0.1 port=5432 dbname=mydb

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3

server_idle_timeout = 600
server_lifetime = 3600
server_connect_timeout = 15
query_timeout = 120
query_wait_timeout = 60

log_connections = 0
log_disconnections = 0
log_pooler_errors = 1
stats_period = 60
```

### 5.3 监控命令

```sql
-- 连接到 PgBouncer 管理控制台
psql -h 127.0.0.1 -p 6432 -U pgbouncer pgbouncer

-- 查看连接池状态
SHOW POOLS;

-- 查看活跃客户端
SHOW CLIENTS;

-- 查看服务端连接
SHOW SERVERS;

-- 查看统计信息
SHOW STATS;
```

---

## 6. 内存参数调优

### 6.1 核心参数

| 参数 | 建议值 | 说明 |
|------|--------|------|
| `shared_buffers` | 物理内存的 25% | 数据页缓存，不宜超过 8GB（OS cache 更高效） |
| `work_mem` | 32MB-256MB | 排序/哈希操作内存，按连接数×并发估算总量 |
| `effective_cache_size` | 物理内存的 50%-75% | 告诉优化器可用缓存量（不分配实际内存） |
| `maintenance_work_mem` | 512MB-2GB | VACUUM/CREATE INDEX 时使用 |
| `wal_buffers` | 64MB | WAL 写入缓冲 |

### 6.2 典型服务器配置示例

```ini
# 16GB 内存服务器
shared_buffers = 4GB
work_mem = 64MB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
wal_buffers = 64MB

# 连接相关
max_connections = 200
```

### 6.3 work_mem 估算

```
总 work_mem 消耗 ≈ work_mem × max_connections × 每查询排序/哈希操作数
# 例：64MB × 200 连接 × 2 操作 = 25.6GB（注意不要超过可用内存）
```

---

## 7. 慢查询日志

### 7.1 配置慢查询记录

```ini
# postgresql.conf
log_min_duration_statement = 200    # 记录超过 200ms 的查询
log_statement = 'none'               # 不记录所有语句（避免日志爆炸）
log_line_prefix = '%t [%p] %u@%d '  # 时间 + PID + 用户 + 数据库

# 自动解释慢查询
auto_explain.log_min_duration = 500  # 超过 500ms 自动记录执行计划
auto_explain.log_analyze = on
auto_explain.log_buffers = on
```

### 7.2 pg_stat_statements 扩展

```sql
-- 启用扩展
CREATE EXTENSION pg_stat_statements;

-- 查看 Top 10 慢查询
SELECT query,
       calls,
       round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2) AS avg_ms,
       rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 查看 Top 10 调用最频繁的查询
SELECT query, calls, rows,
       round(total_exec_time::numeric, 2) AS total_ms
FROM pg_stat_statements
ORDER BY calls DESC
LIMIT 10;

-- 重置统计（定期执行，如每周）
SELECT pg_stat_statements_reset();
```

### 7.3 实时排查活跃查询

```sql
-- 查看当前正在执行的查询
SELECT pid, now() - pg_stat_activity.query_start AS duration,
       state, query, wait_event_type, wait_event
FROM pg_stat_activity
WHERE state = 'active' AND pid <> pg_backend_pid()
ORDER BY duration DESC;

-- 终止指定查询（优雅取消）
SELECT pg_cancel_backend(pid);

-- 强制终止连接（慎用）
SELECT pg_terminate_backend(pid);
```
