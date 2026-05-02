# 功能测试与逻辑验证参考

基于实际项目总结的测试模式和验证清单。

## 关键测试矩阵

### 多租户隔离测试 (P0)

```python
# ============================================
# 来源: test_quality_detail.py — 真实项目必测项
# ============================================

class TestMultiUserIsolation:
    """验证用户 A 看不到用户 B 的数据"""

    async def test_multi_user_isolation(self, session):
        # Arrange: 创建两个用户及各自的数据
        user_a = await create_user(session, "user_a")
        user_b = await create_user(session, "user_b")
        conv_a = await create_conversation(session, user_a.id, "用户A的对话")
        conv_b = await create_conversation(session, user_b.id, "用户B的对话")

        # Act: 用户 A 查询数据
        result_a = await get_quality_detail(session, user_id=user_a.id)

        # Assert: 只返回用户 A 的数据
        assert all(r.user_id == user_a.id for r in result_a)
        assert conv_b.id not in [r.conversation_id for r in result_a]
```

### 集成测试: 定时任务生命周期

```python
# ============================================
# 来源: test_golden_lifecycle.py — 验证生命周期 job 实际效果
# ============================================

class TestGoldenLifecycleIntegration:
    """验证低转化率示例被 job 实际停用"""

    async def test_low_conversion_deactivation(self, session):
        # Arrange: 创建低转化率的 golden example
        example = await create_golden_example(session, conversion_rate=0.01)

        # Act: 执行生命周期 job
        with patch('app.services.get_async_session', return_value=session):
            await golden_lifecycle_job()

        # Assert: 示例被停用
        await session.refresh(example)
        assert example.is_active is False
```

### 服务层集成测试: 质量门控

```python
# ============================================
# 来源: test_quality_gate.py — 验证 LLM 质量评分写入
# ============================================

class TestQualityGateIntegration:
    """验证低质量 LLM 回复被正确标记"""

    async def test_low_quality_flagged(self, session):
        # Arrange: Mock LLM 返回低质量回复
        with patch('app.llm.qwen_client.chat', return_value="不知道"):
            message = await handle_new_message(session, conversation_id, "你好")

        # Assert: quality_score 和 quality_flagged 正确写入
        assert message.quality_score < 0.5
        assert message.quality_flagged is True
```

## 前端功能测试清单

```markdown
### UI 交互测试
- [ ] 按钮防抖: 评分/提交/删除按钮是否有 loading 态防止双击重复提交
- [ ] 空态处理: 列表为空时是否显示友好的空态页面
- [ ] 加载态: 数据请求时是否显示 Skeleton/Spinner
- [ ] 错误态: API 失败时是否有错误提示和重试机制
- [ ] 响应式: 移动端/平板/桌面端布局是否正确

### 数据完整性
- [ ] 分页加载: 翻页后数据是否正确，是否有重复
- [ ] 筛选条件: 筛选后分页是否重置到第 1 页
- [ ] 表单验证: 必填字段、格式校验、长度限制
- [ ] 国际化: i18n 键是否全部存在，无 missing key 警告

### 浏览器兼容性
- [ ] 缓存策略: Service Worker 缓存是否正确更新
- [ ] PWA: 离线页面是否正常显示
- [ ] Console: 无 JS 错误、无 unhandled promise rejection
```

## API 逻辑验证清单

```markdown
### 数据流完整性
- [ ] 创建 → 读取: 创建的数据能被正确查询
- [ ] 更新 → 刷新: 更新后 UI 是否同步反映
- [ ] 删除 → 清理: 删除后关联数据是否级联清理
- [ ] 并发 → 一致: 多个请求同时操作是否产生数据不一致

### 业务规则验证
- [ ] 权限边界: 普通用户无法访问管理接口
- [ ] 状态机: 状态转换是否合法（如 pending → processing → completed）
- [ ] 计算逻辑: 统计数据、费用计算、分页总数是否正确
- [ ] 时区处理: 时间戳是否统一使用 UTC 或固定时区（CST）
```
