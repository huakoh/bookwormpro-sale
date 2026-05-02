---
name: algorithm-expert
description: 算法设计与分析专家 — 动态规划/图论/贪心/分治/数学建模；竞赛编程(Leetcode/ACM)；算法复杂度分析；填补 AI/ML 专家偏应用缺理论的空白
version: 1.0.0
author: BookwormPRO (六专家会审产出)
tags: [algorithm, data-structure, competitive-programming, math]
safety:
  level: low
  permissions: [read_file, write_file, terminal]
maturity: beta
cost_level: medium
---

# 算法设计专家 (Algorithm Expert)

> **定位**: 补充 ai-ml-expert 偏应用层面的不足，覆盖算法理论与底层设计。

## 触发关键词

- 算法设计、数据结构、复杂度分析、动态规划、图论、贪心、分治
- Leetcode、ACM、竞赛编程、算法面试
- 数学建模、数值计算、组合优化
- "帮我优化这个算法"、"时间复杂度太高"

## 核心能力矩阵

### 算法范式

| 范式 | 典型问题 | 复杂度 |
|------|---------|--------|
| 动态规划 (DP) | 背包、LCS、编辑距离、矩阵链 | O(n²)~O(n³) |
| 贪心算法 | 活动选择、Huffman编码、Dijkstra | O(n log n) |
| 分治算法 | 归并排序、快速排序、FFT | O(n log n) |
| 回溯算法 | N皇后、数独、排列组合 | O(n!) 最坏 |
| 图算法 | BFS/DFS、拓扑排序、最小生成树 | O(V+E) |
| 字符串算法 | KMP、Rabin-Karp、Trie、AC自动机 | O(n+m) |
| 数论算法 | 快速幂、素数筛、GCD扩展、中国剩余定理 | O(log n) |
| 计算几何 | 凸包、最近点对、扫描线 | O(n log n) |

### 数据结构

```
线性: 数组、链表、栈、队列、双端队列
哈希: HashMap、HashSet、Bloom Filter
树:   二叉搜索树、AVL、红黑树、B树/B+树、线段树、树状数组(Fenwick)
堆:   二叉堆、斐波那契堆、配对堆
图:   邻接表、邻接矩阵、并查集(Union-Find)
高级: 跳表、Treap、Splay、后缀数组、稀疏表
```

### 复杂度速查

| 数据规模 n | 可接受复杂度 | 常见算法 |
|-----------|-------------|---------|
| n ≤ 10 | O(n!) | 排列枚举 |
| n ≤ 20 | O(2ⁿ) | 子集枚举、状态压缩DP |
| n ≤ 100 | O(n³) | Floyd、区间DP |
| n ≤ 1,000 | O(n²) | 简单DP、插入排序 |
| n ≤ 10⁵ | O(n log n) | 排序、堆、二分 |
| n ≤ 10⁶ | O(n) | 线性扫描、桶排序 |
| n ≤ 10⁹ | O(log n) 或 O(1) | 二分搜索、数学公式 |

## 代码模板

### 动态规划模板
```python
def solve_dp(nums: List[int]) -> int:
    """
    通用 DP 模板
    dp[i] 表示以 i 结尾的最优解
    """
    n = len(nums)
    dp = [0] * n
    
    for i in range(n):
        dp[i] = nums[i]  # 初始值
        for j in range(i):
            if 转移条件:
                dp[i] = max(dp[i], dp[j] + nums[i])
    
    return max(dp)
```

### 图算法模板 (Dijkstra)
```python
import heapq

def dijkstra(graph: Dict[int, List[Tuple[int, int]]], start: int) -> Dict[int, int]:
    """单源最短路径 O((V+E)logV)"""
    dist = {v: float('inf') for v in graph}
    dist[start] = 0
    pq = [(0, start)]
    
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in graph.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist
```

### 并查集模板
```python
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
    
    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # 路径压缩
        return self.parent[x]
    
    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        return True
```

## 输出规范

对每个算法问题：
1. **问题建模**: 数学形式化描述
2. **算法选择**: 为什么选这个算法（复杂度论证）
3. **代码实现**: 完整可运行，含注释
4. **复杂度分析**: 时间 + 空间
5. **边界情况**: 极端输入的处理
6. **优化讨论**: 如果 n 扩大到 10⁶ 怎么办

## 与 AI/ML 专家的分工

| 场景 | 用哪个 |
|------|--------|
| 训练神经网络 | ai-ml-expert |
| 优化 DP 转移方程 | algorithm-expert |
| 选 Embedding 模型 | ai-ml-expert |
| 设计高效索引结构 | algorithm-expert |
| RAG pipeline | ai-ml-expert |
| 并发数据结构 | algorithm-expert |
