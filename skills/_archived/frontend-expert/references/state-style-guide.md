# 状态管理 + 样式方案指南

> 涵盖 Zustand、TanStack Query、状态管理选型、Tailwind CSS 4、CSS Variables 主题系统和响应式设计。

---

## 一、Zustand 模式

### 1.1 基础 Store 设计

```tsx
// stores/authStore.ts
import { create } from 'zustand';

interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

interface AuthActions {
  login: (user: User, token: string) => void;
  logout: () => void;
  updateProfile: (data: Partial<User>) => void;
}

// 状态与操作分离，类型清晰
export const useAuthStore = create<AuthState & AuthActions>((set) => ({
  // 状态
  user: null,
  token: null,
  isAuthenticated: false,

  // 操作
  login: (user, token) =>
    set({ user, token, isAuthenticated: true }),

  logout: () =>
    set({ user: null, token: null, isAuthenticated: false }),

  updateProfile: (data) =>
    set((state) => ({
      user: state.user ? { ...state.user, ...data } : null,
    })),
}));

// 选择器：按需订阅，避免不必要的重渲染
export const useUser = () => useAuthStore((s) => s.user);
export const useIsAuth = () => useAuthStore((s) => s.isAuthenticated);
```

### 1.2 Slice 模式（大型 Store 拆分）

```tsx
// stores/slices/cartSlice.ts
import type { StateCreator } from 'zustand';

export interface CartSlice {
  items: CartItem[];
  addItem: (product: Product, quantity: number) => void;
  removeItem: (productId: string) => void;
  clearCart: () => void;
  totalPrice: () => number;
}

export const createCartSlice: StateCreator<CartSlice> = (set, get) => ({
  items: [],

  addItem: (product, quantity) =>
    set((state) => {
      const existing = state.items.find((i) => i.productId === product.id);
      if (existing) {
        return {
          items: state.items.map((i) =>
            i.productId === product.id
              ? { ...i, quantity: i.quantity + quantity }
              : i
          ),
        };
      }
      return {
        items: [...state.items, { productId: product.id, product, quantity }],
      };
    }),

  removeItem: (productId) =>
    set((state) => ({
      items: state.items.filter((i) => i.productId !== productId),
    })),

  clearCart: () => set({ items: [] }),

  totalPrice: () =>
    get().items.reduce((sum, i) => sum + i.product.price * i.quantity, 0),
});

// stores/index.ts — 合并 Slices
import { create } from 'zustand';
import { createCartSlice, type CartSlice } from './slices/cartSlice';
import { createUISlice, type UISlice } from './slices/uiSlice';

type StoreState = CartSlice & UISlice;

export const useStore = create<StoreState>()((...args) => ({
  ...createCartSlice(...args),
  ...createUISlice(...args),
}));
```

### 1.3 Persist Middleware（持久化）

```tsx
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'system',
      language: 'zh-CN',
      sidebarCollapsed: false,

      setTheme: (theme) => set({ theme }),
      setLanguage: (lang) => set({ language: lang }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: 'app-settings', // localStorage key
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // 只持久化需要的字段
        theme: state.theme,
        language: state.language,
      }),
    }
  )
);
```

### 1.4 Devtools Middleware

```tsx
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export const useCountStore = create<CountState>()(
  devtools(
    (set) => ({
      count: 0,
      increment: () => set((s) => ({ count: s.count + 1 }), false, 'increment'),
      decrement: () => set((s) => ({ count: s.count - 1 }), false, 'decrement'),
    }),
    { name: 'CountStore' } // Redux DevTools 中显示的名称
  )
);
```

---

## 二、TanStack Query

### 2.1 QueryKey 设计

```tsx
// lib/queryKeys.ts — 统一管理查询键
export const queryKeys = {
  // 用户相关
  users: {
    all: ['users'] as const,
    lists: () => [...queryKeys.users.all, 'list'] as const,
    list: (filters: UserFilters) => [...queryKeys.users.lists(), filters] as const,
    details: () => [...queryKeys.users.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.users.details(), id] as const,
  },
  // 文章相关
  posts: {
    all: ['posts'] as const,
    list: (params: PostListParams) => [...queryKeys.posts.all, 'list', params] as const,
    detail: (id: string) => [...queryKeys.posts.all, 'detail', id] as const,
  },
};
```

### 2.2 缓存策略与数据获取

```tsx
// hooks/useUsers.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';

// 查询 Hook
export function useUsers(filters: UserFilters) {
  return useQuery({
    queryKey: queryKeys.users.list(filters),
    queryFn: () => userService.getList(filters),
    staleTime: 5 * 60 * 1000,      // 5分钟内数据视为新鲜
    gcTime: 30 * 60 * 1000,         // 30分钟后垃圾回收（原 cacheTime）
    placeholderData: keepPreviousData, // 切换页码时保留旧数据
  });
}

// 用户详情
export function useUser(id: string) {
  return useQuery({
    queryKey: queryKeys.users.detail(id),
    queryFn: () => userService.getById(id),
    enabled: !!id, // id 不存在时不发请求
  });
}
```

