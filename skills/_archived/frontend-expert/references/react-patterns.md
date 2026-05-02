# React 19 模式与最佳实践

> 本文档涵盖 React 19 核心新特性、常用 Hooks 模式、错误边界、并发特性、性能优化及组件设计模式。

---

## 一、React 19 新特性

### 1.1 Server Components

Server Components 在服务端运行，不会打包到客户端 bundle 中，可以直接访问数据库、文件系统等后端资源。

```tsx
// app/products/page.tsx — Server Component（默认）
// 无需 "use client"，直接在服务端执行
import { db } from '@/lib/db';

export default async function ProductsPage() {
  // 直接查询数据库，零客户端 JS
  const products = await db.product.findMany({
    orderBy: { createdAt: 'desc' },
    take: 20,
  });

  return (
    <main>
      <h1>产品列表</h1>
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </main>
  );
}
```

**核心规则**：
- Server Components **不能**使用 `useState`、`useEffect` 等客户端 Hook
- Server Components **不能**添加事件处理器（onClick 等）
- 需要交互的部分抽取为 `"use client"` 组件
- Server Components 可以 `import` Client Components，反之不行

### 1.2 Actions（表单操作）

Actions 简化了表单提交和数据变更的处理流程，替代传统的 `onSubmit` + `fetch` 模式。

```tsx
// actions/user.ts
'use server';

import { z } from 'zod';
import { revalidatePath } from 'next/cache';

const CreateUserSchema = z.object({
  name: z.string().min(2, '姓名至少2个字符'),
  email: z.string().email('邮箱格式不正确'),
});

export async function createUser(prevState: any, formData: FormData) {
  const result = CreateUserSchema.safeParse({
    name: formData.get('name'),
    email: formData.get('email'),
  });

  if (!result.success) {
    return { errors: result.error.flatten().fieldErrors };
  }

  await db.user.create({ data: result.data });
  revalidatePath('/users');
  return { success: true };
}
```

```tsx
// components/CreateUserForm.tsx
'use client';

import { useActionState } from 'react';
import { createUser } from '@/actions/user';

export function CreateUserForm() {
  const [state, formAction, isPending] = useActionState(createUser, {});

  return (
    <form action={formAction}>
      <input name="name" placeholder="姓名" />
      {state.errors?.name && <p className="text-red-500">{state.errors.name}</p>}

      <input name="email" type="email" placeholder="邮箱" />
      {state.errors?.email && <p className="text-red-500">{state.errors.email}</p>}

      <button type="submit" disabled={isPending}>
        {isPending ? '提交中...' : '创建用户'}
      </button>
    </form>
  );
}
```

### 1.3 use() Hook

`use()` 可以在组件内读取 Promise 或 Context，配合 Suspense 实现优雅的异步数据读取。

```tsx
import { use, Suspense } from 'react';

// 创建数据 Promise
function fetchUser(id: string): Promise<User> {
  return fetch(`/api/users/${id}`).then((r) => r.json());
}

function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  // use() 在渲染期间读取 Promise，配合 Suspense 自动处理加载态
  const user = use(userPromise);

  return (
    <div>
      <h2>{user.name}</h2>
      <p>{user.email}</p>
    </div>
  );
}

// 父组件
export default function UserPage({ params }: { params: { id: string } }) {
  const userPromise = fetchUser(params.id);

  return (
    <Suspense fallback={<UserSkeleton />}>
      <UserProfile userPromise={userPromise} />
    </Suspense>
  );
}
```

### 1.4 React Compiler（实验性）

React Compiler 自动完成 memoization，无需手动使用 `useMemo`、`useCallback`、`React.memo`。

```tsx
// 开启 React Compiler 后，以下代码自动优化，无需手动 memo
function TodoList({ todos, filter }: TodoListProps) {
  // Compiler 自动识别：filteredTodos 仅在 todos 或 filter 变化时重新计算
  const filteredTodos = todos.filter((t) => {
    if (filter === 'active') return !t.completed;
    if (filter === 'completed') return t.completed;
    return true;
  });

  // Compiler 自动识别：handleToggle 不需要每次渲染都重新创建
  const handleToggle = (id: string) => {
    toggleTodo(id);
  };

  return filteredTodos.map((todo) => (
    <TodoItem key={todo.id} todo={todo} onToggle={handleToggle} />
  ));
}
```

---

