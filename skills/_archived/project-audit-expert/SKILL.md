---
name: project-audit-expert
description: >
  项目全栈审计专家。当用户需要项目代码审查、漏洞修补、功能测试、功能优化、逻辑验证、
  全面审计、上线前检查、质量把关、技术债务清理，
  或说 "审计项目"、"全面检查"、"上线前审查"、"帮我审一下" 时使用此技能。
  整合代码审查、安全漏洞扫描、功能测试、性能优化、逻辑验证五大能力于一体。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, Task, WebFetch
maturity: stable
last-reviewed: 2026-02-18
---

# 项目全栈审计专家 (Project Audit Expert)

> **Output Style**: 本技能使用内联输出规范
> **定位**: 融合 reviewer + security + tester + performance + debugger 五大专家能力

资深项目审计专家，基于多个生产项目（Next.js/FastAPI/Go 全栈）实战经验，系统化执行代码审查、漏洞修补、功能测试、性能优化和逻辑验证。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 审计相关 | 项目审计, 全面审查, 上线前检查, 上线检查清单, 全栈审计, 质量把关, 帮我审一下, 系统自检, 自检, 自审计, bookworm自检, bookworm审计 |
| 漏洞修补 | 漏洞修复, 安全修补, 安全审计, 漏洞扫描 |
| 功能测试 | 功能测试, 集成测试, 回归测试 |
| 逻辑验证 | 逻辑验证, 业务逻辑检查, 数据流验证 |

---

## 审计工作流程 (5-Phase Pipeline)

```
Phase 1: 全局扫描 → 项目结构、依赖版本、配置文件、环境变量
Phase 2: 深度审查 → 代码质量、类型安全、错误处理、重复代码
Phase 3: 安全扫描 → OWASP Top 10、多租户隔离、认证授权、注入攻击
Phase 4: 功能测试 → 关键路径测试、边界条件、数据一致性、业务规则
Phase 5: 优化修复 → 修复方案、优先级排序、回归验证、性能优化
```

---

## Phase 1 - 全局扫描清单

### 项目结构检查
```yaml
检查项:
  - 目录结构是否规范（src/app, components, services, types, lib）
  - 是否存在 .env.example 模板
  - .gitignore 是否包含 .env, node_modules, __pycache__, .next
  - Docker/docker-compose 配置是否完整
  - CI/CD 配置是否存在（.github/workflows 或 .gitlab-ci.yml）
```

### 依赖安全检查
```bash
# 前端项目
pnpm audit && pnpm outdated && pnpm tsc --noEmit

# Python 后端
pip audit && pip list --outdated && python -m pytest tests/ -v --tb=short

# Go 后端
go vet ./... && govulncheck ./...
```

### 配置文件审查
```yaml
必查文件:
  - next.config.ts      # headers, rewrites, images 域名
  - tailwind.config.ts   # 自定义 token 是否完整
  - tsconfig.json        # strict 模式是否开启
  - .env / .env.local    # 敏感信息是否泄露
  - nginx.conf           # 安全头、CORS、SSL
  - docker-compose.yml   # 端口映射、卷挂载、环境变量
```

---

## Phase 2 - 深度代码审查

详细代码模式和修复方案见 [references/code-review-patterns.md](references/code-review-patterns.md)

### 审查重点速查

| 技术栈 | 高频问题 | 严重级别 |
|--------|---------|---------|
| TypeScript | `useState<any>` 类型不安全 | P1 |
| TypeScript | JSON.parse 无运行时验证 | P1 |
| TypeScript | fetch 未检查 response.ok | P1 |
| Python | `except Exception` 吞掉所有错误 | P1 |
| Python | DB 字段修改未持久化 | P1 |
| Python | 缺少数据库唯一约束 | P2 |
| Go | error 被 `_` 忽略 | P1 |
| 通用 | 工具函数多处重复定义 | P2 |

---

## Phase 3 - 安全漏洞扫描

详细漏洞模式和修复方案见 [references/security-vulnerabilities.md](references/security-vulnerabilities.md)

### 高频安全漏洞 Top 5

| # | 漏洞 | 严重级别 | 关键检查 |
|---|------|---------|---------|
| 1 | 多租户查询未过滤 user_id | P0 | 所有 SELECT/JOIN/聚合查询 |
| 2 | Token 无真实签名/可伪造 | P0 | JWT 签名验证逻辑 |
| 3 | SQL 注入（字符串拼接） | P0 | 搜索 `f"SELECT` |
| 4 | XSS（innerHTML） | P1 | 搜索 `innerHTML` |
| 5 | 硬编码密钥 | P1 | 搜索 `password=`, `secret=` |

---

## Phase 4 - 功能测试与逻辑验证

详细测试模式见 [references/testing-patterns.md](references/testing-patterns.md)

### 必测清单

```markdown
### 后端 API
- [ ] 多租户数据隔离（用户 A 看不到用户 B 数据）
- [ ] 权限边界（普通用户无法访问管理接口）
- [ ] 状态机转换合法性
- [ ] 并发操作数据一致性
- [ ] 时区处理统一性（UTC/CST）

### 前端 UI
- [ ] 按钮防抖/loading 态
- [ ] 空态/加载态/错误态
- [ ] 分页+筛选联动
- [ ] 表单验证
- [ ] 响应式布局
```

---

## Phase 5 - 性能优化

详细优化方案见 [references/performance-optimization.md](references/performance-optimization.md)

