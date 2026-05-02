# OWASP Top 10 (2021) 防护指南

> 本文档为安全专家技能的参考资料，涵盖 OWASP Top 10 每一项的风险描述、攻击示例、防护代码和检查清单。
> 代码示例基于 FastAPI (Python) 和 Next.js (TypeScript) 技术栈。

---

## A01: 访问控制失效 (Broken Access Control)

### 风险描述

访问控制确保用户只能在其权限范围内操作。失效的访问控制允许攻击者越权访问、修改或删除数据。常见问题包括：IDOR（不安全的直接对象引用）、越权访问、路径遍历、CORS 配置错误。

### 攻击示例

```
# IDOR 攻击：修改 URL 中的 ID 访问他人数据
GET /api/users/1001/profile  →  GET /api/users/1002/profile

# 越权操作：普通用户访问管理接口
POST /api/admin/delete-user
```

### FastAPI 防护代码

```python
from fastapi import Depends, HTTPException, status

# 资源级别权限校验 — 防止 IDOR
async def get_order(order_id: int, current_user: User = Depends(get_current_user)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    # 关键：校验资源归属
    if order.user_id != current_user.id and not current_user.has_role("admin"):
        raise HTTPException(status_code=403, detail="无权访问此资源")
    return order

# 基于装饰器的权限守卫
from functools import wraps

def require_roles(*roles: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
            if not any(role in current_user.roles for role in roles):
                raise HTTPException(status_code=403, detail="权限不足")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

@app.delete("/api/admin/users/{user_id}")
@require_roles("admin", "super_admin")
async def delete_user(user_id: int, current_user: User = Depends(get_current_user)):
    await db.delete(User, user_id)
    return {"message": "用户已删除"}
```

### Next.js 防护代码

```typescript
// middleware.ts — 路由级别访问控制
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { verifyToken } from "@/lib/auth";

const PROTECTED_ROUTES: Record<string, string[]> = {
  "/admin": ["admin", "super_admin"],
  "/dashboard": ["admin", "user"],
};

export async function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const payload = await verifyToken(token);
  if (!payload) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // 检查路由权限
  for (const [path, roles] of Object.entries(PROTECTED_ROUTES)) {
    if (request.nextUrl.pathname.startsWith(path)) {
      if (!roles.includes(payload.role)) {
        return NextResponse.redirect(new URL("/unauthorized", request.url));
      }
    }
  }

  return NextResponse.next();
}
```

### 检查清单

- [ ] 每个 API 端点都有认证和授权检查
- [ ] 资源访问时校验所有者身份（防止 IDOR）
- [ ] 默认拒绝策略：未明确授权的请求一律拒绝
- [ ] CORS 仅允许受信任的来源
- [ ] 目录列表已禁用，`.git` / `.env` 等文件不可访问

---

## A02: 加密失效 (Cryptographic Failures)

### 风险描述

敏感数据（密码、信用卡号、个人信息）未加密或使用弱加密算法。包括：明文传输、弱哈希算法（MD5/SHA1）、密钥硬编码、缺少 TLS。

### 攻击示例

```python
# 错误：使用 MD5 存储密码
import hashlib
password_hash = hashlib.md5(password.encode()).hexdigest()  # 极易被彩虹表破解

# 错误：密钥硬编码
SECRET_KEY = "my-secret-key-123"  # 泄露到版本控制
```

### FastAPI 防护代码

```python
# 密码哈希 — 推荐 Argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher(
    time_cost=3,        # 迭代次数
    memory_cost=65536,  # 内存消耗 64MB
    parallelism=4,      # 并行线程
    hash_len=32,        # 哈希长度
    salt_len=16,        # 盐长度
)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except VerifyMismatchError:
        return False

# 数据加密 — AES-256-GCM
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def encrypt_sensitive_data(plaintext: bytes, key: bytes) -> bytes:
    """使用 AES-256-GCM 加密敏感数据"""
    nonce = os.urandom(12)  # 96-bit nonce
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext  # nonce 拼接密文

def decrypt_sensitive_data(data: bytes, key: bytes) -> bytes:
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)

# TLS 配置 — 生产环境使用 TLS 1.3
# uvicorn main:app --ssl-keyfile=key.pem --ssl-certfile=cert.pem --ssl-version=TLSv1.3
```