## 二、常用 Hooks 模式

### 2.1 useCallback / useMemo 最佳实践

```tsx
// 在未使用 React Compiler 的项目中，仍需手动优化

// useCallback：稳定回调引用，避免子组件不必要的重渲染
function SearchPage() {
  const [query, setQuery] = useState('');

  // 仅在 query 变化时更新搜索函数
  const handleSearch = useCallback(
    debounce((value: string) => {
      fetchResults(value);
    }, 300),
    [] // debounce 函数内部管理 value，依赖为空
  );

  return <SearchInput onSearch={handleSearch} />;
}

// useMemo：缓存计算结果
function DataTable({ data, sortKey, sortOrder }: DataTableProps) {
  const sortedData = useMemo(() => {
    return [...data].sort((a, b) => {
      const result = a[sortKey] > b[sortKey] ? 1 : -1;
      return sortOrder === 'asc' ? result : -result;
    });
  }, [data, sortKey, sortOrder]);

  return <Table data={sortedData} />;
}
```

### 2.2 自定义 Hooks 设计模式

```tsx
// hooks/useLocalStorage.ts — 持久化状态
function useLocalStorage<T>(key: string, initialValue: T) {
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const item = window.localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = useCallback(
    (value: T | ((val: T) => T)) => {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    },
    [key, storedValue]
  );

  return [storedValue, setValue] as const;
}

// hooks/useDebounce.ts — 防抖值
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

// hooks/useMediaQuery.ts — 响应式断点检测
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, [query]);

  return matches;
}
```

---

## 三、错误边界 (Error Boundaries)

### 3.1 实现模式

```tsx
// components/ErrorBoundary.tsx
'use client';

import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // 上报错误到监控服务
    this.props.onError?.(error, errorInfo);
    console.error('ErrorBoundary 捕获错误:', error, errorInfo);
  }

  // 恢复策略：提供重置方法
  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="p-6 text-center">
          <h2 className="text-lg font-bold text-red-600">出错了</h2>
          <p className="mt-2 text-gray-600">{this.state.error?.message}</p>
          <button
            onClick={this.handleReset}
            className="mt-4 rounded bg-blue-500 px-4 py-2 text-white"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

### 3.2 Next.js error.tsx 约定

```tsx
// app/dashboard/error.tsx — Next.js 内置错误边界
'use client';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <h2>仪表盘加载失败</h2>
      <p className="text-gray-500">{error.message}</p>
      <button onClick={reset} className="mt-4 btn-primary">
        重试
      </button>
    </div>
  );
}
```

---

## 四、并发特性

### 4.1 Suspense + 流式渲染

```tsx
import { Suspense } from 'react';

// 并行加载多个数据区域，各自独立展示
export default function DashboardPage() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <Suspense fallback={<CardSkeleton />}>
        <RevenueChart />
      </Suspense>
      <Suspense fallback={<CardSkeleton />}>
        <LatestOrders />
      </Suspense>
      <Suspense fallback={<CardSkeleton />}>
        <TopProducts />
      </Suspense>
    </div>
  );
}
```

### 4.2 startTransition + useTransition

```tsx
'use client';

import { useTransition } from 'react';

function TabContainer() {
  const [tab, setTab] = useState('home');
  const [isPending, startTransition] = useTransition();

  function handleTabChange(nextTab: string) {
    // 标记为低优先级更新，不阻塞用户输入
    startTransition(() => {
      setTab(nextTab);
    });
  }

  return (
    <div>
      <TabBar activeTab={tab} onChange={handleTabChange} />
      <div className={isPending ? 'opacity-50' : ''}>
        {tab === 'home' && <Home />}
        {tab === 'posts' && <Posts />}
        {tab === 'settings' && <Settings />}
      </div>
    </div>
  );
}
```

### 4.3 useDeferredValue

```tsx
'use client';

import { useDeferredValue, useMemo } from 'react';

