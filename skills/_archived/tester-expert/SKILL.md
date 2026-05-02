---
name: tester-expert
description: >
  测试专家。当用户需要编写单元测试、集成测试、E2E 端到端测试、TDD 测试驱动开发、
  Jest/Vitest/Playwright/Cypress/pytest 测试框架、Mock/Stub、测试覆盖率，
  或说 "写测试"、"测试用例" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, mcp__playwright, mcp__chrome-devtools, mcp__selenium
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [debugger-expert, zero-defect-guardian]
---

# 测试专家 (Tester Expert)

> **Output Style**: 本技能使用内联输出规范

资深测试工程师，精通各种测试策略、测试框架和 TDD 开发方法。

## 触发关键词

- **core tier**: `单元测试`, `集成测试`, `E2E测试`, `端到端测试`, `写测试`, `测试用例`, `unit test`, `integration test`, `write tests`, `test case`, `test coverage`, `testing`
- **strong tier**: `Jest`, `Vitest`, `Playwright`, `Cypress`, `pytest`, `TDD`, `BDD`, `测试覆盖率`, `test suite`, `test runner`, `component test`, `snapshot test`, `regression test`
- **extended tier**: `测试驱动`, `Mock`, `Stub`, `覆盖率`, `代码覆盖`, `测试方案`, `testing library`, `test driven`, `assertion`
- **排除场景**: `A/B测试`（数据实验）→ 路由至 data-analyst-expert；`pandas` 相关测试 → 路由至 data-analyst-expert

## 测试金字塔

```
        /\
       /  \
      / E2E \        少量：关键用户流程
     /______\
    /        \
   /Integration\    中量：API和服务交互
  /______________\
 /                \
/   Unit Tests     \   大量：函数和模块
/____________________\
```

## 单元测试

### Jest / Vitest
```typescript
// user.service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UserService } from './user.service';

describe('UserService', () => {
  let userService: UserService;
  let mockUserRepository: any;

  beforeEach(() => {
    mockUserRepository = {
      findById: vi.fn(),
      save: vi.fn(),
    };
    userService = new UserService(mockUserRepository);
  });

  describe('getUserById', () => {
    it('should return user when found', async () => {
      const mockUser = { id: '1', name: 'John' };
      mockUserRepository.findById.mockResolvedValue(mockUser);

      const result = await userService.getUserById('1');

      expect(result).toEqual(mockUser);
      expect(mockUserRepository.findById).toHaveBeenCalledWith('1');
    });

    it('should return null when user not found', async () => {
      mockUserRepository.findById.mockResolvedValue(null);

      const result = await userService.getUserById('999');

      expect(result).toBeNull();
    });

    it('should throw error on database failure', async () => {
      mockUserRepository.findById.mockRejectedValue(new Error('DB Error'));

      await expect(userService.getUserById('1')).rejects.toThrow('DB Error');
    });
  });
});
```

### React 组件测试
```typescript
// Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    
    fireEvent.click(screen.getByRole('button'));
    
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('shows loading spinner when loading', () => {
    render(<Button loading>Submit</Button>);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByText('Submit')).not.toBeInTheDocument();
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

## 集成测试

```typescript
// api.integration.test.ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import request from 'supertest';
import { app } from '../app';
import { db } from '../db';

describe('User API', () => {
  beforeAll(async () => {
    await db.migrate.latest();
    await db.seed.run();
  });

  afterAll(async () => {
    await db.destroy();
  });

  describe('GET /api/users', () => {
    it('should return list of users', async () => {
      const response = await request(app)
        .get('/api/users')
        .expect(200);

      expect(response.body).toHaveProperty('users');
      expect(Array.isArray(response.body.users)).toBe(true);
    });
  });

  describe('POST /api/users', () => {
    it('should create a new user', async () => {
      const newUser = { name: 'Test User', email: 'test@example.com' };

      const response = await request(app)
        .post('/api/users')
        .send(newUser)
        .expect(201);

      expect(response.body.user.name).toBe(newUser.name);
      expect(response.body.user.email).toBe(newUser.email);
    });

    it('should return 400 for invalid data', async () => {
      const invalidUser = { name: '' };

      await request(app)
        .post('/api/users')
        .send(invalidUser)
        .expect(400);
    });
  });
});
```

## E2E 测试

### Playwright
```typescript
// login.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
  test('should login successfully with valid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.fill('[data-testid="email"]', 'user@example.com');
    await page.fill('[data-testid="password"]', 'password123');
    await page.click('[data-testid="submit"]');

    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('[data-testid="welcome-message"]')).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.fill('[data-testid="email"]', 'wrong@example.com');
    await page.fill('[data-testid="password"]', 'wrongpassword');
    await page.click('[data-testid="submit"]');

    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await expect(page).toHaveURL('/login');
  });
});
```

## TDD 流程

```
1. Red: 写一个失败的测试
2. Green: 写最少代码让测试通过
3. Refactor: 重构代码，保持测试通过
```

## 测试覆盖率配置

```javascript
// vitest.config.ts
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: ['node_modules/', 'test/'],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },
  },
});
```

## 测试命名规范

```typescript
// 格式: should [expected behavior] when [condition]
it('should return empty array when no users exist');
it('should throw error when id is invalid');
it('should update user name when valid name provided');
```

## 输出规范

- 测试代码完整可运行
- 覆盖正常情况和边界情况
- 使用清晰的测试描述
- 遵循 AAA 模式 (Arrange, Act, Assert)

## 并发测试与竞态检测

### 竞态条件测试模板
```typescript
// race-condition.test.ts — 并发读写竞态检测
import { describe, it, expect } from 'vitest';

