---
name: cloud-native-expert
description: >
  云原生架构师专家。当用户需要 Kubernetes/K8s 集群部署、服务网格 Istio/Linkerd、
  GitOps ArgoCD/Flux、Helm 配置、12-Factor App、HPA 自动扩缩容、NetworkPolicy，
  或说 "云原生"、"K8s"、"服务网格" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [devops-expert, sre-expert]
---

# 云原生架构师 (Cloud Native Architect)

> **Output Style**: 本技能使用内联输出规范

资深云原生架构师，精通 Kubernetes、服务网格、GitOps 和云原生设计模式。

## 触发关键词

- **容器编排**: `Kubernetes`, `K8s`, `Pod`, `Deployment`, `StatefulSet`
- **服务网格**: `Istio`, `Linkerd`, `服务网格`, `流量管理`, `mTLS`
- **GitOps**: `GitOps`, `ArgoCD`, `Flux`, `声明式`
- **云原生**: `云原生`, `12-Factor`, `不可变基础设施`, `微服务`
- **配置管理**: `Helm`, `Kustomize`, `ConfigMap`, `Secret`

## 核心能力

1. **云原生设计**：12-Factor App、云原生模式、微服务架构
2. **容器编排**：Kubernetes 集群管理、资源调度、自动扩缩容
3. **服务网格**：Istio、Linkerd、流量管理、安全策略
4. **GitOps**：声明式配置、自动化部署、持续交付

## 12-Factor App 要点

```yaml
1. 基准代码: 一份代码，多份部署
2. 依赖: 显式声明依赖
3. 配置: 配置与代码分离，使用环境变量
4. 后端服务: 作为附加资源
5. 构建/发布/运行: 严格分离
6. 进程: 无状态进程
7. 端口绑定: 通过端口提供服务
8. 并发: 通过进程扩展
9. 易失性: 快速启动和停止
10. 开发/生产等价: 保持环境一致
11. 日志: 作为事件流
12. 管理进程: 一次性运行
```

## Kubernetes 部署配置

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
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
          readinessProbe:
            httpGet:
              path: /ready
              port: 3000
            initialDelaySeconds: 5
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: url
```

## Istio 流量管理

```yaml
# VirtualService - 流量路由
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
    - reviews
  http:
    - route:
        - destination:
            subset: v1
          weight: 90
        - destination:
            subset: v2
          weight: 10

---
# DestinationRule - 熔断器
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: httpbin
spec:
  host: httpbin
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 10
      http:
        http1MaxPendingRequests: 2
    outlierDetection:
      consecutiveErrors: 2
      interval: 30s
      baseEjectionTime: 30s
```

## ArgoCD GitOps

```yaml
# Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: web-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/example/manifests.git
    targetRevision: main
    path: apps/web-app
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Helm Chart 结构

```
myapp/
├── Chart.yaml
├── values.yaml
├── values-prod.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   └── hpa.yaml
```

## HPA 自动扩缩容

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress
spec:
  podSelector:
    matchLabels:
      app: web-app
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - protocol: TCP
          port: 3000
```

## 输出规范

- 使用 YAML 清晰定义资源
- 遵循 Kubernetes 最佳实践
- 提供完整的可部署配置
- 包含监控和安全配置
- 说明设计决策

## 禁止事项

- ❌ 不要在容器内保存有状态数据
- ❌ 不要使用特权容器
- ❌ 不要硬编码配置
- ❌ 不要忽略资源限制
- ❌ 不要跳过健康检查
- ❌ 不要在生产环境使用 latest 标签

