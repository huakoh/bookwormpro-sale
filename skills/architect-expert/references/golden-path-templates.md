# 黄金路径模板示例

基于Backstage Software Templates的黄金路径实现参考。

## 黄金路径设计原则

### 核心理念
- **降低认知负荷**：封装复杂性，暴露简单接口
- **默认安全**：安全配置内置，合规自动满足
- **自助服务**：开发者无需等待审批即可启动
- **透明可学**：生成代码可读可改，作为教学工具

### 模板分层架构

```
开发者输入 (元数据)
        │
        ▼
┌───────────────────┐
│   软件模板        │  ← Backstage Scaffolder
│   (YAML定义)      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   骨架代码        │  ← 标准化项目结构
│   (Skeleton)      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   IaC模块         │  ← Terraform/Helm封装
│   (基础设施)      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   GitOps配置      │  ← ArgoCD/Flux部署
│   (CD流水线)      │
└───────────────────┘
```

---

## 模板示例一：后端微服务

### template.yaml

```yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: backend-service-go
  title: Go 后端微服务
  description: |
    创建一个生产就绪的Go微服务，包含:
    - Gin框架 + 标准项目结构
    - OpenTelemetry可观测性
    - Docker + Kubernetes部署
    - GitHub Actions CI/CD
    - SLSA L3合规
  tags:
    - go
    - backend
    - microservice
    - recommended
spec:
  owner: platform-team
  type: service

  parameters:
    - title: 服务基本信息
      required:
        - name
        - owner
        - description
      properties:
        name:
          title: 服务名称
          type: string
          description: 唯一的服务标识符 (小写字母、数字、连字符)
          pattern: '^[a-z0-9-]+$'
          ui:autofocus: true
        owner:
          title: 负责团队
          type: string
          ui:field: OwnerPicker
          ui:options:
            catalogFilter:
              kind: Group
        description:
          title: 服务描述
          type: string
          description: 简短描述服务用途

    - title: 技术配置
      properties:
        database:
          title: 数据库
          type: string
          enum:
            - none
            - postgresql
            - mysql
          default: none
          description: 选择需要的数据库类型
        cache:
          title: 缓存
          type: boolean
          default: false
          description: 是否需要Redis缓存
        messageQueue:
          title: 消息队列
          type: string
          enum:
            - none
            - kafka
            - sqs
          default: none

    - title: 部署配置
      properties:
        environment:
          title: 初始环境
          type: array
          items:
            type: string
            enum:
              - development
              - staging
              - production
          default:
            - development
            - staging
        region:
          title: 部署区域
          type: string
          enum:
            - ap-northeast-1
            - us-east-1
            - eu-west-1
          default: ap-northeast-1

  steps:
    # Step 1: 生成代码骨架
    - id: fetch-skeleton
      name: 获取代码骨架
      action: fetch:template
      input:
        url: ./skeleton
        values:
          name: ${{ parameters.name }}
          owner: ${{ parameters.owner }}
          description: ${{ parameters.description }}
          database: ${{ parameters.database }}
          cache: ${{ parameters.cache }}
          messageQueue: ${{ parameters.messageQueue }}

    # Step 2: 生成基础设施代码
    - id: generate-infra
      name: 生成基础设施配置
      action: fetch:template
      input:
        url: ./infra-template
        targetPath: ./infra
        values:
          name: ${{ parameters.name }}
          environments: ${{ parameters.environment }}
          region: ${{ parameters.region }}
          database: ${{ parameters.database }}
          cache: ${{ parameters.cache }}

    # Step 3: 创建代码仓库
    - id: publish-github
      name: 创建GitHub仓库
      action: publish:github
      input:
        allowedHosts: ['github.com']
        repoUrl: github.com?owner=our-org&repo=${{ parameters.name }}
        description: ${{ parameters.description }}
        defaultBranch: main
        protectDefaultBranch: true
        requireCodeOwnerReviews: true
        requiredStatusChecks:
          - ci/build
          - ci/test
          - security/scan

    # Step 4: 注册到软件目录
    - id: register-catalog
      name: 注册到软件目录
      action: catalog:register
      input:
        repoContentsUrl: ${{ steps['publish-github'].output.repoContentsUrl }}
        catalogInfoPath: /catalog-info.yaml

    # Step 5: 创建ArgoCD应用
    - id: create-argocd-app
      name: 配置GitOps部署
      action: argocd:create-resources
      input:
        appName: ${{ parameters.name }}
        projectName: default
        repoUrl: ${{ steps['publish-github'].output.remoteUrl }}
        path: ./infra/k8s

  output:
    links:
      - title: 代码仓库
        url: ${{ steps['publish-github'].output.remoteUrl }}
      - title: 软件目录
        icon: catalog
        entityRef: ${{ steps['register-catalog'].output.entityRef }}
      - title: CI流水线
        url: ${{ steps['publish-github'].output.remoteUrl }}/actions
```

### 骨架代码结构

```
skeleton/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── handler/
│   │   └── health.go
│   ├── middleware/
│   │   ├── logging.go
│   │   └── tracing.go
│   ├── repository/
│   └── service/
├── pkg/
│   └── config/
│       └── config.go
├── api/
│   └── openapi.yaml
├── .github/
│   └── workflows/
│       ├── ci.yaml
│       └── release.yaml
├── Dockerfile
├── Makefile
├── go.mod
├── catalog-info.yaml
└── README.md
```

---

## 模板示例二：前端应用

### template.yaml

```yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: frontend-nextjs
  title: Next.js 前端应用
  description: |
    创建一个现代化的Next.js前端应用，包含:
    - Next.js 14 App Router
    - TypeScript + Tailwind CSS
    - shadcn/ui组件库
    - 国际化(i18n)支持
    - Vercel/容器化部署
  tags:
    - nextjs
    - frontend
    - typescript
    - recommended
spec:
  owner: platform-team
  type: website

  parameters:
    - title: 应用基本信息
      required:
        - name
        - owner
      properties:
        name:
          title: 应用名称
          type: string
          pattern: '^[a-z0-9-]+$'
        owner:
          title: 负责团队
          type: string
          ui:field: OwnerPicker

    - title: 功能配置
      properties:
        authentication:
          title: 认证方案
          type: string
          enum:
            - none
            - nextauth
            - auth0
            - custom
          default: none
        i18n:
          title: 国际化
          type: boolean
          default: false
        analytics:
          title: 分析集成
          type: string
          enum:
            - none
            - google-analytics
            - posthog
            - mixpanel
          default: none

    - title: 部署方式
      properties:
        deployTarget:
          title: 部署目标
          type: string
          enum:
            - vercel
            - kubernetes
            - cloudflare-pages
          default: vercel

  steps:
    - id: fetch-skeleton
      name: 获取代码骨架
      action: fetch:template
      input:
        url: ./skeleton-nextjs
        values:
          name: ${{ parameters.name }}
          authentication: ${{ parameters.authentication }}
          i18n: ${{ parameters.i18n }}
          analytics: ${{ parameters.analytics }}

    - id: install-shadcn
      name: 配置shadcn/ui
      action: run:command
      input:
        command: npx shadcn-ui@latest init -y

    - id: publish-github
      name: 创建GitHub仓库
      action: publish:github
      input:
        repoUrl: github.com?owner=our-org&repo=${{ parameters.name }}

    - id: register-catalog
      name: 注册到软件目录
      action: catalog:register
      input:
        repoContentsUrl: ${{ steps['publish-github'].output.repoContentsUrl }}
        catalogInfoPath: /catalog-info.yaml
```

---

## 模板示例三：数据管道

### template.yaml

```yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: data-pipeline
  title: 数据处理管道
  description: |
    创建一个数据处理管道，包含:
    - Python + Pandas/PySpark
    - Airflow DAG定义
    - dbt数据转换
    - 数据质量检查(Great Expectations)
  tags:
    - data
    - python
    - airflow
    - etl
spec:
  owner: data-platform-team
  type: pipeline

  parameters:
    - title: 管道基本信息
      required:
        - name
        - owner
        - schedule
      properties:
        name:
          title: 管道名称
          type: string
        owner:
          title: 负责团队
          type: string
          ui:field: OwnerPicker
        schedule:
          title: 调度频率
          type: string
          enum:
            - '@hourly'
            - '@daily'
            - '@weekly'
            - custom
          default: '@daily'

    - title: 数据源配置
      properties:
        sources:
          title: 数据源
          type: array
          items:
            type: object
            properties:
              type:
                type: string
                enum:
                  - postgresql
                  - mysql
                  - s3
                  - bigquery
                  - api
              connection:
                type: string
```

---

## IaC模块封装示例

### 简化的Terraform模块接口

```hcl
# 开发者只需提供这些参数
module "backend_service" {
  source = "git::https://github.com/our-org/terraform-modules//backend-service"

  # 必填参数
  name        = "order-service"
  environment = "production"
  owner       = "commerce-team"

  # 可选参数 (有合理默认值)
  replicas    = 3
  cpu         = "500m"
  memory      = "1Gi"
  
  # 数据库配置
  database = {
    type     = "postgresql"
    size     = "large"  # small/medium/large，平台团队定义具体规格
  }

  # 缓存配置
  cache = {
    enabled = true
    size    = "medium"
  }
}
```

### 模块内部封装的复杂性

```hcl
# 开发者不需要关心的内部实现
# terraform-modules/backend-service/main.tf

locals {
  # 平台团队定义的规格映射
  db_sizes = {
    small  = { instance_class = "db.t3.micro", storage = 20 }
    medium = { instance_class = "db.t3.small", storage = 50 }
    large  = { instance_class = "db.r5.large", storage = 100 }
  }
}

resource "aws_security_group" "db" {
  # 安全组配置 - 默认最小权限
  ingress {
    from_port   = 5432
    to_port     = 5432
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }
  # ... 更多安全配置
}

resource "aws_db_instance" "main" {
  # 数据库实例配置
  instance_class        = local.db_sizes[var.database.size].instance_class
  allocated_storage     = local.db_sizes[var.database.size].storage
  
  # 默认启用的安全配置
  storage_encrypted     = true
  deletion_protection   = var.environment == "production"
  backup_retention_period = 7
  
  # 默认启用的监控
  performance_insights_enabled = true
  monitoring_interval          = 60
  
  # ... 更多配置
}

resource "aws_kms_key" "db_encryption" {
  # 自动创建的加密密钥
  description             = "KMS key for ${var.name} database encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}
```

---

## 模板质量检查清单

创建新模板前，确认满足以下要求：

### 可用性
- [ ] 参数名称清晰易懂
- [ ] 提供合理的默认值
- [ ] 必填项最小化
- [ ] 有完整的描述信息

### 安全性
- [ ] 默认启用加密
- [ ] 默认最小权限
- [ ] 集成安全扫描
- [ ] 无硬编码密钥

### 可观测性
- [ ] 集成日志收集
- [ ] 集成指标采集
- [ ] 集成分布式追踪
- [ ] 健康检查端点

### 可维护性
- [ ] 生成代码可读
- [ ] 包含README文档
- [ ] 遵循团队规范
- [ ] 版本化模板

### 合规性
- [ ] 满足SLSA要求
- [ ] 自动生成SBOM
- [ ] 符合组织策略
- [ ] 资源标签完整