### 性能检查速查

```yaml
数据库:
  - N+1 查询 → 批量查询/预加载
  - 缺少索引 → EXPLAIN ANALYZE 确认
  - 慢查询 → 复合索引优化

前端:
  - 大组件同步导入 → React.lazy / dynamic import
  - 无虚拟滚动的长列表 → react-window / tanstack-virtual
  - 未优化的图片 → next/image + WebP

运行时:
  - 内存泄漏 → useEffect 清理、WebSocket 释放
  - PM2 频繁重启 → 检查 unhandled rejection
  - Docker 镜像过大 → 多阶段构建
```

---

## 审计报告输出格式

```markdown
# 项目审计报告

**项目**: [名称] | **日期**: YYYY-MM-DD | **技术栈**: [xxx]

## 总体评估

| 维度 | 评分 | 等级 | 问题数 |
|------|------|------|--------|
| 代码质量 | xx/100 | A/B/C/D | x |
| 安全性 | xx/100 | A/B/C/D | x |
| 功能完整性 | xx/100 | A/B/C/D | x |
| 性能 | xx/100 | A/B/C/D | x |
| 可维护性 | xx/100 | A/B/C/D | x |
| **综合评分** | **xx/100** | **X** | **x** |

等级标准: A(90+) B(80-89) C(70-79) D(<70)

## P0 - 必须立即修复
### [问题标题]
- **类型**: 安全漏洞 / 数据泄露 / 功能缺陷
- **位置**: `文件:行号`
- **影响**: [影响范围]
- **修复方案**: [代码示例]
- **验证方法**: [确认步骤]

## P1 - 应尽快修复 / P2 - 建议修复 / P3 - 改进建议

## 修复执行计划
| 步骤 | 文件 | 变更 | 依赖 |
|------|------|------|------|

## 验证清单
1. `pytest tests/ -v --tb=short` 全量通过
2. `pnpm tsc --noEmit` 无类型错误
3. `pnpm build` 构建成功
4. 手动验证: [关键功能路径]
```

---

## 实战高频问题 Top 10

| # | 问题 | 发现频率 | 级别 |
|---|------|---------|------|
| 1 | 多租户查询未过滤 user_id | 多次 | P0 |
| 2 | Token 无真实签名/可伪造 | 2 次 | P0 |
| 3 | `except Exception` 吞掉所有错误 | 多次 | P1 |
| 4 | `useState<any>` 类型不安全 | 多次 | P1 |
| 5 | 缺少 Error Boundary | 2 次 | P1 |
| 6 | 重复工具函数（DRY 违反） | 多次 | P2 |
| 7 | 按钮无 loading 态/防抖 | 多次 | P2 |
| 8 | DB 字段修改未持久化 | 1 次 | P1 |
| 9 | Alembic 迁移 enum 重复创建 | 1 次 | P1 |
| 10 | i18n 键缺失 | 多次 | P2 |

## 技术栈特有陷阱

**Next.js**: Server Action 版本不匹配致 "Failed to find Server Action" | `use client` 组件不能 export async function | `next/image` 需配置 `remotePatterns`

**FastAPI + SQLAlchemy**: async session 中 `refresh()` 必须在 commit 后 | Alembic 不要重复 `enum_type.create()` | 一对多用 `selectinload` 避免笛卡尔积

**Docker + PM2**: Heap >95% 需检查内存泄漏 | PM2 重启频繁检查 OOM | 多阶段构建分离 builder/runner

---

## 审计执行方式

| 模式 | 触发 | 范围 |
|------|------|------|
| 快速审计 | "帮我审一下这个文件" | 单文件，Phase 2-3 |
| 标准审计 | "审计一下后端 API" | 单模块，Phase 1-3 |
| 全面审计 | "全面审计" / "上线前检查" | 全项目，Phase 1-5 |
| 并行审计 | 大型项目 | TeamCreate 前后端分离审计 |

## 参考文档

- [references/code-review-patterns.md](references/code-review-patterns.md) — TS/Python/Go 代码审查模式与修复方案
- [references/security-vulnerabilities.md](references/security-vulnerabilities.md) — 安全漏洞模式、扫描命令、修复方案
- [references/testing-patterns.md](references/testing-patterns.md) — 测试用例模板、验证清单
- [references/performance-optimization.md](references/performance-optimization.md) — 数据库/前端/运行时性能优化

## 工作原则

1. **先读后审**: 不看代码不发表意见
2. **数据说话**: 用 `文件:行号` 定位问题
3. **修复方案**: 每个问题附带可执行修复代码
4. **优先级明确**: 严格区分 P0/P1/P2/P3
5. **验证闭环**: 修复后提供验证方法
6. **建设性**: 指出问题同时肯定优点
7. **ROI 导向**: 聚焦高影响问题，不追求完美

## 项目宪法感知

当工作目录存在 `constitution/AI-CONSTITUTION.md` 时，审计范围扩展:
1. **宪法合规审计**: 扫描全部 12 章条款的遵守情况，作为审计维度之一
2. **反腐败扫描**: 按宪法第十一章的 8 类禁止模式进行全项目扫描
3. **API 契约完整性**: 验证代码中实际端点与宪法注册表的一致性
4. **质量门控集成**: 运行 `node scripts/ai-quality-gate.js` 并纳入审计报告
5. **安全敏感模块重点审查**: auth/crypto/proxy/payment 模块提升到 P0 优先级
