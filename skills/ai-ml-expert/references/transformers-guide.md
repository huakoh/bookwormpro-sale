# Hugging Face Transformers 指南

## 文本分类

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import Trainer, TrainingArguments
from datasets import Dataset

# 加载模型和分词器
model_name = 'bert-base-chinese'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=num_classes)

# 数据预处理
def preprocess(examples):
    return tokenizer(
        examples['text'],
        truncation=True,
        padding='max_length',
        max_length=512
    )

dataset = Dataset.from_pandas(df)
dataset = dataset.map(preprocess, batched=True)

# 训练参数
training_args = TrainingArguments(
    output_dir='./results',
    num_train_epochs=3,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    warmup_ratio=0.1,
    learning_rate=2e-5,
    weight_decay=0.01,
    logging_steps=100,
    eval_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
    metric_for_best_model='f1',
)

# 评估指标
from sklearn.metrics import accuracy_score, f1_score

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = predictions.argmax(axis=-1)
    return {
        'accuracy': accuracy_score(labels, predictions),
        'f1': f1_score(labels, predictions, average='macro')
    }

# 训练
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    compute_metrics=compute_metrics,
)
trainer.train()
```

## 命名实体识别 (NER)

```python
from transformers import AutoModelForTokenClassification

# 标签映射
label_list = ['O', 'B-PER', 'I-PER', 'B-ORG', 'I-ORG', 'B-LOC', 'I-LOC']
label2id = {l: i for i, l in enumerate(label_list)}
id2label = {i: l for i, l in enumerate(label_list)}

model = AutoModelForTokenClassification.from_pretrained(
    model_name,
    num_labels=len(label_list),
    id2label=id2label,
    label2id=label2id
)

# 数据预处理（处理子词对齐）
def tokenize_and_align_labels(examples):
    tokenized = tokenizer(
        examples['tokens'],
        truncation=True,
        is_split_into_words=True
    )
    
    labels = []
    for i, label in enumerate(examples['ner_tags']):
        word_ids = tokenized.word_ids(batch_index=i)
        label_ids = []
        previous_word_idx = None
        for word_idx in word_ids:
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != previous_word_idx:
                label_ids.append(label[word_idx])
            else:
                label_ids.append(-100)  # 子词
            previous_word_idx = word_idx
        labels.append(label_ids)
    
    tokenized['labels'] = labels
    return tokenized
```

## 文本生成

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = 'Qwen/Qwen2-7B-Instruct'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map='auto'
)

# 生成
messages = [
    {"role": "system", "content": "你是一个有帮助的助手。"},
    {"role": "user", "content": "写一首关于春天的诗"}
]

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors='pt').to(model.device)

outputs = model.generate(
    **inputs,
    max_new_tokens=512,
    temperature=0.7,
    top_p=0.9,
    do_sample=True,
    pad_token_id=tokenizer.eos_token_id
)

response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
```

## Embedding 模型

```python
from sentence_transformers import SentenceTransformer

# 加载模型
model = SentenceTransformer('BAAI/bge-large-zh-v1.5')

# 编码
sentences = ['这是一个句子', '这是另一个句子']
embeddings = model.encode(sentences, normalize_embeddings=True)

# 相似度计算
from sklearn.metrics.pairwise import cosine_similarity
similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
```

## LoRA 微调

```python
from peft import LoraConfig, get_peft_model, TaskType

# LoRA 配置
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=8,                       # LoRA 秩
    lora_alpha=32,             # 缩放因子
    lora_dropout=0.1,
    target_modules=['q_proj', 'v_proj', 'k_proj', 'o_proj'],  # 目标模块
)

# 应用 LoRA
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# 训练后保存
model.save_pretrained('lora_model')

# 加载
from peft import PeftModel
base_model = AutoModelForCausalLM.from_pretrained(base_model_name)
model = PeftModel.from_pretrained(base_model, 'lora_model')
```

## Pipeline 快速推理

```python
from transformers import pipeline

# 文本分类
classifier = pipeline('text-classification', model='bert-base-chinese')
result = classifier('这是一个测试句子')

# NER
ner = pipeline('ner', model='bert-base-chinese-ner', aggregation_strategy='simple')
entities = ner('张三在北京工作')

# 文本生成
generator = pipeline('text-generation', model='gpt2')
text = generator('Once upon a time', max_length=50)

# 问答
qa = pipeline('question-answering', model='bert-large-uncased-whole-word-masking-finetuned-squad')
answer = qa(question='What is AI?', context='AI is artificial intelligence...')

# 零样本分类
classifier = pipeline('zero-shot-classification')
result = classifier('这是一篇体育新闻', candidate_labels=['体育', '科技', '娱乐'])
```

## 量化推理

```python
from transformers import BitsAndBytesConfig

# 4-bit 量化配置
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type='nf4',
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb_config,
    device_map='auto'
)
```
