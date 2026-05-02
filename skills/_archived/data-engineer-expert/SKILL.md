---
name: data-engineer-expert
description: >
  数据工程师专家。当用户需要进行数据管道设计、ETL 开发、数据仓库建模、流处理、
  Spark/Kafka/Airflow/dbt 使用、维度建模、数据质量，
  或说 "数据工程"、"ETL"、"数据管道" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [data-analyst-expert, database-tuning-expert]
---

# 数据工程师 (Data Engineer Expert)

> **Output Style**: 本技能使用内联输出规范

资深数据工程师，精通数据管道设计、ETL 开发、数据仓库建模和流处理技术。

## 触发关键词

- **数据处理**: `ETL`, `数据管道`, `数据流`, `数据处理`
- **存储**: `数据仓库`, `数据湖`, `数据集市`, `OLAP`
- **工具**: `Spark`, `Kafka`, `Airflow`, `dbt`, `Flink`
- **建模**: `维度建模`, `星型模型`, `雪花模型`
- **质量**: `数据质量`, `数据治理`, `数据血缘`

## 技术栈

### 批处理
- **Apache Spark**: 大规模数据处理
- **dbt**: 数据转换和建模
- **Apache Airflow**: 工作流编排

### 流处理
- **Apache Kafka**: 消息队列
- **Apache Flink**: 实时流处理
- **Kafka Streams**: 轻量流处理

### 数据存储
- **Snowflake/BigQuery**: 云数据仓库
- **Delta Lake**: 数据湖格式
- **Apache Iceberg**: 表格式

## 数据管道设计

### Airflow DAG
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-team',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='user_analytics_pipeline',
    default_args=default_args,
    schedule_interval='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    
    extract = PythonOperator(
        task_id='extract_data',
        python_callable=extract_from_source,
    )
    
    transform = PythonOperator(
        task_id='transform_data',
        python_callable=transform_data,
    )
    
    load = PythonOperator(
        task_id='load_to_warehouse',
        python_callable=load_to_warehouse,
    )
    
    extract >> transform >> load
```

### dbt 模型
```sql
-- models/marts/dim_users.sql
{{ config(materialized='table') }}

WITH source_users AS (
    SELECT * FROM {{ ref('stg_users') }}
),

enriched AS (
    SELECT
        user_id,
        email,
        created_at,
        COALESCE(country, 'Unknown') AS country,
        DATE_TRUNC('month', created_at) AS signup_month,
        CASE 
            WHEN last_login_at > CURRENT_DATE - INTERVAL '30 days' THEN 'active'
            ELSE 'inactive'
        END AS status
    FROM source_users
)

SELECT * FROM enriched
```

### Spark ETL
```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, sum as spark_sum

spark = SparkSession.builder \
    .appName("UserAnalytics") \
    .getOrCreate()

# 读取数据
df = spark.read.parquet("s3://data-lake/users/")

# 转换
result = df \
    .filter(col("created_at") >= "2024-01-01") \
    .groupBy("country") \
    .agg(
        spark_sum("revenue").alias("total_revenue"),
        spark_sum(when(col("is_active"), 1).otherwise(0)).alias("active_users")
    )

# 写入
result.write \
    .mode("overwrite") \
    .parquet("s3://data-warehouse/user_metrics/")
```

## 维度建模

### 星型模型
```sql
-- 事实表
CREATE TABLE fact_orders (
    order_id BIGINT PRIMARY KEY,
    user_id BIGINT REFERENCES dim_users(user_id),
    product_id BIGINT REFERENCES dim_products(product_id),
    date_id INT REFERENCES dim_date(date_id),
    quantity INT,
    revenue DECIMAL(18, 2),
    created_at TIMESTAMP
);

-- 维度表
CREATE TABLE dim_users (
    user_id BIGINT PRIMARY KEY,
    email VARCHAR(255),
    name VARCHAR(255),
    country VARCHAR(100),
    tier VARCHAR(50)
);

CREATE TABLE dim_date (
    date_id INT PRIMARY KEY,
    date DATE,
    year INT,
    quarter INT,
    month INT,
    week INT,
    day_of_week INT
);
```

## 数据质量

### Great Expectations
```python
import great_expectations as gx

context = gx.get_context()

# 定义期望
validator = context.sources.pandas_default.read_csv("users.csv")
validator.expect_column_values_to_not_be_null("user_id")
validator.expect_column_values_to_be_unique("email")
validator.expect_column_values_to_be_between("age", 0, 150)

# 验证
results = validator.validate()
```

## 输出规范

- 使用中文注释
- 提供完整的管道代码
- 说明数据流向
- 包含错误处理和重试
- 考虑数据质量检查

## 禁止事项

- ❌ 不要忽略数据质量检查
- ❌ 不要硬编码凭据
- ❌ 不要忽略幂等性设计
- ❌ 不要跳过数据血缘记录

