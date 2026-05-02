# 认证授权实现模式与安全头配置

> 本文档为安全专家技能的参考资料，涵盖主流认证授权模式的实现细节和安全头配置速查。
> 代码示例基于 FastAPI (Python) 和 Next.js (TypeScript) 技术栈。

---

## JWT 实现模式

### Access/Refresh Token 双令牌机制

核心思想：Access Token 短期有效（15-30 分钟），Refresh Token 长期有效（7-30 天）。Access Token 用于接口认证，Refresh Token 用于获取新的 Access Token。

### FastAPI JWT 完整实现

```python
from datetime import datetime, timedelta
from typing import Optional
import jwt
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# 配置
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=30)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)

security = HTTPBearer()

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

def create_access_token(user_id: int, roles: list[str]) -> str:
    payload = {
        "sub": str(user_id),
        "roles": roles,
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + ACCESS_TOKEN_EXPIRE,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + REFRESH_TOKEN_EXPIRE,
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=ALGORITHM)

def create_token_pair(user_id: int, roles: list[str]) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id, roles),
        refresh_token=create_refresh_token(user_id),
    )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="无效的令牌类型")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="令牌已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的令牌")

# Token 轮转 — 每次刷新时生成新的 Refresh Token
@app.post("/api/auth/refresh")
async def refresh_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, JWT_REFRESH_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="无效的令牌类型")

        # 检查黑名单（已撤销的 Refresh Token）
        jti = payload.get("jti")
        if jti and await redis.exists(f"revoked_token:{jti}"):
            raise HTTPException(status_code=401, detail="令牌已撤销")

        user_id = int(payload["sub"])
        user = await db.get_user(user_id)
        # 生成新的令牌对（Token 轮转）
        return create_token_pair(user.id, user.roles)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

# Token 黑名单 — 使用 Redis 存储已撤销的令牌
async def revoke_token(token: str, token_type: str = "access"):
    secret = JWT_SECRET if token_type == "access" else JWT_REFRESH_SECRET
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"])
    ttl = (exp - datetime.utcnow()).total_seconds()
    if ttl > 0:
        await redis.setex(f"revoked_token:{token}", int(ttl), "1")
```

### Next.js Middleware JWT 验证

```typescript
// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

const JWT_SECRET = new TextEncoder().encode(process.env.JWT_SECRET!);

interface JWTPayload {
  sub: string;
  roles: string[];
  type: string;
  exp: number;
}

async function verifyAccessToken(token: string): Promise<JWTPayload | null> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET);
    if (payload.type !== "access") return null;
    return payload as unknown as JWTPayload;
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  // 公开路由跳过验证
  const publicPaths = ["/login", "/register", "/api/auth/refresh"];
  if (publicPaths.some((p) => request.nextUrl.pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // 从 Cookie 或 Authorization Header 获取令牌
  const token =
    request.cookies.get("access_token")?.value ||
    request.headers.get("Authorization")?.replace("Bearer ", "");

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const payload = await verifyAccessToken(token);
  if (!payload) {
    // 令牌无效或过期，尝试刷新
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // 将用户信息注入请求头传递给 API Route
  const response = NextResponse.next();
  response.headers.set("x-user-id", payload.sub);
  response.headers.set("x-user-roles", JSON.stringify(payload.roles));
  return response;
}

export const config = {
  matcher: ["/dashboard/:path*", "/api/protected/:path*", "/admin/:path*"],
};
```

---

## OAuth 2.0 / OpenID Connect

### 授权码流程 (Authorization Code Flow)

适用于有后端的 Web 应用，是最安全的 OAuth 流程。

```
用户 → 应用 → 授权服务器（获取授权码）→ 应用后端（用授权码换令牌）→ 资源服务器
```

### PKCE 扩展 (Proof Key for Code Exchange)

适用于 SPA 和移动应用，防止授权码拦截攻击。