### 检查清单

- [ ] 密码使用 Argon2 或 bcrypt 哈希存储
- [ ] 敏感数据使用 AES-256-GCM 加密
- [ ] 传输层强制 TLS 1.2+，推荐 TLS 1.3
- [ ] 密钥通过环境变量或密钥管理服务注入，不硬编码
- [ ] 禁用 MD5、SHA1 等弱哈希算法

---

## A03: 注入 (Injection)

### 风险描述

攻击者将恶意数据作为命令或查询的一部分发送。常见类型包括 SQL 注入、NoSQL 注入、OS Command 注入、LDAP 注入。

### 攻击示例

```python
# SQL 注入
query = f"SELECT * FROM users WHERE name = '{user_input}'"
# 输入: ' OR '1'='1' --    → 返回所有用户

# OS Command 注入
os.system(f"ping {user_input}")
# 输入: 127.0.0.1; rm -rf /   → 执行恶意命令
```

### FastAPI 防护代码

```python
# SQL 注入防护 — 使用 ORM（SQLAlchemy）
from sqlalchemy.orm import Session
from sqlalchemy import text

# 正确：使用 ORM 查询
def get_user_by_name(db: Session, name: str):
    return db.query(User).filter(User.name == name).first()

# 正确：使用参数化查询
def search_users(db: Session, keyword: str):
    stmt = text("SELECT * FROM users WHERE name LIKE :keyword")
    return db.execute(stmt, {"keyword": f"%{keyword}%"}).fetchall()

# 错误示范（绝不使用）：
# db.execute(f"SELECT * FROM users WHERE name = '{name}'")

# OS Command 注入防护 — 使用 subprocess 参数列表
import subprocess
import shlex

def safe_ping(host: str):
    # 输入验证
    import re
    if not re.match(r'^[a-zA-Z0-9.\-]+$', host):
        raise ValueError("无效的主机名")
    # 使用参数列表而非字符串拼接
    result = subprocess.run(
        ["ping", "-c", "4", host],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout

# NoSQL 注入防护 — MongoDB
from bson import ObjectId

async def get_user(user_id: str):
    # 验证 ObjectId 格式
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="无效的用户 ID")
    return await collection.find_one({"_id": ObjectId(user_id)})

# 输入验证 — Pydantic 模型
from pydantic import BaseModel, validator
import re

class UserSearch(BaseModel):
    keyword: str

    @validator("keyword")
    def sanitize_keyword(cls, v):
        if not re.match(r'^[\w\s\u4e00-\u9fff]+$', v):
            raise ValueError("搜索关键词包含非法字符")
        if len(v) > 100:
            raise ValueError("搜索关键词过长")
        return v.strip()
```

### Next.js 防护代码

```typescript
// API Route 输入验证 — 使用 zod
import { z } from "zod";

const searchSchema = z.object({
  keyword: z.string().min(1).max(100).regex(/^[\w\s\u4e00-\u9fff]+$/),
  page: z.number().int().positive().default(1),
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const result = searchSchema.safeParse({
    keyword: searchParams.get("keyword"),
    page: Number(searchParams.get("page")),
  });

  if (!result.success) {
    return Response.json({ error: "参数验证失败" }, { status: 400 });
  }

  // 使用 Prisma ORM 查询（自动防 SQL 注入）
  const users = await prisma.user.findMany({
    where: { name: { contains: result.data.keyword } },
    skip: (result.data.page - 1) * 20,
    take: 20,
  });
  return Response.json(users);
}
```

