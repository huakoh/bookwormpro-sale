# 安全漏洞扫描参考

基于实际项目发现的安全漏洞模式和修复方案。

## 高危: 多租户数据泄露

```
严重等级: P0 (最高)
发现频率: 多次（novo 项目 stats.py, customer_service.py）
```

```python
# ============================================
# 漏洞: API 查询未过滤 user_id，导致跨租户数据泄露
# 来源: stats.py get_ai_quality_report() lines 294-326
# 3 个查询（fallback_count, today_ai_replies, intent_distribution）均无 user_id 过滤
# ============================================

# ❌ 多租户数据泄露
fallback_count = session.query(func.count(Message.id)).filter(
    Message.is_fallback == True
).scalar()  # 所有用户的数据混在一起

# ✅ 添加 user_id 过滤子查询
user_conv_ids = (
    session.query(Conversation.id)
    .filter(Conversation.user_id == current_user.id)
    .subquery()
)
fallback_count = session.query(func.count(Message.id)).filter(
    Message.conversation_id.in_(user_conv_ids),
    Message.is_fallback == True
).scalar()

# 必须验证: 同一 pattern 复用到所有查询中
```

**审计检查点:**
```markdown
- [ ] 所有 SELECT 查询是否包含 user_id/tenant_id 过滤
- [ ] JOIN 查询是否通过 user 关联的 conversation_id 约束
- [ ] 聚合查询（COUNT/SUM/AVG）是否限制在当前用户范围
- [ ] 分页 API 是否返回了其他用户的数据
- [ ] 管理员接口是否有独立的权限检查
```

## 高危: Token 伪造

```
严重等级: P0
发现项目: mybioweb (明远生物官网)
```

```typescript
// ============================================
// 漏洞: Token 无 HMAC 签名验证，任何人可伪造超级管理员
// 来源: auth-store.ts 中 generateToken 使用 Base64 伪签名
// ============================================

// ❌ 伪 JWT: 签名是固定字符串 "sig"
function generateToken(user: AdminUser): string {
  const base64Payload = btoa(JSON.stringify(payload));
  return `myb.${base64Payload}.sig`; // 无真实签名，可伪造
}

// ❌ 攻击者可以直接构造:
const fakeToken = `myb.${btoa(JSON.stringify({
  role: "super_admin",
  username: "attacker"
}))}.sig`;

// ✅ 修复: 使用服务端 JWT 签发 + httpOnly Cookie
// 方案 A: Next.js API Route 签发
import { SignJWT, jwtVerify } from 'jose';
const secret = new TextEncoder().encode(process.env.JWT_SECRET);

export async function createToken(user: AdminUser) {
  return new SignJWT({ sub: user.id, role: user.role })
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('24h')
    .sign(secret);
}

// 方案 B: httpOnly Cookie（推荐）
response.cookies.set('auth-token', token, {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax',
  maxAge: 86400,
});
```

## 中危: 常见安全问题速查表

| 漏洞类型 | 检查方法 | 修复方案 |
|---------|---------|---------|
| SQL 注入 | 搜索字符串拼接 SQL `f"SELECT` | 参数化查询 / ORM |
| XSS | 搜索 `innerHTML`, `dangerouslySetInnerHTML` | `textContent` / 转义 |
| CSRF | 检查 POST 接口是否验证 Origin/Token | SameSite Cookie + CSRF Token |
| 路径穿越 | 搜索用户输入拼接文件路径 | `path.resolve` + 白名单 |
| 硬编码密钥 | 搜索 `password`, `secret`, `key` | 环境变量 `.env` |
| 信息泄露 | 检查错误响应是否暴露堆栈 | 生产环境返回通用错误 |
| CORS 过宽 | 检查 `Access-Control-Allow-Origin: *` | 白名单域名 |
| 缺少安全头 | 检查 `X-Frame-Options`, `CSP`, `HSTS` | 安全中间件 |

## 安全扫描命令

```bash
# 搜索硬编码密钥（正则）
grep -rn "password\s*=\s*['\"]" --include="*.py" --include="*.ts" --include="*.js" .
grep -rn "secret\s*=\s*['\"]" --include="*.py" --include="*.ts" --include="*.js" .

# 搜索 SQL 拼接
grep -rn 'f"SELECT\|f"INSERT\|f"UPDATE\|f"DELETE' --include="*.py" .

# 搜索不安全的 HTML 操作
grep -rn 'innerHTML\|dangerouslySetInnerHTML' --include="*.tsx" --include="*.jsx" .

# 搜索宽泛异常处理
grep -rn 'except Exception\|except:$' --include="*.py" .

# 搜索 any 类型使用
grep -rn 'useState<any>\|: any\b' --include="*.ts" --include="*.tsx" .
```
