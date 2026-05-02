# 数据可视化模板

## 环境配置

```python
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
```

## 分布图

```python
def plot_dist(df, col):
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    
    sns.histplot(df[col], kde=True, ax=ax[0])
    ax[0].axvline(df[col].mean(), c='r', ls='--', label=f'均值:{df[col].mean():.1f}')
    ax[0].legend()
    
    sns.boxplot(x=df[col], ax=ax[1])
    plt.tight_layout()
    return fig
```

## 对比图

```python
def plot_compare(df, cat, val):
    order = df.groupby(cat)[val].mean().sort_values(ascending=False).index
    
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=df, x=cat, y=val, order=order, ax=ax)
    ax.tick_params(axis='x', rotation=45)
    
    for p in ax.patches:
        ax.annotate(f'{p.get_height():.1f}', 
                   (p.get_x() + p.get_width()/2, p.get_height()),
                   ha='center', va='bottom')
    plt.tight_layout()
    return fig
```

## 时间序列

```python
def plot_trend(df, date_col, val_col):
    fig = px.line(df, x=date_col, y=val_col)
    
    # 添加移动平均
    df['MA7'] = df[val_col].rolling(7).mean()
    fig.add_scatter(x=df[date_col], y=df['MA7'], name='7日均线', line=dict(dash='dash'))
    
    fig.update_layout(hovermode='x unified')
    return fig
```

## 热力图

```python
def plot_heatmap(df):
    corr = df.select_dtypes(include=[np.number]).corr()
    
    plt.figure(figsize=(10, 8))
    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r', center=0)
    plt.tight_layout()
    return plt.gcf()
```

## 漏斗图

```python
def plot_funnel(stages, values):
    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textposition="inside",
        textinfo="value+percent initial"
    ))
    return fig

# 示例
plot_funnel(['访问','浏览','加购','支付'], [10000, 5000, 1000, 500])
```

## 饼图

```python
def plot_pie(series, title=''):
    fig, ax = plt.subplots()
    series.plot(kind='pie', autopct='%1.1f%%', ax=ax)
    ax.set_ylabel('')
    ax.set_title(title)
    return fig
```

## 组合仪表板

```python
def plot_dashboard(df, num_col, cat_col, date_col):
    fig = plt.figure(figsize=(14, 10))
    
    ax1 = fig.add_subplot(2, 2, 1)
    sns.histplot(df[num_col], kde=True, ax=ax1)
    
    ax2 = fig.add_subplot(2, 2, 2)
    df.groupby(cat_col)[num_col].mean().plot(kind='bar', ax=ax2)
    
    ax3 = fig.add_subplot(2, 2, 3)
    df.groupby(date_col)[num_col].sum().plot(ax=ax3)
    
    ax4 = fig.add_subplot(2, 2, 4)
    df[cat_col].value_counts().plot(kind='pie', ax=ax4, autopct='%1.1f%%')
    
    plt.tight_layout()
    return fig
```

## 保存图表

```python
plt.savefig('chart.png', dpi=300, bbox_inches='tight')
fig.write_html('chart.html')  # Plotly
```
