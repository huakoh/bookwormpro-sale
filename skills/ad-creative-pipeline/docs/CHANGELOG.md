# AdCreativePipeline CHANGELOG

## v1.1.0 (2026-05-02) — Alpha Release

### Added
- **5-Stage Pipeline**: ConceptIdeation → DesignDirection → ImageGeneration → CritiqueRefine → FinalExport
- **ImageProvider 抽象**: 支持 gpt-image-2 (中转站) 和 DashScope，可扩展
- **并发生成**: Stage 3 ThreadPoolExecutor，3 张图 15s (vs 串行 45s)
- **Prompt 分层**: System/User/Negative 三层构造
- **Critic 反馈闭环**: 低分维度自动增强重生成 prompt
- **品牌色量化**: ΔE CIE76 色彩距离比对
- **18 条反模式规则**: 文字/色彩/构图/品牌/AI 通病自动检测
- **成本追踪**: CostTracker 预算上限 + 实时计数
- **安全模块**: Prompt 注入过滤 (17 条中英文规则) + API Key 保护 + 输出文件校验 + 路径沙箱
- **Pre-flight 检查**: 5 项启动前验证
- **自动清理**: 7 天过期 Pipeline 目录清理
- **运行时指标**: metrics.jsonl 每阶段耗时/成本/成功率
- **人工双 Gate**: Stage 2→3 和 Stage 4→5 之间的审批
- **状态恢复**: `--resume` 断点续传
- **8 种创意角度库**: 痛点/利益/社交证明/权威/好奇/竞品/紧迫感/故事
- **12 种设计风格库**: 科技冷峻/温暖关怀/专业企业/极简高端/活力冲击...
- **多平台导出**: 8 平台 20+ 尺寸适配

### Fixed (from v1.0 review)
- P0-1: API Key 保护 (S1)
- P0-2: 成本追踪 (O1)
- P0-3: Prompt 注入过滤 (S2)
- P0-4: 输出文件安全校验 (S3)
- P1-1: Stage 3 并发生成 (A1)
- P1-2: Prompt 分层 (M1)
- P1-3: Critic → Prompt 反馈闭环 (M2)
- P1-4: 品牌色量化比对 (D1)
- P1-5: 脏数据自动清理 (O2)
- P1-6: Pre-flight 健康检查 (O3)
- P1-7: 工期重估 12→18 天 (T1)
- P2-1: ImageProvider 抽象接口 (A5)
- P2-2: 设计反模式库 (D2)
- P2-3: 降级策略 (T2)
- P2-4: 运行时指标 (O4)
- P2-5: 输出路径沙箱 (S4)

### Known Issues
- gpt-image-2 via 中转站不稳定 (限流/超时)，默认 fallback DashScope
- DashScope 不保证中文文字精确渲染
- Stage 4 PIL 修复仅限基础色彩/对比度，复杂问题需重生成
- CRLF 行尾在某些 Windows 环境下导致 patch 工具失败

---

## v1.0.0 (2026-05-02) — Design Phase

### Created
- 完整架构设计文档 (1,242 行)
- 六专家交叉评审 (Architect/Security/AI-ML/Designer/Tech-Lead/DevOps)
- 3 份 ADR (架构决策记录)
- 实施计划 (7 Phase, 18 天)
