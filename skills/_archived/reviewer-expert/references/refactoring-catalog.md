# 重构模式目录 (Refactoring Catalog)

> 常见重构模式的说明、适用场景与 before/after TypeScript 代码示例。

---

## Extract 模式（提取）

### Extract Function — 长函数拆分

**适用场景**：函数超过 30 行，包含多个逻辑段落。

```typescript
// ❌ Before: 验证 + 计算 + 支付全在一个函数
async function processOrder(order: Order) {
  if (!order.items.length) throw new Error('空订单');
  if (order.items.some(i => i.quantity <= 0)) throw new Error('数量无效');
  let total = order.items.reduce((s, i) => s + i.unitPrice * i.quantity, 0);
  total += total * 0.13;
  const payment = await paymentService.create({ orderId: order.id, amount: total });
  return { order, payment, total };
}

// ✅ After: 拆分为独立函数
function validateOrder(order: Order): void { /* 验证逻辑 */ }
function calculateTotal(items: OrderItem[]): number { /* 计算逻辑 */ }
async function processOrder(order: Order) {
  validateOrder(order);
  const total = calculateTotal(order.items);
  const payment = await paymentService.create({ orderId: order.id, amount: total });
  return { order, payment, total };
}
```

### Extract Component — React 大组件拆分

**适用场景**：组件 JSX 超过 150 行，包含多个独立 UI 区块。拆分为 `OrderFilterForm`、`OrderTable`、`Pagination` 等子组件，父组件仅负责组合与状态传递。

```typescript
// ✅ After: 父组件只做组合
function OrderPage() {
  const [filter, setFilter] = useState('');
  const { data: orders, total } = useOrders(filter);
  return (
    <div>
      <OrderFilterForm value={filter} onChange={setFilter} />
      <OrderTable orders={orders} onSelect={handleSelect} />
      <Pagination total={total} page={page} onPageChange={setPage} />
    </div>
  );
}
```

### Extract Hook — 自定义 Hook 提取

**适用场景**：多个组件共享相同的状态逻辑或副作用。

```typescript
// ✅ 通用异步数据 Hook（替代组件中重复的 data/loading/error + useEffect）
function useAsync<T>(asyncFn: (signal: AbortSignal) => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: Error | null }>(
    { data: null, loading: true, error: null }
  );
  useEffect(() => {
    const ctrl = new AbortController();
    asyncFn(ctrl.signal)
      .then(data => setState({ data, loading: false, error: null }))
      .catch(error => { if (!ctrl.signal.aborted) setState({ data: null, loading: false, error }); });
    return () => ctrl.abort();
  }, deps);
  return state;
}
```

### Extract Service — API 调用逻辑抽取

**适用场景**：API 调用散布在组件中，缺少统一管理。

```typescript
// ✅ Service 层统一封装（替代组件中分散的 fetch 调用）
class OrderService {
  create(data: CreateOrderDTO): Promise<Order> { return apiClient.post('/orders', data); }
  getById(id: string): Promise<Order> { return apiClient.get(`/orders/${id}`); }
  list(params: OrderQuery): Promise<PaginatedResult<Order>> {
    return apiClient.get('/orders', { params });
  }
}
export const orderService = new OrderService();
```

---

## Replace 模式（替换）

### Replace Conditional with Polymorphism — switch 转策略模式

**适用场景**：多处 switch/if-else 判断同一变量，分支可能增长。

```typescript
// ❌ Before: switch 散布在多个函数中
function calculateShipping(method: string, weight: number): number {
  switch (method) {
    case 'standard': return weight * 5;
    case 'express':  return weight * 10 + 15;
    case 'overnight': return weight * 20 + 30;
  }
}

// ✅ After: 策略模式，新增方式只需加一行
interface ShippingStrategy { cost(weight: number): number; days: number; }
const strategies: Record<string, ShippingStrategy> = {
  standard:  { cost: (w) => w * 5,       days: 7 },
  express:   { cost: (w) => w * 10 + 15, days: 3 },
  overnight: { cost: (w) => w * 20 + 30, days: 1 },
};
```

