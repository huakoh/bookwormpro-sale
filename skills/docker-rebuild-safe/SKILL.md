---
name: docker-rebuild-safe
description: >
  Docker容器安全重建 — 源码修改后重建镜像，避免SSH断连、容器丢失等问题。
  触发词：Docker重建、rebuild、容器更新、镜像构建。
maturity: stable
cost_level: medium
---

# Docker 容器安全重建

修改源码后重建 Docker 镜像的注意事项。

## 核心问题

Docker build 期间如果执行 `docker compose down`，可能导致:
- SSH 连接断开（容器管理网络接口）
- 旧的容器被删除但新容器未启动
- 服务中断

## 安全重建流程

### 1. 使用后台模式

```bash
# 不要用前台命令！
# docker build && docker compose down && docker compose up -d  ← SSH会断

# 使用 terminal(background=true)
ssh root@server 'cd /project && docker build -t image:latest . && docker compose down && docker compose up -d'
```

### 2. 验证重建结果

```bash
# 检查容器状态
docker ps --filter "name=container" --format "{{.Status}}"

# 检查运行时间判断是否重建
docker ps --format "{{.Names}} {{.Status}}"
# Up 5 days → 旧容器，未重建
# Up 10 seconds → 新容器

# 验证功能
curl -sk https://domain.com/ | grep -c "expected-content"
```

### 3. 回滚方案

如果构建失败，旧容器可能已被删除:
```bash
# 检查是否有旧镜像可用
docker images | grep image-name
# 如有旧tag，用旧tag启动
docker tag image:old-tag image:latest
docker compose up -d
```

### 4. 找到源码目录

```bash
# 常见位置
/opt/project-name/
/home/user/project/

# 通过 Docker 检查
docker inspect container --format "{{.Config.Image}}"
# 通过docker-compose文件查找
find / -name "docker-compose.yml" -path "*/project*"
```

### 5. JSX/TSX 修改注意事项

修改 React/Next.js 组件时:
- **不要用 sed 在 JSX 标签中间插入** — 会破坏标签结构
- **用 Python 精准替换** — 匹配完整标签块
- **保留备份** — `cp file.tsx file.tsx.bak`
- **构建前检查** — `grep -n "新增内容" file.tsx`

```python
# 正确做法: Python 文件级替换
path = "/opt/project/src/Component.tsx"
with open(path, "r") as f:
    content = f.read()

old = '<a\n    href="https://old.com/"\n    target="_blank">旧链接</a>'
new = '<a href="https://new.com/" target="_blank">新链接</a>\n<a href="https://old.com/" target="_blank">旧链接</a>'

content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
```
