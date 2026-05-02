---
name: ai-ml-expert
description: >
safety:
  level: medium
  permissions: [read_file, write_file, terminal]
  AI/机器学习专家。当用户需要 PyTorch、TensorFlow、深度学习、神经网络、
  NLP 自然语言处理、CV 计算机视觉、LLM 大语言模型、RAG 检索增强、
  Prompt Engineering、模型微调 Fine-tuning、Agent 开发、Hugging Face、
  LangChain，或说 "机器学习"、"AI"、"模型训练" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
cost_level: high
last-reviewed: 2026-02-18
---

# AI/机器学习专家 (AI/ML Expert)

> **Output Style**: 本技能使用内联输出规范

AI/机器学习专家，专注于机器学习建模、深度学习、NLP、CV、LLM 应用开发的完整流程。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 通用 | AI, 机器学习, 深度学习, 神经网络, 模型训练 |
| 框架 | PyTorch, TensorFlow, Keras, Transformers, scikit-learn |
| NLP | 文本分类, NER, 文本生成, 语义搜索, Embedding |
| CV | 图像分类, 目标检测, 分割, OCR, YOLO |
| LLM | LLM, GPT, BERT, LLaMA, Qwen, ChatGPT, 大模型 |
| 应用 | RAG, Agent, LangChain, Prompt Engineering, 微调, LoRA |
| 传统ML | XGBoost, LightGBM, 分类, 回归, 聚类, 特征工程 |

## 核心能力

| 领域 | 技术栈 |
|------|--------|
| 传统ML | 分类、回归、聚类、特征工程、集成学习 |
| 深度学习 | CNN、RNN/LSTM、Transformer、GAN |
| NLP | 文本分类、NER、文本生成、语义搜索、RAG |
| CV | 图像分类、目标检测、分割、OCR |
| LLM | Prompt Engineering、Fine-tuning、Agent、RAG |
| MLOps | 训练、评估、监控 |

## 任务-模型速查

| 任务类型 | 推荐模型 |
|---------|---------|
| 表格分类/回归 | XGBoost, LightGBM, CatBoost |
| 文本分类 | BERT, RoBERTa, 中文用 BERT-wwm |
| 文本生成 | GPT系列, LLaMA, Qwen |
| NER | BERT+CRF, GlobalPointer |
| 图像分类 | ResNet, EfficientNet, ViT |
| 目标检测 | YOLOv8, RT-DETR |
| 语义分割 | U-Net, DeepLabV3+ |
| RAG系统 | Embedding + VectorDB + LLM |

## 快速开始

### PyTorch 模型模板
```python
import torch
import torch.nn as nn

class Model(nn.Module):
    def __init__(self, config):
        super().__init__()
        # 定义层

    def forward(self, x):
        return x

# 训练循环
for epoch in range(epochs):
    model.train()
    for batch in train_loader:
        optimizer.zero_grad()
        loss = criterion(model(batch['x']), batch['y'])
        loss.backward()
        optimizer.step()
```

### Hugging Face 快速使用
```python
from transformers import AutoTokenizer, AutoModel

tokenizer = AutoTokenizer.from_pretrained("bert-base-chinese")
model = AutoModel.from_pretrained("bert-base-chinese")

inputs = tokenizer("你好世界", return_tensors="pt")
outputs = model(**inputs)
```

### LangChain RAG
```python
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA

vectorstore = Chroma.from_documents(docs, OpenAIEmbeddings())
qa = RetrievalQA.from_chain_type(llm, retriever=vectorstore.as_retriever())
answer = qa.run("你的问题")
```

## 评估指标

| 任务 | 指标 |
|-----|------|
| 二分类 | AUC, F1, Precision, Recall |
| 多分类 | Accuracy, Macro-F1, Confusion Matrix |
| 回归 | MSE, MAE, R², MAPE |
| NER | Entity-level F1 |
| 生成 | BLEU, ROUGE, Perplexity |
| 检测 | mAP, IoU |

## 参考文档

- `references/pytorch-guide.md` - PyTorch 深度学习指南
- `references/transformers-guide.md` - Hugging Face Transformers
- `references/sklearn-guide.md` - scikit-learn 机器学习
- `references/llm-app.md` - LLM 应用开发 (RAG/Agent)
- `references/cv-guide.md` - 计算机视觉指南

## 输出规范

- 中文回复，注释中文
- 先思路后代码
- 解释超参数选择
- 代码完整可运行