function SearchResults({ query }: { query: string }) {
  // 延迟更新搜索结果，保证输入框流畅响应
  const deferredQuery = useDeferredValue(query);
  const isStale = query !== deferredQuery;

  const results = useMemo(() => filterItems(deferredQuery), [deferredQuery]);

  return (
    <div className={isStale ? 'opacity-60' : ''}>
      {results.map((item) => (
        <ResultItem key={item.id} item={item} />
      ))}
    </div>
  );
}
```

---

## 五、性能优化模式

### 5.1 React.memo — 跳过不必要的重渲染

```tsx
// 仅在 props 实际变化时重渲染（浅比较）
const ExpensiveList = React.memo(function ExpensiveList({
  items,
  onSelect,
}: {
  items: Item[];
  onSelect: (id: string) => void;
}) {
  return items.map((item) => (
    <ListItem key={item.id} item={item} onSelect={onSelect} />
  ));
});
```

### 5.2 React.lazy + Suspense — 代码分割

```tsx
import { lazy, Suspense } from 'react';

// 按需加载重量级组件
const HeavyChart = lazy(() => import('@/components/HeavyChart'));
const MarkdownEditor = lazy(() => import('@/components/MarkdownEditor'));

function Dashboard() {
  return (
    <div>
      <Suspense fallback={<ChartSkeleton />}>
        <HeavyChart data={chartData} />
      </Suspense>
      <Suspense fallback={<EditorSkeleton />}>
        <MarkdownEditor />
      </Suspense>
    </div>
  );
}
```

### 5.3 虚拟列表 — 大数据渲染

```tsx
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualList({ items }: { items: Item[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50, // 每行预估高度
  });

  return (
    <div ref={parentRef} className="h-[400px] overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.key}
            style={{
              position: 'absolute',
              top: 0,
              transform: `translateY(${virtualRow.start}px)`,
              height: `${virtualRow.size}px`,
            }}
          >
            {items[virtualRow.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 六、组件设计模式

### 6.1 Compound Components（复合组件）

```tsx
// 通过 Context 共享状态，允许灵活组合子组件
interface TabsContextValue {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function Tabs({ defaultTab, children }: { defaultTab: string; children: ReactNode }) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div>{children}</div>
    </TabsContext.Provider>
  );
}

function TabList({ children }: { children: ReactNode }) {
  return <div className="flex border-b">{children}</div>;
}

function Tab({ value, children }: { value: string; children: ReactNode }) {
  const ctx = use(TabsContext)!;
  return (
    <button
      className={ctx.activeTab === value ? 'border-b-2 border-blue-500' : ''}
      onClick={() => ctx.setActiveTab(value)}
    >
      {children}
    </button>
  );
}

function TabPanel({ value, children }: { value: string; children: ReactNode }) {
  const ctx = use(TabsContext)!;
  return ctx.activeTab === value ? <div>{children}</div> : null;
}

// 使用方式 — 灵活组合
<Tabs defaultTab="profile">
  <TabList>
    <Tab value="profile">个人资料</Tab>
    <Tab value="settings">设置</Tab>
  </TabList>
  <TabPanel value="profile"><ProfileForm /></TabPanel>
  <TabPanel value="settings"><SettingsForm /></TabPanel>
</Tabs>
```

### 6.2 Render Props 的现代替代 — Headless Hooks

```tsx
// 将组件逻辑抽取为 Hook，由调用方控制 UI
function useDropdown<T>(items: T[]) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const toggle = () => setIsOpen(!isOpen);
  const select = (index: number) => {
    setSelectedIndex(index);
    setIsOpen(false);
  };

  return {
    isOpen,
    selectedItem: items[selectedIndex] ?? null,
    toggle,
    select,
    items,
  };
}

// 使用时完全控制 UI
function MyDropdown() {
  const dropdown = useDropdown(['选项A', '选项B', '选项C']);

  return (
    <div>
      <button onClick={dropdown.toggle}>
        {dropdown.selectedItem ?? '请选择'}
      </button>
      {dropdown.isOpen && (
        <ul>
          {dropdown.items.map((item, i) => (
            <li key={i} onClick={() => dropdown.select(i)}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

### 6.3 受控与非受控模式的统一

```tsx
// 同时支持受控和非受控用法
interface InputProps {
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
}

function useControllableState<T>({
  value: controlledValue,
  defaultValue,
  onChange,
}: {
  value?: T;
  defaultValue: T;
  onChange?: (value: T) => void;
}) {
  const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
  const isControlled = controlledValue !== undefined;
  const currentValue = isControlled ? controlledValue : uncontrolledValue;

  const setValue = useCallback(
    (next: T) => {
      if (!isControlled) setUncontrolledValue(next);
      onChange?.(next);
    },
    [isControlled, onChange]
  );

  return [currentValue, setValue] as const;
}
```
