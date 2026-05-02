# Pandas 数据处理指南

## 数据加载

```python
# 基础加载
df = pd.read_csv('data.csv')
df = pd.read_excel('data.xlsx', sheet_name='Sheet1')

# 大文件优化
df = pd.read_csv('large.csv', 
    dtype={'id': 'int32', 'name': 'category'},
    usecols=['id', 'name', 'value'],
    parse_dates=['date'],
    chunksize=100000
)
```

## 数据清洗

### 链式操作
```python
df_clean = (df
    .drop_duplicates(subset=['id'])
    .dropna(subset=['critical_col'])
    .assign(
        date=lambda x: pd.to_datetime(x['date']),
        value_norm=lambda x: (x['value'] - x['value'].mean()) / x['value'].std()
    )
    .query('value > 0')
    .reset_index(drop=True)
)
```

### 缺失值处理
```python
# 查看缺失
df.isnull().sum()
df.isnull().mean() * 100

# 删除高缺失列 (>50%)
df = df.drop(columns=df.columns[df.isnull().mean() > 0.5])

# 填充
num_cols = df.select_dtypes(include=[np.number]).columns
cat_cols = df.select_dtypes(include=['object']).columns
df[num_cols] = df[num_cols].fillna(df[num_cols].median())
df[cat_cols] = df[cat_cols].fillna(df[cat_cols].mode().iloc[0])
```

### 异常值处理
```python
# IQR方法
def remove_outliers_iqr(df, col, k=1.5):
    Q1, Q3 = df[col].quantile([0.25, 0.75])
    IQR = Q3 - Q1
    return df[(df[col] >= Q1 - k*IQR) & (df[col] <= Q3 + k*IQR)]

# Z-score方法
from scipy import stats
df = df[np.abs(stats.zscore(df[col])) < 3]
```

## 特征工程

### 时间特征
```python
df['year'] = df['date'].dt.year
df['month'] = df['date'].dt.month
df['day_of_week'] = df['date'].dt.dayofweek
df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
df['quarter'] = df['date'].dt.quarter
```

### 分箱
```python
df['age_group'] = pd.cut(df['age'], 
    bins=[0, 18, 30, 45, 60, 100],
    labels=['<18', '18-30', '30-45', '45-60', '60+']
)
df['value_q'] = pd.qcut(df['value'], q=4, labels=['Q1','Q2','Q3','Q4'])
```

### 编码
```python
# 标签编码
df['cat_code'] = df['category'].astype('category').cat.codes

# One-Hot
df = pd.get_dummies(df, columns=['category'], prefix='cat')
```

## 聚合分析

```python
# 多维聚合
summary = (df
    .groupby(['region', 'product'])
    .agg({
        'revenue': ['sum', 'mean'],
        'quantity': 'sum',
        'user_id': 'nunique'
    })
)
summary.columns = ['_'.join(c) for c in summary.columns]

# 透视表
pivot = df.pivot_table(
    values='revenue',
    index='region',
    columns='quarter',
    aggfunc='sum',
    margins=True
)
```

## 数据合并

```python
# Merge
df = pd.merge(df1, df2, on='id', how='left')

# Concat
df = pd.concat([df1, df2], ignore_index=True)
```

## 性能优化

```python
# 内存优化
for col in df.select_dtypes(include=['int']).columns:
    df[col] = pd.to_numeric(df[col], downcast='integer')
for col in df.select_dtypes(include=['object']).columns:
    if df[col].nunique() / len(df) < 0.5:
        df[col] = df[col].astype('category')

# 向量化
df['new'] = np.where(df['value'] > 100, 'high', 'low')
```