```typescript
// Next.js — OAuth PKCE 实现
import crypto from "crypto";

function generateCodeVerifier(): string {
  return crypto.randomBytes(32).toString("base64url");
}

function generateCodeChallenge(verifier: string): string {
  return crypto.createHash("sha256").update(verifier).digest("base64url");
}

// 发起授权请求
export async function GET(request: Request) {
  const codeVerifier = generateCodeVerifier();
  const codeChallenge = generateCodeChallenge(codeVerifier);

  // 存储 code_verifier 到 session（后续换令牌时需要）
  cookies().set("code_verifier", codeVerifier, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: 600, // 10 分钟
  });

  const authUrl = new URL("https://provider.com/oauth/authorize");
  authUrl.searchParams.set("client_id", process.env.OAUTH_CLIENT_ID!);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("redirect_uri", process.env.OAUTH_REDIRECT_URI!);
  authUrl.searchParams.set("scope", "openid profile email");
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");
  authUrl.searchParams.set("state", crypto.randomBytes(16).toString("hex"));

  return Response.redirect(authUrl.toString());
}
```

### 常见 OAuth 提供商配置

```python
# FastAPI — Google OAuth 配置示例
OAUTH_PROVIDERS = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scopes": ["openid", "profile", "email"],
    },
    "github": {
        "client_id": os.getenv("GITHUB_CLIENT_ID"),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": ["read:user", "user:email"],
    },
}
```

---

## Session 认证

### Cookie 安全配置

```python
# FastAPI — 安全 Cookie 设置
from fastapi.responses import JSONResponse

def set_auth_cookie(response: JSONResponse, session_id: str):
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,     # 禁止 JavaScript 访问（防 XSS 窃取）
        secure=True,       # 仅通过 HTTPS 发送
        samesite="lax",    # 防 CSRF（lax 允许顶级导航携带）
        max_age=3600,      # 1 小时过期
        path="/",
        domain=".yourdomain.com",  # 限定域名
    )
```

### Redis Session Store

```python
import secrets
from datetime import timedelta

class RedisSessionStore:
    PREFIX = "session:"
    DEFAULT_TTL = timedelta(hours=1)

    def __init__(self, redis_client):
        self.redis = redis_client

    async def create(self, user_id: int, data: dict) -> str:
        session_id = secrets.token_urlsafe(32)
        session_data = {"user_id": user_id, **data}
        await self.redis.setex(
            f"{self.PREFIX}{session_id}",
            int(self.DEFAULT_TTL.total_seconds()),
            json.dumps(session_data),
        )
        return session_id

    async def get(self, session_id: str) -> dict | None:
        data = await self.redis.get(f"{self.PREFIX}{session_id}")
        if not data:
            return None
        # 滑动过期：每次访问续期
        await self.redis.expire(
            f"{self.PREFIX}{session_id}",
            int(self.DEFAULT_TTL.total_seconds()),
        )
        return json.loads(data)

    async def destroy(self, session_id: str):
        await self.redis.delete(f"{self.PREFIX}{session_id}")

    async def regenerate(self, old_session_id: str) -> str:
        """登录后重新生成 Session ID（防 Session 固定攻击）"""
        data = await self.get(old_session_id)
        if not data:
            raise ValueError("Session 不存在")
        await self.destroy(old_session_id)
        return await self.create(data["user_id"], data)
```

---

## RBAC 实现模式

### 角色-权限模型

```python
# FastAPI — 完整 RBAC 实现
from enum import Enum
from typing import List
from fastapi import Depends, HTTPException

class Permission(str, Enum):
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    ORDER_READ = "order:read"
    ORDER_WRITE = "order:write"
    ADMIN_PANEL = "admin:panel"

class Role(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"

ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.VIEWER: [Permission.USER_READ, Permission.ORDER_READ],
    Role.EDITOR: [Permission.USER_READ, Permission.USER_WRITE, Permission.ORDER_READ, Permission.ORDER_WRITE],
    Role.ADMIN: list(Permission),  # 管理员拥有所有权限
}

def require_permission(*permissions: Permission):
    """权限守卫依赖注入"""
    async def checker(current_user: dict = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        user_permissions = set()
        for role in user_roles:
            user_permissions.update(ROLE_PERMISSIONS.get(Role(role), []))

        for perm in permissions:
            if perm not in user_permissions:
                raise HTTPException(status_code=403, detail=f"缺少权限: {perm.value}")
        return current_user
    return checker

# 使用示例
@app.get("/api/users")
async def list_users(user=Depends(require_permission(Permission.USER_READ))):
    return await db.get_all_users()

@app.delete("/api/users/{user_id}")
async def delete_user(
    user_id: int,
    user=Depends(require_permission(Permission.USER_DELETE)),
):
    await db.delete_user(user_id)
    return {"message": "用户已删除"}
```

