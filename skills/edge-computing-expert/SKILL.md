---
name: edge-computing-expert
description: >
  边缘计算专家。当用户需要 Cloudflare Workers、Vercel Edge Functions、Deno Deploy、
  边缘数据库 D1/Turso/Upstash、全球部署、CDN 优化，
  或说 "边缘计算"、"Edge Functions"、"Workers" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-20
---

# 边缘计算专家 (Edge Computing Expert)

> **Output Style**: 本技能使用内联输出规范

精通 Edge Functions、全球部署和边缘优化策略。

## 触发关键词

- **平台**: `Cloudflare Workers`, `Vercel Edge`, `Deno Deploy`
- **技术**: `Edge Functions`, `边缘计算`, `边缘函数`
- **部署**: `全球部署`, `CDN`, `就近访问`
- **数据**: `边缘数据库`, `Turso`, `D1`, `KV`

## 技术栈

### 边缘运行时
- Cloudflare Workers
- Vercel Edge Functions
- Deno Deploy
- Fastly Compute@Edge

### 边缘数据库
- Cloudflare D1 (SQLite)
- Turso (分布式 SQLite)
- Upstash Redis
- PlanetScale (边缘兼容)

## Cloudflare Workers

```typescript
// worker.ts
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    
    // 从边缘 KV 读取缓存
    const cached = await env.CACHE.get(url.pathname);
    if (cached) {
      return new Response(cached, {
        headers: { 'X-Cache': 'HIT' }
      });
    }
    
    // 调用源站
    const response = await fetch(`${env.ORIGIN}${url.pathname}`);
    const data = await response.text();
    
    // 写入缓存
    await env.CACHE.put(url.pathname, data, { expirationTtl: 3600 });
    
    return new Response(data, {
      headers: { 'X-Cache': 'MISS' }
    });
  }
};
```

## Vercel Edge Functions

```typescript
// app/api/geo/route.ts
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'edge';

export async function GET(request: NextRequest) {
  const { geo } = request;
  
  return NextResponse.json({
    country: geo?.country,
    city: geo?.city,
    region: geo?.region,
  });
}
```

## 边缘数据库

### Turso
```typescript
import { createClient } from '@libsql/client';

const client = createClient({
  url: process.env.TURSO_URL,
  authToken: process.env.TURSO_TOKEN,
});

export async function getUser(id: string) {
  const result = await client.execute({
    sql: 'SELECT * FROM users WHERE id = ?',
    args: [id],
  });
  return result.rows[0];
}
```

## 输出规范

- 考虑冷启动时间
- 注意执行时间限制
- 优化包大小
- 使用边缘友好的数据库

## 禁止事项

- ❌ 不要使用不兼容边缘的包
- ❌ 不要忽略执行时间限制
- ❌ 不要阻塞主线程

