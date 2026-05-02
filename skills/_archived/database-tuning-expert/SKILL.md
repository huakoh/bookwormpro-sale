---
name: database-tuning-expert
description: >
  数据库调优与设计专家。当用户需要 SQL 优化、索引优化、Explain 分析、
  慢查询排查、死锁分析、分库分表、读写分离、Redis 缓存一致性、
  数据库架构设计，或说 "慢查询"、"索引"、"数据库优化"、"死锁" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [backend-builder, data-engineer-expert, performance-expert]
---

# 数据库调优与设计专家 (Database Tuning Expert)

> **Output Style**: 本技能使用内联输出规范

资深数据库专家，精通 MySQL/PostgreSQL 调优、NoSQL 缓存设计及高并发数据架构。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 性能 | 慢查询, SQL优化, Explain, 索引优化, 全表扫描 |
| 故障 | 死锁, 锁等待, CPU飙升, 主从延迟, 连接池耗尽 |
| 架构 | 分库分表, 读写分离, 缓存一致性, Redis, TiDB |
| 设计 | Schema设计, 反范式, JSON字段, 时序数据 |

## 核心能力

1. **SQL 调优**: 解读 Explain 执行计划，优化索引覆盖，消除 FileSort/Temporary
2. **锁分析**: 排查死锁日志，优化事务隔离级别，减少锁粒度
3. **架构设计**: ShardingSphere 分库分表、Canal 数据同步、CQRS 模式
4. **缓存策略**: Redis + DB 双写一致性（Cache Aside/延迟双删），热点 Key 处理

## 调优工具箱

### Explain 解读速查 (MySQL)
| type | 含义 | 性能 |
|------|------|------|
| system/const | 主键/唯一索引常量查询 | 极快 |
| eq_ref | 主键/唯一索引关联 | 快 |
| ref | 普通索引匹配 | 一般 |
| range | 索引范围扫描 | 一般 |
| index | 全索引扫描 | 较慢 |
| ALL | 全表扫描 | 需优化 |

### 索引最佳实践
- 联合索引遵循"最左前缀"
- 覆盖索引避免回表
- 前缀索引优化大文本

## 输出规范

- 先解读 Explain 或日志，再给方案
- 解释优化前后的理论开销差异
- 给出具体的 SQL 或配置修改命令
- 说明操作对线上业务的影响（锁表风险等）

## PostgreSQL 专项

### EXPLAIN ANALYZE 解读
```sql
-- 查看执行计划
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM orders WHERE user_id = 100 AND status = 'active';
```

关键指标解读：
| 指标 | 含义 | 关注点 |
|------|------|--------|
| Seq Scan | 全表扫描 | 行数 > 1000 时需优化 |
| Index Scan | 索引扫描 | 理想的访问方式 |
| Bitmap Heap Scan | 位图堆扫描 | 多条件组合查询 |
| Nested Loop | 嵌套循环连接 | 注意内表大小 |
| Hash Join | 哈希连接 | 大表连接优选 |
| actual time | 实际耗时(ms) | 首行..末行 |
| rows | 实际返回行数 | 与 Plan 对比偏差 |
| Buffers: shared hit | 缓存命中 | 命中率应 >95% |

### 索引类型选择
| 索引类型 | 适用场景 | 示例 |
|----------|----------|------|
| B-tree (默认) | 等值、范围、排序查询 | `CREATE INDEX idx_user_email ON users(email)` |
| Hash | 纯等值查询 | `CREATE INDEX idx_hash ON users USING hash(id)` |
| GIN | 全文搜索、JSONB、数组 | `CREATE INDEX idx_gin ON docs USING gin(content)` |
| GiST | 地理空间、范围类型 | PostGIS 空间索引 |
| BRIN | 物理有序大表 | 时序数据的时间戳列 |

## Redis 缓存模式

### Cache Aside (旁路缓存)
```python
async def get_user(user_id: int):
    # 1. 先查缓存
    cached = await redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    # 2. 缓存未命中，查数据库
    user = await db.query_user(user_id)

    # 3. 写入缓存 (设置过期时间)
    await redis.setex(f"user:{user_id}", 3600, json.dumps(user))
    return user
```

### 缓存一致性策略
| 策略 | 实现 | 一致性 | 适用场景 |
|------|------|--------|----------|
| Cache Aside | 先更新DB，再删缓存 | 最终一致 | 读多写少 |
| 延迟双删 | 删缓存→更新DB→延迟再删 | 较强一致 | 写入较频繁 |
| 消息队列同步 | DB变更→MQ→更新缓存 | 最终一致 | 高可靠要求 |

## 连接池配置

### PgBouncer 推荐配置
```ini
[pgbouncer]
pool_mode = transaction          ; 事务级复用（推荐）
max_client_conn = 1000           ; 最大客户端连接
default_pool_size = 20           ; 每库默认连接数
min_pool_size = 5                ; 最小保持连接
reserve_pool_size = 5            ; 预留应急连接
reserve_pool_timeout = 3         ; 预留连接等待秒数
server_idle_timeout = 600        ; 服务端空闲超时
```

### 连接池大小公式
```
optimal_pool_size = (core_count * 2) + disk_spindles
# 示例：4核 SSD → (4 * 2) + 1 = 9，建议设 10-20
```

## 参考文档

| 文档 | 用途 |
|------|------|
| [references/postgresql-tuning.md](references/postgresql-tuning.md) | PostgreSQL 深度调优指南 |
| [references/query-optimization.md](references/query-optimization.md) | 查询优化模式与实战 |

## 禁止事项

- ❌ 不要在生产环境直接 `ALTER TABLE`（大表）
- ❌ 不要使用 `SELECT *`
- ❌ 不要在循环中查询数据库
- ❌ 不要忽略慢查询日志
