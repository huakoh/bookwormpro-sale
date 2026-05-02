# Next.js 15 App Router 完整指南

> 涵盖 App Router 核心约定、数据获取、Server Actions、路由系统、缓存策略、ISR 和中间件。

---

## 一、App Router 核心约定

### 1.1 文件约定

App Router 使用文件系统路由，每个文件夹代表一个路由段，特殊文件名有约定含义：

```
app/
├── layout.tsx          # 根布局（必须）
├── page.tsx            # 首页 /
├── loading.tsx         # 加载 UI（自动包裹 Suspense）
├── error.tsx           # 错误 UI（自动包裹 ErrorBoundary）
├── not-found.tsx       # 404 UI
├── global-error.tsx    # 全局错误处理
├── dashboard/
│   ├── layout.tsx      # 仪表盘布局（嵌套布局）
│   ├── page.tsx        # /dashboard
│   ├── loading.tsx     # 仪表盘加载态
│   └── settings/
│       └── page.tsx    # /dashboard/settings
```

### 1.2 Layout（布局）

Layout 在路由切换时保持状态，不重新渲染，适合放导航、侧边栏等共享 UI。

```tsx
// app/layout.tsx — 根布局
import { Inter } from 'next/font/google';
import '@/styles/globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: { default: '我的应用', template: '%s | 我的应用' },
  description: '应用描述',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={inter.className}>
      <body>
        <header><Navbar /></header>
        <main>{children}</main>
        <footer><Footer /></footer>
      </body>
    </html>
  );
}
```

### 1.3 Loading + Error

```tsx
// app/dashboard/loading.tsx — 自动 Suspense 边界
export default function DashboardLoading() {
  return (
    <div className="grid grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-32 animate-pulse rounded-lg bg-gray-200" />
      ))}
    </div>
  );
}

// app/dashboard/error.tsx — 自动 ErrorBoundary
'use client';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-4 p-8">
      <h2 className="text-xl font-bold">仪表盘加载失败</h2>
      <p className="text-gray-500">{error.message}</p>
      <button onClick={reset} className="btn-primary">重试</button>
    </div>
  );
}
```

---

## 二、数据获取

### 2.1 Server Components 数据获取

Server Components 是默认的，可以直接使用 `async/await`。

```tsx
// app/posts/page.tsx — 直接在组件中获取数据
export default async function PostsPage() {
  // 方式1：使用 fetch（支持缓存控制）
  const res = await fetch('https://api.example.com/posts', {
    next: { revalidate: 3600 }, // 1小时后重新验证
  });
  const posts: Post[] = await res.json();

  // 方式2：直接查询数据库（推荐，减少网络往返）
  // const posts = await db.post.findMany({ orderBy: { createdAt: 'desc' } });

  return (
    <ul>
      {posts.map((post) => (
        <li key={post.id}><PostCard post={post} /></li>
      ))}
    </ul>
  );
}
```

### 2.2 fetch 缓存策略

```tsx
// 强制缓存（默认行为，等同于 SSG）
fetch(url, { cache: 'force-cache' });

// 不缓存（每次请求都重新获取，等同于 SSR）
fetch(url, { cache: 'no-store' });

// 按时间重新验证（ISR）
fetch(url, { next: { revalidate: 60 } }); // 60秒后重新验证

// 按标签重新验证
fetch(url, { next: { tags: ['posts'] } });
// 调用 revalidateTag('posts') 触发重新获取
```

### 2.3 并行数据获取

```tsx
// 避免请求瀑布流，使用 Promise.all 并行获取
export default async function DashboardPage() {
  // 并行发起请求
  const [user, stats, notifications] = await Promise.all([
    getUser(),
    getStats(),
    getNotifications(),
  ]);

  return (
    <div>
      <UserHeader user={user} />
      <StatsGrid stats={stats} />
      <NotificationList items={notifications} />
    </div>
  );
}
```

---

## 三、Server Actions

### 3.1 表单处理

