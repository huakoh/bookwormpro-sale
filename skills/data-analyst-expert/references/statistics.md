# 统计分析和假设检验

## 描述性统计

```python
def describe_column(series):
    return {
        'count': len(series),
        'mean': series.mean(),
        'std': series.std(),
        'min': series.min(),
        'q25': series.quantile(0.25),
        'median': series.median(),
        'q75': series.quantile(0.75),
        'max': series.max(),
        'skew': series.skew(),
        'kurtosis': series.kurtosis()
    }
```

## T检验

```python
from scipy import stats

# 独立样本T检验（两组均值比较）
stat, p = stats.ttest_ind(group1, group2)

# 配对T检验
stat, p = stats.ttest_rel(before, after)

# 单样本T检验
stat, p = stats.ttest_1samp(sample, popmean=100)

# 结果解读
print(f"p={p:.4f}, {'显著' if p < 0.05 else '不显著'}")
```

## 卡方检验

```python
# 分类变量独立性检验
contingency = pd.crosstab(df['col1'], df['col2'])
chi2, p, dof, expected = stats.chi2_contingency(contingency)
```

## A/B测试

```python
from statsmodels.stats.proportion import proportions_ztest

def ab_test(ctrl_conv, ctrl_n, treat_conv, treat_n, alpha=0.05):
    count = np.array([treat_conv, ctrl_conv])
    nobs = np.array([treat_n, ctrl_n])
    stat, p = proportions_ztest(count, nobs)
    
    ctrl_rate = ctrl_conv / ctrl_n
    treat_rate = treat_conv / treat_n
    lift = (treat_rate - ctrl_rate) / ctrl_rate * 100
    
    return {
        'ctrl_rate': f"{ctrl_rate:.2%}",
        'treat_rate': f"{treat_rate:.2%}",
        'lift': f"{lift:.1f}%",
        'p_value': p,
        'significant': p < alpha
    }
```

## ANOVA

```python
# 单因素方差分析
f_stat, p = stats.f_oneway(g1, g2, g3)

# 事后检验
from statsmodels.stats.multicomp import pairwise_tukeyhsd
tukey = pairwise_tukeyhsd(df['value'], df['group'])
print(tukey.summary())
```

## 相关性分析

```python
# Pearson/Spearman相关
corr = df.select_dtypes(include=[np.number]).corr(method='pearson')

# 找高相关对
high_corr = []
for i in range(len(corr.columns)):
    for j in range(i+1, len(corr.columns)):
        if abs(corr.iloc[i,j]) > 0.7:
            high_corr.append((corr.columns[i], corr.columns[j], corr.iloc[i,j]))
```

## 回归分析

```python
import statsmodels.api as sm

X = df[features]
y = df[target]
X = sm.add_constant(X)

model = sm.OLS(y, X).fit()
print(model.summary())
print(f"R² = {model.rsquared:.4f}")
```

## 效应量

```python
# Cohen's d
def cohens_d(g1, g2):
    n1, n2 = len(g1), len(g2)
    pooled_std = np.sqrt(((n1-1)*g1.var() + (n2-1)*g2.var()) / (n1+n2-2))
    return (g1.mean() - g2.mean()) / pooled_std
# |d| < 0.2 小, 0.2-0.8 中, > 0.8 大
```

## 样本量计算

```python
from statsmodels.stats.power import TTestIndPower

analysis = TTestIndPower()
n = analysis.solve_power(effect_size=0.5, alpha=0.05, power=0.8)
print(f"每组需要 {int(np.ceil(n))} 样本")
```
