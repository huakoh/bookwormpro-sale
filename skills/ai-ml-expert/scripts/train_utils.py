#!/usr/bin/env python3
"""
AI/ML 训练工具函数
Training Utility Functions
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Optional, Callable
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EarlyStopping:
    """早停机制"""
    def __init__(self, patience: int = 5, min_delta: float = 0, mode: str = 'min'):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.early_stop = False
    
    def __call__(self, score: float) -> bool:
        if self.best_score is None:
            self.best_score = score
            return False
        
        if self.mode == 'min':
            improved = score < self.best_score - self.min_delta
        else:
            improved = score > self.best_score + self.min_delta
        
        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        
        return self.early_stop


class AverageMeter:
    """计算和存储平均值"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0
    
    def update(self, val: float, n: int = 1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def set_seed(seed: int = 42):
    """设置随机种子"""
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_device() -> torch.device:
    """获取可用设备"""
    if torch.cuda.is_available():
        return torch.device('cuda')
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


def count_parameters(model: nn.Module) -> int:
    """统计模型参数量"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def save_checkpoint(model: nn.Module, optimizer: torch.optim.Optimizer, 
                    epoch: int, loss: float, path: str):
    """保存检查点"""
    torch.save({
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': loss
    }, path)
    logger.info(f"Checkpoint saved to {path}")


def load_checkpoint(model: nn.Module, optimizer: Optional[torch.optim.Optimizer],
                    path: str, device: torch.device) -> int:
    """加载检查点"""
    checkpoint = torch.load(path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    if optimizer:
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    logger.info(f"Checkpoint loaded from {path}")
    return checkpoint['epoch']


def get_lr_scheduler(optimizer: torch.optim.Optimizer, scheduler_type: str,
                     num_epochs: int, **kwargs):
    """获取学习率调度器"""
    if scheduler_type == 'cosine':
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
    elif scheduler_type == 'step':
        return torch.optim.lr_scheduler.StepLR(optimizer, step_size=kwargs.get('step_size', 10))
    elif scheduler_type == 'plateau':
        return torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=5)
    elif scheduler_type == 'warmup_cosine':
        from transformers import get_cosine_schedule_with_warmup
        return get_cosine_schedule_with_warmup(
            optimizer,
            num_warmup_steps=kwargs.get('warmup_steps', 0),
            num_training_steps=kwargs.get('total_steps', num_epochs)
        )
    else:
        return None


class Trainer:
    """通用训练器"""
    def __init__(self, model: nn.Module, optimizer: torch.optim.Optimizer,
                 criterion: nn.Module, device: torch.device,
                 scheduler: Optional = None):
        self.model = model.to(device)
        self.optimizer = optimizer
        self.criterion = criterion
        self.device = device
        self.scheduler = scheduler
        self.history = {'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': []}
    
    def train_epoch(self, dataloader) -> Dict[str, float]:
        self.model.train()
        loss_meter = AverageMeter()
        acc_meter = AverageMeter()
        
        for batch in dataloader:
            x = batch['x'].to(self.device)
            y = batch['y'].to(self.device)
            
            self.optimizer.zero_grad()
            outputs = self.model(x)
            loss = self.criterion(outputs, y)
            loss.backward()
            
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            
            # 计算准确率
            preds = outputs.argmax(dim=1)
            acc = (preds == y).float().mean().item()
            
            loss_meter.update(loss.item(), x.size(0))
            acc_meter.update(acc, x.size(0))
        
        return {'loss': loss_meter.avg, 'acc': acc_meter.avg}
    
    @torch.no_grad()
    def evaluate(self, dataloader) -> Dict[str, float]:
        self.model.eval()
        loss_meter = AverageMeter()
        acc_meter = AverageMeter()
        
        for batch in dataloader:
            x = batch['x'].to(self.device)
            y = batch['y'].to(self.device)
            
            outputs = self.model(x)
            loss = self.criterion(outputs, y)
            
            preds = outputs.argmax(dim=1)
            acc = (preds == y).float().mean().item()
            
            loss_meter.update(loss.item(), x.size(0))
            acc_meter.update(acc, x.size(0))
        
        return {'loss': loss_meter.avg, 'acc': acc_meter.avg}
    
    def fit(self, train_loader, val_loader, epochs: int,
            early_stopping: Optional[EarlyStopping] = None,
            save_path: Optional[str] = None):
        best_val_loss = float('inf')
        
        for epoch in range(epochs):
            start_time = time.time()
            
            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.evaluate(val_loader)
            
            if self.scheduler:
                self.scheduler.step()
            
            # 记录历史
            self.history['train_loss'].append(train_metrics['loss'])
            self.history['val_loss'].append(val_metrics['loss'])
            self.history['train_acc'].append(train_metrics['acc'])
            self.history['val_acc'].append(val_metrics['acc'])
            
            elapsed = time.time() - start_time
            logger.info(
                f"Epoch {epoch+1}/{epochs} ({elapsed:.1f}s) - "
                f"train_loss: {train_metrics['loss']:.4f}, train_acc: {train_metrics['acc']:.4f}, "
                f"val_loss: {val_metrics['loss']:.4f}, val_acc: {val_metrics['acc']:.4f}"
            )
            
            # 保存最优模型
            if val_metrics['loss'] < best_val_loss:
                best_val_loss = val_metrics['loss']
                if save_path:
                    save_checkpoint(self.model, self.optimizer, epoch, val_metrics['loss'], save_path)
            
            # 早停
            if early_stopping and early_stopping(val_metrics['loss']):
                logger.info(f"Early stopping at epoch {epoch+1}")
                break
        
        return self.history


if __name__ == '__main__':
    # 测试
    set_seed(42)
    device = get_device()
    print(f"Using device: {device}")
    
    # 简单模型测试
    model = nn.Linear(10, 2)
    print(f"Parameters: {count_parameters(model)}")
