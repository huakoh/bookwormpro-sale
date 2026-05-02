# SQL 分析查询模板

## 窗口函数

```sql
-- 排名
SELECT 
    user_id, amount,
    ROW_NUMBER() OVER (ORDER BY amount DESC) as rank,
    NTILE(4) OVER (ORDER BY amount DESC) as quartile
FROM orders;

-- 同比环比
SELECT 
    DATE_TRUNC('month', order_date) as month,
    SUM(amount) as revenue,
    LAG(SUM(amount), 1) OVER (ORDER BY DATE_TRUNC('month', order_date)) as prev_month,
    LAG(SUM(amount), 12) OVER (ORDER BY DATE_TRUNC('month', order_date)) as prev_year
FROM orders
GROUP BY 1;

-- 累计
SELECT 
    order_date,
    daily_revenue,
    SUM(daily_revenue) OVER (ORDER BY order_date) as cumulative
FROM daily_stats;
```

## 留存分析

```sql
WITH cohort AS (
    SELECT user_id, DATE_TRUNC('week', MIN(order_date)) as cohort_week
    FROM orders GROUP BY 1
),
activity AS (
    SELECT 
        o.user_id, c.cohort_week,
        DATE_TRUNC('week', o.order_date) - c.cohort_week as weeks_since
    FROM orders o JOIN cohort c ON o.user_id = c.user_id
)
SELECT 
    cohort_week,
    weeks_since,
    COUNT(DISTINCT user_id) as users,
    COUNT(DISTINCT user_id) * 100.0 / 
        FIRST_VALUE(COUNT(DISTINCT user_id)) OVER (PARTITION BY cohort_week ORDER BY weeks_since) as retention
FROM activity
WHERE weeks_since >= 0
GROUP BY 1, 2;
```

## 漏斗分析

```sql
WITH funnel AS (
    SELECT 
        user_id,
        MAX(CASE WHEN event='view' THEN 1 ELSE 0 END) as step1,
        MAX(CASE WHEN event='cart' THEN 1 ELSE 0 END) as step2,
        MAX(CASE WHEN event='checkout' THEN 1 ELSE 0 END) as step3,
        MAX(CASE WHEN event='pay' THEN 1 ELSE 0 END) as step4
    FROM events GROUP BY 1
)
SELECT 
    SUM(step1) as view,
    SUM(step2) as cart,
    SUM(step3) as checkout,
    SUM(step4) as pay,
    ROUND(SUM(step2)*100.0/SUM(step1), 2) as view_to_cart,
    ROUND(SUM(step4)*100.0/SUM(step3), 2) as checkout_to_pay
FROM funnel;
```

## RFM分析

```sql
WITH rfm AS (
    SELECT 
        user_id,
        CURRENT_DATE - MAX(order_date) as recency,
        COUNT(*) as frequency,
        SUM(amount) as monetary
    FROM orders
    WHERE order_date >= CURRENT_DATE - INTERVAL '1 year'
    GROUP BY 1
),
scores AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency DESC) as r,
        NTILE(5) OVER (ORDER BY frequency) as f,
        NTILE(5) OVER (ORDER BY monetary) as m
    FROM rfm
)
SELECT *,
    CASE 
        WHEN r>=4 AND f>=4 AND m>=4 THEN '高价值'
        WHEN r>=4 AND f<3 THEN '新客户'
        WHEN r<2 AND f>=4 THEN '流失风险'
        WHEN r<2 AND f<2 THEN '已流失'
        ELSE '一般客户'
    END as segment
FROM scores;
```

## 用户分群

```sql
-- 活跃度分群
SELECT 
    user_id,
    CASE 
        WHEN last_active >= CURRENT_DATE - 7 THEN '活跃'
        WHEN last_active >= CURRENT_DATE - 30 THEN '沉默'
        WHEN last_active >= CURRENT_DATE - 90 THEN '流失风险'
        ELSE '流失'
    END as activity_segment
FROM users;
```

## 常用聚合

```sql
-- 多维度聚合
SELECT 
    region, category,
    COUNT(*) as orders,
    COUNT(DISTINCT user_id) as users,
    SUM(amount) as revenue,
    AVG(amount) as avg_order_value
FROM orders
GROUP BY 1, 2
ORDER BY revenue DESC;

-- 百分比
SELECT 
    category,
    revenue,
    ROUND(revenue * 100.0 / SUM(revenue) OVER (), 2) as pct
FROM category_stats;
```