### Replace Temp with Query — 临时变量转计算属性

**适用场景**：临时变量缓存表达式结果，该表达式可封装为方法。

```typescript
// ❌ Before: 临时变量堆积
const basePrice = items.reduce((s, i) => s + i.price * i.qty, 0);
const discount = basePrice > 1000 ? 0.1 : 0;
const total = basePrice * (1 - discount) * 1.13;

// ✅ After: 计算属性类，逻辑可复用
class OrderCalculator {
  constructor(private items: OrderItem[]) {}
  get basePrice() { return this.items.reduce((s, i) => s + i.price * i.qty, 0); }
  get discountRate() { return this.basePrice > 1000 ? 0.1 : 0; }
  get total() { return this.basePrice * (1 - this.discountRate) * 1.13; }
}
```

### Replace Nested Conditionals with Guard Clauses — 卫语句简化

**适用场景**：多层嵌套 if-else 导致代码右漂（4 层 if 嵌套 → 卫语句提前返回）。

```typescript
// ✅ After: 卫语句提前返回，主逻辑清晰（替代 4 层嵌套 if-else）
function processPayment(order: Order | null, user: User) {
  if (!order) return { success: false, reason: '订单不存在' };
  if (order.status !== 'pending') return { success: false, reason: '状态不允许' };
  if (!user.isActive) return { success: false, reason: '用户已停用' };
  if (user.balance < order.total) return { success: false, reason: '余额不足' };
  return { success: true };
}
```

---

## Introduce 模式（引入）

### Introduce Parameter Object — 多参数转配置对象

**适用场景**：函数参数超过 3-4 个。

```typescript
// ❌ Before: 8 个参数
function searchProducts(keyword: string, category: string, minPrice: number,
  maxPrice: number, sortBy: string, sortOrder: 'asc'|'desc', page: number, size: number) {}

// ✅ After: 配置对象
interface SearchParams {
  keyword: string;
  category?: string;
  priceRange?: { min: number; max: number };
  sort?: { field: string; order: 'asc' | 'desc' };
  pagination?: { page: number; size: number };
}
function searchProducts(params: SearchParams) { /* ... */ }
```

### Introduce Null Object — null 检查转空对象模式

**适用场景**：多处 `if (x != null)` 检查同一对象。

```typescript
// ❌ Before: 多处 null 检查
const name = user ? user.name : '游客';
const avatar = user ? user.avatarUrl : '/default.png';

// ✅ After: 预定义空对象
const GUEST: User = { id: '', name: '游客', avatarUrl: '/default.png', role: 'guest', permissions: [] };
function ensureUser(user: User | null): User { return user ?? GUEST; }
```

### Introduce Facade — 复杂接口转门面简化

**适用场景**：调用方需协调多个服务才能完成一个操作。将 inventory/order/payment/notification 多服务协调封装为 `CheckoutFacade.placeOrder()`，内部处理库存校验、支付扣款、补偿回滚和异步通知。

---

## 重构安全准则

1. **测试覆盖前置**：重构前确保目标代码有测试覆盖，没有则先补测试
2. **小步提交**：每次重构一个明确步骤，独立 commit，方便回滚
3. **单一职责每次**：一次只做一种重构操作，不混合多种手法
4. **重构与功能不混合**：重构 commit 与功能 commit 分离

### 重构信号速查表

| 信号 | 说明 | 对应模式 |
|------|------|----------|
| 函数超过 30 行 | 职责过多 | Extract Function |
| 组件超过 150 行 JSX | UI 逻辑混杂 | Extract Component |
| 相同逻辑出现 3+ 次 | 违反 DRY | Extract Function / Hook |
| switch/if-else 超过 5 分支 | 需要策略模式 | Replace Conditional |
| 函数参数超过 4 个 | 接口复杂 | Introduce Parameter Object |
| 嵌套超过 3 层 | 难以理解 | Guard Clauses |
| 多处 null 检查同一对象 | 空值逻辑散布 | Introduce Null Object |
| 调用方需协调 3+ 服务 | 耦合过高 | Introduce Facade |