### 检查清单

- [ ] 所有 SQL 使用 ORM 或参数化查询
- [ ] 系统命令使用 subprocess 参数列表，禁止字符串拼接
- [ ] 所有用户输入使用 Pydantic/zod 校验
- [ ] NoSQL 查询验证数据类型和格式
- [ ] HTML 输出自动转义（React/Jinja2 默认行为）

---

## A04: 不安全设计 (Insecure Design)

### 风险描述

设计层面的安全缺陷，无法通过代码修补解决。包括缺少威胁建模、业务逻辑漏洞、缺乏速率限制。

### 防护策略

```python
# 速率限制 — 使用 slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/auth/login")
@limiter.limit("5/minute")  # 每分钟最多 5 次登录尝试
async def login(request: Request, credentials: LoginForm):
    # 登录逻辑
    pass

# 业务逻辑保护 — 幂等性检查
from fastapi import Header

@app.post("/api/orders")
async def create_order(
    order: OrderCreate,
    idempotency_key: str = Header(...),
    current_user: User = Depends(get_current_user),
):
    # 幂等性检查：防止重复提交
    existing = await db.get_order_by_idempotency_key(idempotency_key)
    if existing:
        return existing
    return await db.create_order(order, current_user.id, idempotency_key)
```

### 检查清单

- [ ] 关键业务流程已进行威胁建模（STRIDE）
- [ ] 敏感操作有速率限制
- [ ] 支付/转账等操作有幂等性保护
- [ ] 业务规则在服务端验证，不依赖前端

---

## A05: 安全配置错误 (Security Misconfiguration)

### 风险描述

默认配置、不完整配置、开放的云存储、不必要的 HTTP 头、详细的错误信息泄露敏感信息。

### FastAPI 防护代码

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    docs_url=None if IS_PRODUCTION else "/docs",   # 生产环境禁用文档
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# CORS 严格配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # 不使用 ["*"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# 全局异常处理 — 隐藏内部错误细节
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},  # 不暴露堆栈信息
    )
```

### 加固清单

- [ ] 生产环境禁用调试模式和 API 文档
- [ ] CORS 配置白名单模式，不使用通配符
- [ ] 异常处理器隐藏内部错误详情
- [ ] 移除 Server/X-Powered-By 等信息泄露头
- [ ] 文件上传限制大小和类型
- [ ] 禁用不必要的 HTTP 方法（TRACE、OPTIONS）

---

## A06: 易受攻击和过时组件 (Vulnerable and Outdated Components)

### 风险描述

使用存在已知漏洞的库、框架或组件。依赖链中的任何环节都可能引入风险。

### 依赖扫描工具

```bash
# Python 依赖扫描
pip install pip-audit
pip-audit                          # 扫描已安装的包
pip-audit -r requirements.txt      # 扫描依赖文件

# 使用 safety 扫描
pip install safety
safety check

# Node.js 依赖扫描
npm audit                          # 内置审计
npm audit fix                      # 自动修复
npx audit-ci --moderate            # CI 集成，中等以上阻断

# pnpm 依赖扫描
pnpm audit
pnpm audit --fix

# 通用工具 — Trivy
trivy fs .                         # 扫描项目目录
trivy image myapp:latest           # 扫描 Docker 镜像
```

### CI/CD 集成

```yaml
# GitHub Actions — 依赖扫描
- name: Python 依赖审计
  run: |
    pip install pip-audit
    pip-audit -r requirements.txt --strict

- name: Node.js 依赖审计
  run: pnpm audit --audit-level=moderate
```

### 检查清单

- [ ] CI/CD 流水线集成依赖扫描
- [ ] 定期更新依赖版本（至少每月一次）
- [ ] 使用 Dependabot / Renovate 自动化依赖更新
- [ ] 监控 CVE 公告（NVD、GitHub Advisory）

---

## A07: 身份识别和认证失败 (Identification and Authentication Failures)

### 风险描述

弱密码策略、缺乏暴力破解保护、未实现 MFA、Session 固定攻击。

### FastAPI 防护代码

```python
# 密码复杂度验证
import re
from pydantic import BaseModel, validator

