# BookwormPRO 安装指南

## 系统要求

- Python 3.10+
- Git
- 至少一个 LLM API Key（DeepSeek 推荐）

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/huakoh/bookwormpro-sale.git /tmp/bookwormpro-sale
```

### 2. 运行安装脚本

```bash
cd /tmp/bookwormpro-sale
python scripts/setup.py
```

脚本会引导你填入 API Key。

### 3. 快速安装（跳过交互）

```bash
python scripts/setup.py --quick
# 然后手动编辑 ~/.bookwormpro/.env
```

### 4. 验证安装

重启 AI 助手后，输入以下命令验证：

```
bookworm自检
```

如果看到 6 环节体检报告，说明安装成功。

## 手动安装

如果脚本不可用，手动复制：

```bash
# 创建目录
mkdir -p ~/.bookwormpro

# 复制技能（核心）
cp -r skills/ ~/.bookwormpro/skills/

# 复制灵魂文件
cp soul/SOUL.md ~/.bookwormpro/
cp soul/SOUL.md ~/.claude/

# 复制配置模板
cp config/.env.template ~/.bookwormpro/.env
cp config/config.yaml ~/.bookwormpro/config.yaml

# 编辑 .env 填入你的 API Key
nano ~/.bookwormpro/.env
```

## 最少配置

`~/.bookwormpro/.env` 最少需要：

```bash
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

## 验证

```
bookworm自检           # 完整自检
bookworm自检 只看cron  # 只检查定时任务
bookworm自检 只看env   # 只检查环境变量
```

## 更新

```bash
cd /tmp/bookwormpro-sale && git pull
python scripts/setup.py --quick
```

## 卸载

```bash
rm -rf ~/.bookwormpro/skills
rm -rf ~/.bookwormpro/SOUL.md
```

## 常见问题

### Q: 提示 "skill not found"
A: 确认 `~/.bookwormpro/skills/` 目录存在且有 SKILL.md 文件。运行 `python scripts/setup.py` 重新安装。

### Q: API 调用失败
A: 检查 `~/.bookwormpro/.env` 中 API Key 是否正确，确认账户有余额。

### Q: 如何切换主 provider
A: 编辑 `~/.bookwormpro/config.yaml`，修改 `model.provider` 字段。