```tsx
// actions/post.ts
'use server';

import { z } from 'zod';
import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

const PostSchema = z.object({
  title: z.string().min(1, '标题不能为空').max(100, '标题不超过100字'),
  content: z.string().min(10, '内容至少10个字符'),
  categoryId: z.string().uuid('分类ID格式错误'),
});

type PostState = {
  errors?: { title?: string[]; content?: string[]; categoryId?: string[] };
  message?: string;
};

export async function createPost(
  prevState: PostState,
  formData: FormData
): Promise<PostState> {
  const parsed = PostSchema.safeParse({
    title: formData.get('title'),
    content: formData.get('content'),
    categoryId: formData.get('categoryId'),
  });

  if (!parsed.success) {
    return { errors: parsed.error.flatten().fieldErrors };
  }

  try {
    const post = await db.post.create({ data: parsed.data });
    revalidatePath('/posts');
    redirect(`/posts/${post.id}`);
  } catch (e) {
    return { message: '创建失败，请稍后重试' };
  }
}
```

### 3.2 useActionState 配合表单

```tsx
'use client';

import { useActionState } from 'react';
import { createPost } from '@/actions/post';

export function CreatePostForm() {
  const [state, formAction, isPending] = useActionState(createPost, {});

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label htmlFor="title">标题</label>
        <input id="title" name="title" className="input" />
        {state.errors?.title?.map((e) => (
          <p key={e} className="text-sm text-red-500">{e}</p>
        ))}
      </div>

      <div>
        <label htmlFor="content">内容</label>
        <textarea id="content" name="content" className="input" rows={6} />
        {state.errors?.content?.map((e) => (
          <p key={e} className="text-sm text-red-500">{e}</p>
        ))}
      </div>

      {state.message && <p className="text-red-500">{state.message}</p>}

      <button type="submit" disabled={isPending} className="btn-primary">
        {isPending ? '发布中...' : '发布文章'}
      </button>
    </form>
  );
}
```

### 3.3 revalidatePath 与 revalidateTag

```tsx
'use server';

import { revalidatePath, revalidateTag } from 'next/cache';

export async function updatePost(id: string, data: PostData) {
  await db.post.update({ where: { id }, data });

  // 方式1：按路径重新验证
  revalidatePath('/posts');           // 重新验证列表页
  revalidatePath(`/posts/${id}`);     // 重新验证详情页

  // 方式2：按标签重新验证（更精确）
  revalidateTag('posts');             // 所有带 posts 标签的 fetch 都重新验证
  revalidateTag(`post-${id}`);        // 特定文章
}
```

---

## 四、路由系统

### 4.1 动态路由

```tsx
// app/posts/[id]/page.tsx — 动态路由段
interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function PostPage({ params }: PageProps) {
  const { id } = await params;
  const post = await db.post.findUnique({ where: { id } });

  if (!post) notFound(); // 触发 not-found.tsx

  return <PostDetail post={post} />;
}

// 静态生成参数（用于 SSG）
export async function generateStaticParams() {
  const posts = await db.post.findMany({ select: { id: true } });
  return posts.map((post) => ({ id: post.id }));
}
```

### 4.2 路由组

```tsx
// 使用 (groupName) 组织路由，不影响 URL 路径
app/
├── (marketing)/
│   ├── layout.tsx        # 营销页面专用布局
│   ├── about/page.tsx    # /about
│   └── pricing/page.tsx  # /pricing
├── (dashboard)/
│   ├── layout.tsx        # 仪表盘专用布局（带侧边栏）
│   ├── overview/page.tsx # /overview
│   └── settings/page.tsx # /settings
```

### 4.3 平行路由

```tsx
// 使用 @slotName 实现平行路由，同一页面渲染多个独立路由
app/dashboard/
├── layout.tsx
├── page.tsx
├── @analytics/
│   └── page.tsx          # 分析面板
├── @activity/
│   └── page.tsx          # 活动面板

// app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
  analytics,
  activity,
}: {
  children: React.ReactNode;
  analytics: React.ReactNode;
  activity: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2">{children}</div>
      <aside>
        {analytics}
        {activity}
      </aside>
    </div>
  );
}
```

### 4.4 拦截路由