class PasswordPolicy(BaseModel):
    password: str

    @validator("password")
    def validate_strength(cls, v):
        if len(v) < 12:
            raise ValueError("密码长度至少 12 位")
        if not re.search(r'[A-Z]', v):
            raise ValueError("需要至少一个大写字母")
        if not re.search(r'[a-z]', v):
            raise ValueError("需要至少一个小写字母")
        if not re.search(r'\d', v):
            raise ValueError("需要至少一个数字")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("需要至少一个特殊字符")
        return v

# 暴力破解防护 — 账户锁定
from datetime import datetime, timedelta

class LoginAttemptTracker:
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    async def check_and_record(self, username: str, success: bool):
        key = f"login_attempts:{username}"
        attempts = await redis.get(key)

        if attempts and int(attempts) >= self.MAX_ATTEMPTS:
            ttl = await redis.ttl(key)
            raise HTTPException(
                status_code=429,
                detail=f"账户已锁定，请在 {ttl} 秒后重试"
            )

        if not success:
            await redis.incr(key)
            await redis.expire(key, int(self.LOCKOUT_DURATION.total_seconds()))
        else:
            await redis.delete(key)

# TOTP 双因素认证
import pyotp

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # 允许前后 30 秒偏移
```

### 检查清单

- [ ] 密码策略：最少 12 位，含大小写、数字、特殊字符
- [ ] 暴力破解防护：5 次失败后锁定 15 分钟
- [ ] 敏感操作启用 MFA（TOTP/WebAuthn）
- [ ] Session ID 在登录后重新生成（防 Session 固定）
- [ ] 使用安全的密码重置流程（带过期的一次性令牌）

---

## A08: 软件和数据完整性失败 (Software and Data Integrity Failures)

### 风险描述

软件更新、CI/CD 管道和反序列化缺乏完整性验证。供应链攻击正在成为主要威胁。

### 防护策略

```bash
# npm 锁文件完整性 — 使用 --frozen-lockfile
pnpm install --frozen-lockfile     # CI 中确保使用锁文件

# Python 依赖哈希校验
pip install --require-hashes -r requirements.txt

# requirements.txt 带哈希
# flask==3.0.0 --hash=sha256:xxxx
```

```python
# 反序列化安全 — 禁止 pickle 反序列化不可信数据
import json

# 正确：使用 JSON
data = json.loads(user_input)

# 错误：不要对不可信数据使用 pickle
# import pickle
# data = pickle.loads(user_input)  # 远程代码执行风险！

# Webhook 签名验证
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### 检查清单

- [ ] CI/CD 使用锁文件和哈希校验
- [ ] 禁止反序列化不可信数据（pickle/yaml.load）
- [ ] Webhook 回调验证签名
- [ ] Docker 镜像使用固定摘要而非 latest 标签
- [ ] 代码签名和发布流程有完整性校验

---

## A09: 安全日志和监控失败 (Security Logging and Monitoring Failures)

### 风险描述

缺乏充分的日志记录和监控使攻击难以被检测。平均攻击检测时间超过 200 天。

### FastAPI 安全日志

```python
import logging
import structlog
from datetime import datetime

# 结构化安全日志
security_logger = structlog.get_logger("security")

# 记录认证事件
async def log_auth_event(event_type: str, username: str, ip: str, success: bool, detail: str = ""):
    security_logger.info(
        "auth_event",
        event_type=event_type,
        username=username,
        ip_address=ip,
        success=success,
        detail=detail,
        timestamp=datetime.utcnow().isoformat(),
    )

# 记录访问控制事件
async def log_access_event(user_id: int, resource: str, action: str, allowed: bool):
    security_logger.info(
        "access_event",
        user_id=user_id,
        resource=resource,
        action=action,
        allowed=allowed,
        timestamp=datetime.utcnow().isoformat(),
    )

# 关键：不要在日志中记录敏感数据
# 错误：logger.info(f"用户登录: password={password}")
# 正确：logger.info(f"用户登录: username={username}")
```