### Next.js 前端路由守卫

```typescript
// hooks/useAuth.ts
"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

interface AuthOptions {
  requiredRoles?: string[];
  redirectTo?: string;
}

export function useAuth(options: AuthOptions = {}) {
  const { requiredRoles = [], redirectTo = "/login" } = options;
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace(redirectTo);
      return;
    }

    // 解析 JWT payload（仅用于前端路由守卫，后端仍需完整验证）
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const userRoles: string[] = payload.roles || [];

      if (requiredRoles.length > 0) {
        const hasRequired = requiredRoles.some((r) => userRoles.includes(r));
        if (!hasRequired) {
          router.replace("/unauthorized");
        }
      }
    } catch {
      router.replace(redirectTo);
    }
  }, [requiredRoles, redirectTo, router]);
}

// 页面使用示例
// app/admin/page.tsx
export default function AdminPage() {
  useAuth({ requiredRoles: ["admin"] });

  return <div>管理后台内容</div>;
}
```

---

## 安全头配置速查

### Content-Security-Policy (CSP)

控制浏览器允许加载的资源来源，有效防止 XSS。

```python
# FastAPI — CSP 配置
CSP_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'nonce-{nonce}'",    # 允许带 nonce 的内联脚本
    "style-src 'self' 'unsafe-inline'",      # 样式通常需要 inline
    "img-src 'self' data: https:",           # 允许 HTTPS 图片
    "font-src 'self'",
    "connect-src 'self' https://api.example.com",
    "frame-ancestors 'none'",                # 禁止被嵌入 iframe
    "base-uri 'self'",
    "form-action 'self'",
])
```

### Strict-Transport-Security (HSTS)

强制浏览器使用 HTTPS 连接。

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

- `max-age=31536000`: 一年内强制 HTTPS
- `includeSubDomains`: 子域名也强制 HTTPS
- `preload`: 申请加入浏览器 HSTS 预加载列表

### X-Frame-Options

防止页面被嵌入 iframe（Clickjacking 防护）。

```
X-Frame-Options: DENY          # 完全禁止
X-Frame-Options: SAMEORIGIN    # 仅同源允许
```

### X-Content-Type-Options

防止浏览器 MIME 类型嗅探。

```
X-Content-Type-Options: nosniff
```

### Permissions-Policy

控制浏览器功能的使用权限。

```
Permissions-Policy: camera=(), microphone=(), geolocation=(self), payment=()
```

### 完整安全头中间件

```python
# FastAPI — 完整安全头中间件
import secrets
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        # CSP
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data: https:; "
            f"font-src 'self'; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'"
        )
        # HSTS
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        # 其他安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(self), payment=()"
        )
        # 移除信息泄露头
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response

app.add_middleware(SecurityHeadersMiddleware)
```

```typescript
// Next.js — next.config.js 安全头配置
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
  {
    key: "Content-Security-Policy",
    value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; frame-ancestors 'none'",
  },
];

module.exports = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};
```

---

## 安全头速查表

| 安全头 | 作用 | 推荐值 |
|--------|------|--------|
| Content-Security-Policy | 防 XSS，控制资源加载 | `default-src 'self'` + 按需放宽 |
| Strict-Transport-Security | 强制 HTTPS | `max-age=31536000; includeSubDomains` |
| X-Frame-Options | 防 Clickjacking | `DENY` |
| X-Content-Type-Options | 防 MIME 嗅探 | `nosniff` |
| Referrer-Policy | 控制 Referer 泄露 | `strict-origin-when-cross-origin` |
| Permissions-Policy | 限制浏览器 API | 按需配置，默认关闭摄像头/麦克风 |
