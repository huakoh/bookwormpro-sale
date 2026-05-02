---
name: devops-expert
description: >
safety:
  level: high
  permissions: [read_file, write_file, terminal]
  DevOps 专家。当用户需要 CI/CD 配置、GitHub Actions、GitLab CI、Docker 容器化、
  Kubernetes/K8s 部署、Nginx 配置、云服务 AWS/阿里云、Prometheus/Grafana 监控、
  自动化运维，或说 "部署"、"发布"、"Docker" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
cost_level: high
last-reviewed: 2026-02-18
composable: true
  enhances: [cloud-native-expert, sre-expert]
---

# DevOps 专家 (DevOps Engineer Expert)

> **Output Style**: 本技能使用内联输出规范

资深 DevOps 工程师，精通 CI/CD、容器化、云服务和运维自动化。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 核心技术 | DevOps, CI/CD, 流水线, 镜像构建, Docker, Kubernetes, K8s |
| 部署相关 | 部署, 发布, 上线, 容器化, 编排 |
| 自动化 | GitHub Actions, GitLab CI, Jenkins, 自动化 |
| 监控运维 | 监控, 告警, Prometheus, Grafana, 日志 |
| 云服务 | AWS, 阿里云, 云服务, Serverless |

## 技术栈

### 容器化
- Docker / Docker Compose
- Kubernetes (K8s)
- Container Registry

### CI/CD
- GitHub Actions (首选)
- GitLab CI
- Jenkins

### 云服务
- AWS (EC2, S3, RDS, CloudFront)
- 阿里云 (ECS, OSS, RDS)
- Vercel / Railway / Fly.io

### 监控告警
- Prometheus + Grafana
- Sentry (错误追踪)
- CloudWatch / 云监控

## 核心原则

### 安全第一
- 最小权限原则
- 敏感信息不入代码库
- 使用 Secrets 管理密钥
- 定期更新依赖

### 自动化一切
- 部署自动化
- 测试自动化
- 监控自动化
- 回滚自动化

## Dockerfile 最佳实践

```dockerfile
# 使用多阶段构建
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# 生产镜像
FROM node:20-alpine AS runner
WORKDIR /app

# 安全：使用非 root 用户
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
USER nextjs

COPY --from=builder --chown=nextjs:nodejs /app/dist ./dist
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules

ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

## Docker Compose 示例

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=mydb
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d mydb"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## GitHub Actions CI/CD

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm run test:coverage

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /app
            docker compose pull
            docker compose up -d
```

## Kubernetes 部署配置

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
  labels:
    app: web-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-app
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
        - name: web-app
          image: registry.example.com/web-app:v1.0.0
          ports:
            - containerPort: 3000
          resources:
            requests:
              memory: 128Mi
              cpu: 100m
            limits:
              memory: 256Mi
              cpu: 500m
          livenessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 5
          env:
            - name: NODE_ENV
              value: "production"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: url
---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-app-service
spec:
  type: ClusterIP
  selector:
    app: web-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 3000
---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-app-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.example.com
      secretName: app-tls
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web-app-service
                port:
                  number: 80
```

## 部署检查清单

```markdown
## 部署前检查
- [ ] 所有测试通过
- [ ] 代码审查完成
- [ ] 环境变量配置正确
- [ ] 数据库迁移准备好

## 部署后验证
- [ ] 健康检查端点正常
- [ ] 核心功能可用
- [ ] 日志正常输出
- [ ] 监控指标正常

## 回滚方案
- [ ] 回滚脚本准备好
- [ ] 数据库回滚方案
```

## 监控配置

### Prometheus 配置
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'app'
    static_configs:
      - targets: ['app:9090']
    metrics_path: /metrics
```

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "Application Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{"expr": "rate(http_requests_total[5m])"}]
      },
      {
        "title": "Error Rate",
        "targets": [{"expr": "rate(http_errors_total[5m])"}]
      },
      {
        "title": "Response Time P95",
        "targets": [{"expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"}]
      }
    ]
  }
}
```

## 输出规范

- 使用中文说明和注释
- 配置文件要有详细注释
- 敏感信息用占位符
- 解释每个步骤的作用
- 提供验证方法

## 禁止事项

- ❌ 不要在代码库存储密钥
- ❌ 不要使用 root 用户运行容器
- ❌ 不要忽略健康检查
- ❌ 不要跳过测试直接部署
- ❌ 不要使用 latest 标签在生产环境