```tsx
// 使用 (.) (..) (...) 拦截路由，实现模态框效果
app/
├── feed/
│   ├── page.tsx                    # /feed（帖子列表）
│   ├── (..)photo/[id]/page.tsx     # 拦截：在模态框中打开
├── photo/
│   └── [id]/
│       └── page.tsx                # /photo/123（完整页面）

// 点击 feed 中的图片时，(..)photo/[id] 拦截路由，用模态框展示
// 直接访问 /photo/123 时，走正常的全页面路由
```

---

## 五、缓存策略

### 5.1 四层缓存体系

```
┌─────────────────────────────────────┐
│ 1. Request Memoization (请求去重)    │ → 同一渲染中相同 fetch 自动去重
├─────────────────────────────────────┤
│ 2. Data Cache (数据缓存)            │ → fetch 结果缓存，跨请求持久化
├─────────────────────────────────────┤
│ 3. Full Route Cache (全路由缓存)     │ → 静态路由在构建时缓存 HTML + RSC
├─────────────────────────────────────┤
│ 4. Router Cache (客户端路由缓存)     │ → 浏览器端缓存已访问的路由
└─────────────────────────────────────┘
```

### 5.2 按需重新验证

```tsx
// 方式1：基于时间 — 页面级
export const revalidate = 3600; // 整个路由每3600秒重新验证

// 方式2：基于时间 — fetch 级
fetch(url, { next: { revalidate: 60 } });

// 方式3：按需 — 通过 Server Action 触发
'use server';
import { revalidatePath, revalidateTag } from 'next/cache';

export async function publishPost() {
  await db.post.update({ ... });
  revalidateTag('posts');
}
```

---

## 六、ISR（增量静态再生）

```tsx
// app/blog/[slug]/page.tsx
// 在构建时生成静态页面，之后按需重新生成

export const revalidate = 3600; // 页面每小时重新生成一次

export async function generateStaticParams() {
  // 构建时生成前100篇文章的静态页面
  const posts = await db.post.findMany({ take: 100, select: { slug: true } });
  return posts.map((post) => ({ slug: post.slug }));
}

// dynamicParams 默认为 true
// 未预生成的页面会在首次访问时动态生成并缓存
export default async function BlogPost({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await db.post.findUnique({ where: { slug } });

  if (!post) notFound();

  return (
    <article>
      <h1>{post.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: post.htmlContent }} />
    </article>
  );
}
```

---

## 七、中间件

### 7.1 认证中间件

```tsx
// middleware.ts（项目根目录）
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// 需要认证的路由
const protectedRoutes = ['/dashboard', '/settings', '/profile'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 检查认证 token
  const token = request.cookies.get('auth-token')?.value;

  // 保护路由：未登录重定向到登录页
  if (protectedRoutes.some((route) => pathname.startsWith(route))) {
    if (!token) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('callbackUrl', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // 已登录用户访问登录页，重定向到仪表盘
  if (pathname === '/login' && token) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  // 匹配所有路由，排除静态资源和 API
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
```

### 7.2 国际化中间件

```tsx
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { match } from '@formatjs/intl-localematcher';
import Negotiator from 'negotiator';

const locales = ['zh-CN', 'en', 'ja'];
const defaultLocale = 'zh-CN';

function getLocale(request: NextRequest): string {
  const headers = { 'accept-language': request.headers.get('accept-language') ?? '' };
  const languages = new Negotiator({ headers }).languages();
  return match(languages, locales, defaultLocale);
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 检查路径是否已包含 locale 前缀
  const hasLocale = locales.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  );

  if (hasLocale) return NextResponse.next();

  // 自动检测语言并重定向
  const locale = getLocale(request);
  return NextResponse.redirect(new URL(`/${locale}${pathname}`, request.url));
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
```

### 7.3 请求头 / 重定向

```tsx
// middleware.ts — 添加自定义请求头
export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // 安全头
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');

  // 传递请求信息给 Server Components
  response.headers.set('x-pathname', request.nextUrl.pathname);
  response.headers.set('x-search-params', request.nextUrl.search);

  return response;
}
```
