#!/usr/bin/env python3
"""
AI/ML 评估工具函数
Evaluation Utility Functions
"""

import numpy as np
import torch
from typing import Dict, List, Optional, Union
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    mean_squared_error, mean_absolute_error, r2_score
)
import matplotlib.pyplot as plt
import seaborn as sns


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                          y_proba: Optional[np.ndarray] = None,
                          average: str = 'macro') -> Dict[str, float]:
    """计算分类指标"""
    metrics = {
        'accuracy': accuracy_score(y_true, y_pred),
        'precision': precision_score(y_true, y_pred, average=average, zero_division=0),
        'recall': recall_score(y_true, y_pred, average=average, zero_division=0),
        'f1': f1_score(y_true, y_pred, average=average, zero_division=0)
    }
    
    if y_proba is not None:
        try:
            if y_proba.ndim == 1 or y_proba.shape[1] == 2:
                # 二分类
                proba = y_proba[:, 1] if y_proba.ndim == 2 else y_proba
                metrics['auc'] = roc_auc_score(y_true, proba)
            else:
                # 多分类
                metrics['auc'] = roc_auc_score(y_true, y_proba, multi_class='ovr', average=average)
        except Exception:
            pass
    
    return metrics


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """计算回归指标"""
    return {
        'mse': mean_squared_error(y_true, y_pred),
        'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
        'mae': mean_absolute_error(y_true, y_pred),
        'r2': r2_score(y_true, y_pred),
        'mape': np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
    }


def plot_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray,
                         class_names: Optional[List[str]] = None,
                         normalize: bool = True,
                         figsize: tuple = (10, 8)) -> plt.Figure:
    """绘制混淆矩阵"""
    cm = confusion_matrix(y_true, y_pred)
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(cm, annot=True, fmt='.2f' if normalize else 'd',
                cmap='Blues', ax=ax,
                xticklabels=class_names, yticklabels=class_names)
    ax.set_xlabel('预测标签')
    ax.set_ylabel('真实标签')
    ax.set_title('混淆矩阵' + (' (归一化)' if normalize else ''))
    plt.tight_layout()
    return fig


def plot_roc_curve(y_true: np.ndarray, y_proba: np.ndarray,
                  class_names: Optional[List[str]] = None,
                  figsize: tuple = (10, 8)) -> plt.Figure:
    """绘制 ROC 曲线"""
    from sklearn.metrics import roc_curve, auc
    from sklearn.preprocessing import label_binarize
    
    fig, ax = plt.subplots(figsize=figsize)
    
    if y_proba.ndim == 1 or y_proba.shape[1] == 2:
        # 二分类
        proba = y_proba[:, 1] if y_proba.ndim == 2 else y_proba
        fpr, tpr, _ = roc_curve(y_true, proba)
        roc_auc = auc(fpr, tpr)
        ax.plot(fpr, tpr, label=f'ROC (AUC = {roc_auc:.3f})')
    else:
        # 多分类
        n_classes = y_proba.shape[1]
        y_bin = label_binarize(y_true, classes=range(n_classes))
        
        for i in range(n_classes):
            fpr, tpr, _ = roc_curve(y_bin[:, i], y_proba[:, i])
            roc_auc = auc(fpr, tpr)
            label = class_names[i] if class_names else f'Class {i}'
            ax.plot(fpr, tpr, label=f'{label} (AUC = {roc_auc:.3f})')
    
    ax.plot([0, 1], [0, 1], 'k--', label='随机')
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title('ROC 曲线')
    ax.legend(loc='lower right')
    plt.tight_layout()
    return fig


def plot_precision_recall_curve(y_true: np.ndarray, y_proba: np.ndarray,
                               figsize: tuple = (10, 8)) -> plt.Figure:
    """绘制 PR 曲线"""
    from sklearn.metrics import precision_recall_curve, average_precision_score
    
    fig, ax = plt.subplots(figsize=figsize)
    
    proba = y_proba[:, 1] if y_proba.ndim == 2 else y_proba
    precision, recall, _ = precision_recall_curve(y_true, proba)
    ap = average_precision_score(y_true, proba)
    
    ax.plot(recall, precision, label=f'PR (AP = {ap:.3f})')
    ax.set_xlabel('Recall')
    ax.set_ylabel('Precision')
    ax.set_title('Precision-Recall 曲线')
    ax.legend()
    plt.tight_layout()
    return fig


def plot_learning_curves(history: Dict[str, List[float]],
                        figsize: tuple = (12, 4)) -> plt.Figure:
    """绘制学习曲线"""
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    
    # Loss
    axes[0].plot(history['train_loss'], label='Train')
    if 'val_loss' in history:
        axes[0].plot(history['val_loss'], label='Validation')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].set_title('Loss 曲线')
    axes[0].legend()
    
    # Accuracy
    if 'train_acc' in history:
        axes[1].plot(history['train_acc'], label='Train')
        if 'val_acc' in history:
            axes[1].plot(history['val_acc'], label='Validation')
        axes[1].set_xlabel('Epoch')
        axes[1].set_ylabel('Accuracy')
        axes[1].set_title('Accuracy 曲线')
        axes[1].legend()
    
    plt.tight_layout()
    return fig


def plot_feature_importance(importance: np.ndarray, feature_names: List[str],
                           top_k: int = 20, figsize: tuple = (10, 8)) -> plt.Figure:
    """绘制特征重要性"""
    idx = np.argsort(importance)[-top_k:]
    
    fig, ax = plt.subplots(figsize=figsize)
    ax.barh(range(len(idx)), importance[idx])
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([feature_names[i] for i in idx])
    ax.set_xlabel('重要性')
    ax.set_title(f'特征重要性 Top {top_k}')
    plt.tight_layout()
    return fig


def print_classification_report(y_true: np.ndarray, y_pred: np.ndarray,
                               class_names: Optional[List[str]] = None):
    """打印分类报告"""
    print("\n" + "="*60)
    print("分类报告")
    print("="*60)
    print(classification_report(y_true, y_pred, target_names=class_names, digits=4))


# NER 评估
def ner_metrics(y_true: List[List[str]], y_pred: List[List[str]]) -> Dict[str, float]:
    """NER 实体级别评估"""
    from seqeval.metrics import f1_score as seq_f1, precision_score as seq_p, recall_score as seq_r
    
    return {
        'precision': seq_p(y_true, y_pred),
        'recall': seq_r(y_true, y_pred),
        'f1': seq_f1(y_true, y_pred)
    }


# 目标检测评估
def compute_iou(box1: np.ndarray, box2: np.ndarray) -> float:
    """计算 IoU"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0


if __name__ == '__main__':
    # 测试分类指标
    y_true = np.array([0, 1, 1, 0, 1, 0, 1, 1])
    y_pred = np.array([0, 1, 0, 0, 1, 1, 1, 1])
    y_proba = np.array([[0.8, 0.2], [0.3, 0.7], [0.6, 0.4], [0.9, 0.1],
                        [0.2, 0.8], [0.4, 0.6], [0.3, 0.7], [0.1, 0.9]])
    
    metrics = classification_metrics(y_true, y_pred, y_proba)
    print("分类指标:", metrics)
    
    # 测试回归指标
    y_true_reg = np.array([3.0, 5.0, 2.5, 7.0])
    y_pred_reg = np.array([2.8, 5.2, 2.3, 6.8])
    
    metrics_reg = regression_metrics(y_true_reg, y_pred_reg)
    print("回归指标:", metrics_reg)