### 2.3 Optimistic Updates（乐观更新）

```tsx
export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateUserData) => userService.update(data),

    // 乐观更新：先更新 UI，再等服务端确认
    onMutate: async (newData) => {
      // 取消正在进行的查询，避免覆盖乐观更新
      await queryClient.cancelQueries({
        queryKey: queryKeys.users.detail(newData.id),
      });

      // 保存之前的数据用于回滚
      const previousUser = queryClient.getQueryData(
        queryKeys.users.detail(newData.id)
      );

      // 乐观更新缓存
      queryClient.setQueryData(
        queryKeys.users.detail(newData.id),
        (old: User) => ({ ...old, ...newData })
      );

      return { previousUser };
    },

    // 出错时回滚
    onError: (_err, newData, context) => {
      if (context?.previousUser) {
        queryClient.setQueryData(
          queryKeys.users.detail(newData.id),
          context.previousUser
        );
      }
    },

    // 无论成功失败，都重新获取最新数据
    onSettled: (_data, _err, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.users.detail(variables.id),
      });
    },
  });
}
```

### 2.4 Infinite Queries（无限滚动）

```tsx
export function useInfinitePosts() {
  return useInfiniteQuery({
    queryKey: queryKeys.posts.all,
    queryFn: ({ pageParam }) =>
      postService.getList({ cursor: pageParam, limit: 20 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
}

// 组件中使用
function PostFeed() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfinitePosts();

  // 所有页面的文章合并为一个列表
  const allPosts = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div>
      {allPosts.map((post) => (
        <PostCard key={post.id} post={post} />
      ))}
      {hasNextPage && (
        <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
          {isFetchingNextPage ? '加载中...' : '加载更多'}
        </button>
      )}
    </div>
  );
}
```

---

## 三、状态管理选型

```
┌─────────────────────────────────────────────────────────────────┐
│  状态类型          │  推荐方案            │  典型场景            │
├────────────────────┼──────────────────────┼──────────────────────┤
│  服务端状态        │  TanStack Query      │  API 数据、分页、缓存 │
│  客户端全局状态    │  Zustand             │  用户认证、UI设置     │
│  组件局部状态      │  useState/useReducer │  表单、开关、临时状态  │
│  跨组件共享        │  Context             │  主题、语言（低频更新）│
│  URL 状态          │  nuqs / searchParams │  筛选、排序、分页     │
│  表单状态          │  React Hook Form     │  复杂表单、多步骤表单  │
└─────────────────────────────────────────────────────────────────┘
```

**选型原则**：
- 服务端数据 **一律**用 TanStack Query，不要手动 `useEffect` + `useState` 管理
- 全局 UI 状态（主题、侧边栏展开、通知等）用 Zustand
- 筛选条件、分页参数放 URL，保证可分享、可后退
- Context 仅用于低频更新的全局数据（主题、i18n），避免高频更新导致整棵树重渲染

---

## 四、Tailwind CSS 4

### 4.1 新特性

Tailwind CSS 4 使用 CSS-first 配置方式，不再需要 `tailwind.config.js`：

```css
/* app/globals.css */
@import 'tailwindcss';

/* 自定义主题 — 直接用 CSS 语法 */
@theme {
  --color-brand-50: #eff6ff;
  --color-brand-500: #3b82f6;
  --color-brand-900: #1e3a5f;

  --font-display: 'Inter', sans-serif;
  --breakpoint-3xl: 1920px;
}
```

### 4.2 CSS Variables 实现多主题系统

```css
/* styles/themes.css */
@import 'tailwindcss';

/* 默认亮色主题 */
:root {
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f9fafb;
  --color-text-primary: #111827;
  --color-text-secondary: #6b7280;
  --color-border: #e5e7eb;
  --color-accent: #3b82f6;
  --color-accent-hover: #2563eb;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.07);
  --radius-default: 0.5rem;
}

/* 暗色主题 */
[data-theme='dark'] {
  --color-bg-primary: #0f172a;
  --color-bg-secondary: #1e293b;
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-border: #334155;
  --color-accent: #60a5fa;
  --color-accent-hover: #93bbfc;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
}

/* 粉色主题 */
[data-theme='pink'] {
  --color-accent: #ec4899;
  --color-accent-hover: #db2777;
}

/* 绿色主题 */
[data-theme='green'] {
  --color-accent: #22c55e;
  --color-accent-hover: #16a34a;
}
```

### 4.3 主题切换组件