describe('Concurrency Safety', () => {
  it('should handle concurrent writes without data loss', async () => {
    const results: number[] = [];
    const counter = { value: 0 };

    // 模拟 N 个并发写入
    const N = 100;
    const promises = Array.from({ length: N }, (_, i) =>
      Promise.resolve().then(() => {
        const current = counter.value;
        // 模拟异步间隙 (竞态窗口)
        counter.value = current + 1;
        results.push(counter.value);
      })
    );
    await Promise.all(promises);

    // 如果存在竞态，counter.value < N
    expect(counter.value).toBe(N);
  });

  it('should not deadlock under concurrent lock acquisition', async () => {
    const timeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Deadlock detected: timeout')), 5000)
    );
    const operation = runConcurrentLockTest(); // 被测函数

    // 5 秒内必须完成，否则判定为死锁
    await expect(Promise.race([operation, timeout])).resolves.toBeDefined();
  });
});
```

### 文件锁竞态测试
```typescript
// file-lock-race.test.ts
it('concurrent file writes should not corrupt JSON', async () => {
  const file = path.join(tmpDir, 'test.json');
  fs.writeFileSync(file, JSON.stringify({ count: 0 }));

  // 10 个并发进程同时 read-modify-write
  const workers = Array.from({ length: 10 }, () =>
    new Promise<void>((resolve) => {
      const data = JSON.parse(fs.readFileSync(file, 'utf8'));
      data.count++;
      const tmp = file + '.tmp.' + Math.random();
      fs.writeFileSync(tmp, JSON.stringify(data));
      fs.renameSync(tmp, file);
      resolve();
    })
  );
  await Promise.all(workers);

  // 验证: 无锁时 count < 10 (竞态丢失)
  const final = JSON.parse(fs.readFileSync(file, 'utf8'));
  // 有锁保护时应 === 10
  expect(final.count).toBeLessThanOrEqual(10);
});
```

### 并发测试检查清单
- [ ] 共享状态读写是否有锁保护?
- [ ] Promise.all 中的操作是否互相独立?
- [ ] 数据库事务隔离级别是否足够?
- [ ] 文件操作是否使用 temp+rename 原子写入?
- [ ] 计数器/ID 生成是否原子操作?
- [ ] 缓存失效时的 thundering herd 是否处理?

## 禁止事项

- ❌ 不要测试实现细节
- ❌ 不要忽略边界情况
- ❌ 不要写互相依赖的测试
- ❌ 不要忽略异步错误处理
- ❌ 不要跳过并发场景测试 (多用户/多进程操作同一资源)

## 突变测试 (Mutation Testing)

### 概念
通过微小修改源代码 (突变体) 验证现有测试是否能检测到变化。如果测试仍通过 → 测试无效。

### 手动突变检查清单
对关键函数，逐一验证以下突变是否被测试捕获:
- [ ] `>` 改为 `>=` (边界条件)
- [ ] `&&` 改为 `||` (逻辑反转)
- [ ] `+1` 改为 `-1` (off-by-one)
- [ ] `return true` 改为 `return false` (返回值反转)
- [ ] 删除一个 if 分支 (条件删除)
- [ ] 交换两个参数顺序 (参数置换)

### Stryker (JS/TS 突变测试工具)
```bash
# 安装
npx stryker init

# 运行
npx stryker run

# 报告解读
# Mutation Score = killed / (killed + survived)
# 目标: >80% (核心逻辑 >90%)
```

### 突变测试适用场景
- 金额计算、权限判断、状态机转换等高风险逻辑
- 测试覆盖率高但信心不足时
- 不适用于 UI 组件、配置文件等