### 告警规则示例

```yaml
# Prometheus 告警规则
groups:
  - name: security_alerts
    rules:
      - alert: BruteForceDetected
        expr: rate(auth_failures_total[5m]) > 10
        for: 1m
        annotations:
          summary: "检测到暴力破解攻击"

      - alert: UnauthorizedAccessSpike
        expr: rate(http_responses_total{status="403"}[5m]) > 20
        for: 2m
        annotations:
          summary: "403 响应异常增多"
```

### 检查清单

- [ ] 记录所有认证事件（登录、登出、失败）
- [ ] 记录访问控制失败事件
- [ ] 日志中不包含密码、令牌等敏感信息
- [ ] 日志集中存储且防篡改
- [ ] 配置告警规则：暴力破解、异常访问模式

---

## A10: 服务器端请求伪造 (Server-Side Request Forgery, SSRF)

### 风险描述

攻击者让服务器发起非预期的请求，访问内部服务、云元数据端点或内网资源。

### 攻击示例

```
# 访问云实例元数据
POST /api/fetch-url
{"url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"}

# 访问内网服务
{"url": "http://192.168.1.100:6379/"}  # 直接访问内网 Redis
```

### FastAPI 防护代码

```python
import ipaddress
from urllib.parse import urlparse
import socket

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # 云元数据
    ipaddress.ip_network("0.0.0.0/8"),
]

def validate_url(url: str) -> str:
    """验证 URL 安全性，防止 SSRF"""
    parsed = urlparse(url)

    # 协议白名单
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"不允许的协议: {parsed.scheme}")

    # 域名白名单（推荐）
    ALLOWED_DOMAINS = ["api.example.com", "cdn.example.com"]
    if parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(f"不允许的域名: {parsed.hostname}")

    # 解析 IP 并检查是否为内网地址
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(f"不允许访问内网地址: {ip}")
    except socket.gaierror:
        raise ValueError(f"无法解析域名: {parsed.hostname}")

    return url

@app.post("/api/fetch-url")
async def fetch_external_url(url: str):
    safe_url = validate_url(url)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(safe_url, follow_redirects=False)
        return {"status": response.status_code, "body": response.text[:1000]}
```

### 检查清单

- [ ] 用户提供的 URL 进行协议白名单检查
- [ ] DNS 解析结果检查，阻止内网 IP
- [ ] 使用域名白名单而非黑名单
- [ ] 禁止 HTTP 重定向跟踪（或重定向后再次验证）
- [ ] 云环境中使用 IMDSv2 或禁用实例元数据

---

## 快速参考表

| 编号 | 名称 | 核心防护 |
|------|------|----------|
| A01 | 访问控制失效 | RBAC + 资源归属校验 + 默认拒绝 |
| A02 | 加密失效 | Argon2 + AES-256-GCM + TLS 1.3 |
| A03 | 注入 | ORM + 参数化查询 + 输入验证 |
| A04 | 不安全设计 | 威胁建模 + 速率限制 + 幂等性 |
| A05 | 安全配置错误 | 生产加固 + CORS 白名单 + 错误隐藏 |
| A06 | 易受攻击组件 | pip-audit + npm audit + CI 集成 |
| A07 | 认证失败 | 强密码策略 + 账户锁定 + MFA |
| A08 | 数据完整性失败 | 锁文件 + 签名验证 + 禁止 pickle |
| A09 | 日志监控不足 | 结构化日志 + 告警规则 + 集中存储 |
| A10 | SSRF | URL 白名单 + IP 检查 + 禁止重定向 |