```tsx
'use client';

import { useSettingsStore } from '@/stores/settingsStore';

const themes = [
  { value: 'light', label: '亮色' },
  { value: 'dark', label: '暗色' },
  { value: 'pink', label: '粉色' },
  { value: 'green', label: '绿色' },
] as const;

export function ThemeSwitcher() {
  const { theme, setTheme } = useSettingsStore();

  const handleChange = (newTheme: string) => {
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  return (
    <div className="flex gap-2">
      {themes.map((t) => (
        <button
          key={t.value}
          onClick={() => handleChange(t.value)}
          className={`rounded-lg px-3 py-1.5 text-sm transition-colors
            ${theme === t.value
              ? 'bg-[var(--color-accent)] text-white'
              : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]'
            }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
```

### 4.4 在 Tailwind 中使用 CSS Variables

```tsx
// 使用 arbitrary values 引用 CSS 变量
function Card({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="
        rounded-[var(--radius-default)]
        bg-[var(--color-bg-primary)]
        text-[var(--color-text-primary)]
        border border-[var(--color-border)]
        shadow-[var(--shadow-md)]
        p-6
      "
    >
      {children}
    </div>
  );
}
```

---

## 五、响应式设计模式

### 5.1 Container Queries

Container queries 让组件根据**容器宽度**（而非视口宽度）自适应布局：

```tsx
// 父容器标记为 container
function Sidebar() {
  return (
    <aside className="@container">
      <UserCard />
    </aside>
  );
}

// 子组件根据容器宽度响应
function UserCard() {
  return (
    <div className="flex flex-col @md:flex-row @lg:gap-4 items-center gap-2">
      <Avatar className="size-10 @md:size-16" />
      <div>
        <h3 className="text-sm @md:text-base font-medium">用户名</h3>
        <p className="hidden @md:block text-xs text-gray-500">用户简介</p>
      </div>
    </div>
  );
}
```

### 5.2 clamp() 实现流体排版

```css
/* 字体大小在 16px ~ 24px 之间流畅缩放 */
.fluid-title {
  font-size: clamp(1rem, 0.5rem + 2vw, 1.5rem);
}

/* 间距也可以流体化 */
.fluid-section {
  padding: clamp(1rem, 3vw, 3rem);
  gap: clamp(0.5rem, 1.5vw, 1.5rem);
}
```

```tsx
// 在 Tailwind 中使用 clamp
function HeroSection() {
  return (
    <section className="px-[clamp(1rem,5vw,4rem)] py-[clamp(2rem,8vw,6rem)]">
      <h1 className="text-[clamp(1.5rem,4vw,3.5rem)] font-bold leading-tight">
        欢迎使用我们的平台
      </h1>
      <p className="mt-[clamp(0.5rem,1.5vw,1.5rem)] text-[clamp(0.875rem,1.5vw,1.25rem)]">
        描述文字
      </p>
    </section>
  );
}
```

### 5.3 移动优先响应式设计

```tsx
// Tailwind 默认就是移动优先：无前缀 = 移动端，sm/md/lg = 向上覆盖
function ProductGrid() {
  return (
    <div
      className="
        grid
        grid-cols-1          /* 移动端：单列 */
        sm:grid-cols-2       /* >=640px：两列 */
        md:grid-cols-3       /* >=768px：三列 */
        lg:grid-cols-4       /* >=1024px：四列 */
        gap-4
        sm:gap-6
      "
    >
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  );
}

// 响应式导航：移动端汉堡菜单 → 桌面端水平导航
function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="relative">
      {/* 移动端：汉堡按钮 */}
      <button
        className="md:hidden p-2"
        onClick={() => setIsOpen(!isOpen)}
      >
        <MenuIcon />
      </button>

      {/* 导航链接：移动端垂直展开，桌面端水平排列 */}
      <ul
        className={`
          ${isOpen ? 'flex' : 'hidden'}
          flex-col absolute top-full left-0 w-full bg-white shadow-lg
          md:static md:flex md:flex-row md:shadow-none md:w-auto
          gap-1 md:gap-6
        `}
      >
        <li><a href="/" className="block px-4 py-2">首页</a></li>
        <li><a href="/products" className="block px-4 py-2">产品</a></li>
        <li><a href="/about" className="block px-4 py-2">关于</a></li>
      </ul>
    </nav>
  );
}
```

### 5.4 常用响应式断点参考

```
┌─────────────┬──────────┬─────────────────┐
│  断点        │  宽度    │  设备类型        │
├─────────────┼──────────┼─────────────────┤
│  (默认)      │  0px+    │  手机竖屏        │
│  sm          │  640px+  │  手机横屏        │
│  md          │  768px+  │  平板竖屏        │
│  lg          │  1024px+ │  平板横屏/小笔记本 │
│  xl          │  1280px+ │  桌面显示器      │
│  2xl         │  1536px+ │  大屏显示器      │
└─────────────┴──────────┴─────────────────┘
```
