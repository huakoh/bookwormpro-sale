#!/usr/bin/env python3
"""
数据分析工具函数
Data Analysis Utility Functions
"""

import pandas as pd
import numpy as np
from scipy import stats


def data_overview(df: pd.DataFrame) -> dict:
    """数据概览"""
    return {
        'shape': df.shape,
        'memory_mb': df.memory_usage(deep=True).sum() / 1024**2,
        'dtypes': df.dtypes.value_counts().to_dict(),
        'missing': df.isnull().sum()[df.isnull().sum() > 0].to_dict(),
        'duplicates': df.duplicated().sum()
    }


def handle_missing(df: pd.DataFrame, strategy: str = 'auto') -> pd.DataFrame:
    """
    处理缺失值
    strategy: 'auto' | 'drop' | 'fill_median' | 'fill_mode'
    """
    df = df.copy()
    
    if strategy == 'drop':
        return df.dropna()
    
    num_cols = df.select_dtypes(include=[np.number]).columns
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    
    if strategy in ['auto', 'fill_median']:
        df[num_cols] = df[num_cols].fillna(df[num_cols].median())
    
    if strategy in ['auto', 'fill_mode']:
        for col in cat_cols:
            df[col] = df[col].fillna(df[col].mode().iloc[0] if len(df[col].mode()) > 0 else 'Unknown')
    
    return df


def remove_outliers(df: pd.DataFrame, column: str, method: str = 'iqr', threshold: float = 1.5) -> pd.DataFrame:
    """
    移除异常值
    method: 'iqr' | 'zscore'
    """
    if method == 'iqr':
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - threshold * IQR
        upper = Q3 + threshold * IQR
        return df[(df[column] >= lower) & (df[column] <= upper)]
    
    elif method == 'zscore':
        z_scores = np.abs(stats.zscore(df[column].dropna()))
        mask = np.zeros(len(df), dtype=bool)
        mask[df[column].notna()] = z_scores < threshold
        return df[mask]
    
    return df


def add_time_features(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    """添加时间特征"""
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column])
    
    df['year'] = df[date_column].dt.year
    df['month'] = df[date_column].dt.month
    df['day'] = df[date_column].dt.day
    df['day_of_week'] = df[date_column].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    df['quarter'] = df[date_column].dt.quarter
    df['week_of_year'] = df[date_column].dt.isocalendar().week
    
    return df


def correlation_analysis(df: pd.DataFrame, threshold: float = 0.7) -> pd.DataFrame:
    """相关性分析，返回高相关对"""
    corr = df.select_dtypes(include=[np.number]).corr()
    
    high_corr = []
    for i in range(len(corr.columns)):
        for j in range(i+1, len(corr.columns)):
            if abs(corr.iloc[i, j]) > threshold:
                high_corr.append({
                    'var1': corr.columns[i],
                    'var2': corr.columns[j],
                    'correlation': round(corr.iloc[i, j], 3)
                })
    
    return pd.DataFrame(high_corr).sort_values('correlation', key=abs, ascending=False)


def ab_test(control_success: int, control_total: int, 
            treatment_success: int, treatment_total: int,
            alpha: float = 0.05) -> dict:
    """A/B测试比例检验"""
    from statsmodels.stats.proportion import proportions_ztest
    
    count = np.array([treatment_success, control_success])
    nobs = np.array([treatment_total, control_total])
    
    stat, p_value = proportions_ztest(count, nobs)
    
    control_rate = control_success / control_total
    treatment_rate = treatment_success / treatment_total
    lift = (treatment_rate - control_rate) / control_rate * 100
    
    return {
        'control_rate': f"{control_rate:.2%}",
        'treatment_rate': f"{treatment_rate:.2%}",
        'lift': f"{lift:.2f}%",
        'p_value': round(p_value, 4),
        'significant': p_value < alpha,
        'recommendation': '采用新方案' if (p_value < alpha and lift > 0) else '保持原方案'
    }


if __name__ == '__main__':
    # 测试
    df = pd.DataFrame({
        'a': [1, 2, 3, None, 5],
        'b': ['x', 'y', None, 'x', 'y'],
        'c': [10, 20, 100, 40, 50]
    })
    
    print("Overview:", data_overview(df))
    print("\nAfter handling missing:", handle_missing(df))
