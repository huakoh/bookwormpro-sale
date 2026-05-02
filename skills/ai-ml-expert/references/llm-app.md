# LLM 应用开发指南 (RAG/Agent)

## RAG 系统架构

```
用户查询 → 查询改写 → 向量检索 → 重排序 → LLM生成 → 回答
                         ↓
                    向量数据库
                         ↑
               文档切分 → Embedding
```

## 文档处理

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader, TextLoader

# 加载文档
loader = PyPDFLoader('document.pdf')
documents = loader.load()

# 文档切分
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=['\n\n', '\n', '。', '！', '？', '，', ' ']
)
chunks = splitter.split_documents(documents)
```

## 向量数据库

### Chroma

```python
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma

# Embedding 模型
embeddings = HuggingFaceEmbeddings(
    model_name='BAAI/bge-large-zh-v1.5',
    model_kwargs={'device': 'cuda'},
    encode_kwargs={'normalize_embeddings': True}
)

# 创建向量库
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory='./chroma_db'
)

# 检索
retriever = vectorstore.as_retriever(
    search_type='similarity',  # mmr
    search_kwargs={'k': 5}
)
docs = retriever.get_relevant_documents('查询内容')
```

### FAISS

```python
from langchain.vectorstores import FAISS

vectorstore = FAISS.from_documents(chunks, embeddings)
vectorstore.save_local('faiss_index')

# 加载
vectorstore = FAISS.load_local('faiss_index', embeddings)
```

## RAG 实现

### 基础 RAG

```python
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

llm = OpenAI(temperature=0)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type='stuff',  # map_reduce, refine
    retriever=retriever,
    return_source_documents=True
)

result = qa_chain({'query': '问题'})
print(result['result'])
print(result['source_documents'])
```

### 自定义 Prompt

```python
from langchain.prompts import PromptTemplate

template = """基于以下上下文回答问题。如果无法从上下文中找到答案，请说"我不知道"。

上下文:
{context}

问题: {question}

回答:"""

prompt = PromptTemplate(
    template=template,
    input_variables=['context', 'question']
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    chain_type_kwargs={'prompt': prompt}
)
```

### 对话历史

```python
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

memory = ConversationBufferMemory(
    memory_key='chat_history',
    return_messages=True
)

qa_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=memory
)

result = qa_chain({'question': '问题'})
```

## Agent 开发

### ReAct Agent

```python
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.tools import DuckDuckGoSearchRun

# 定义工具
search = DuckDuckGoSearchRun()

tools = [
    Tool(
        name='Search',
        func=search.run,
        description='用于搜索互联网上的信息'
    ),
    Tool(
        name='Calculator',
        func=lambda x: eval(x),
        description='用于数学计算'
    )
]

# 创建 Agent
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

result = agent.run('北京今天的天气怎么样？')
```

### 自定义工具

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(description='搜索查询')

class CustomSearchTool(BaseTool):
    name = 'custom_search'
    description = '自定义搜索工具'
    args_schema = SearchInput
    
    def _run(self, query: str) -> str:
        # 实现搜索逻辑
        return f'搜索结果: {query}'
    
    async def _arun(self, query: str) -> str:
        return self._run(query)
```

## Prompt Engineering

### 结构化输出

```python
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel

class ExtractedInfo(BaseModel):
    name: str
    age: int
    occupation: str

parser = PydanticOutputParser(pydantic_object=ExtractedInfo)

prompt = PromptTemplate(
    template='从以下文本中提取信息:\n{text}\n\n{format_instructions}',
    input_variables=['text'],
    partial_variables={'format_instructions': parser.get_format_instructions()}
)

chain = prompt | llm | parser
result = chain.invoke({'text': '张三，30岁，软件工程师'})
```

### Few-shot Learning

```python
from langchain.prompts import FewShotPromptTemplate

examples = [
    {'input': '今天天气真好', 'output': '正面'},
    {'input': '服务太差了', 'output': '负面'},
    {'input': '还行吧', 'output': '中性'},
]

example_prompt = PromptTemplate(
    input_variables=['input', 'output'],
    template='输入: {input}\n输出: {output}'
)

few_shot_prompt = FewShotPromptTemplate(
    examples=examples,
    example_prompt=example_prompt,
    prefix='对以下文本进行情感分类:\n',
    suffix='\n输入: {input}\n输出:',
    input_variables=['input']
)
```

## vLLM 部署

```python
from vllm import LLM, SamplingParams

# 加载模型
llm = LLM(
    model='Qwen/Qwen2-7B-Instruct',
    tensor_parallel_size=1,
    dtype='float16'
)

# 采样参数
sampling_params = SamplingParams(
    temperature=0.7,
    top_p=0.9,
    max_tokens=512
)

# 批量推理
prompts = ['问题1', '问题2']
outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    print(output.outputs[0].text)
```

## API 服务

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Query(BaseModel):
    question: str

@app.post('/chat')
async def chat(query: Query):
    result = qa_chain({'query': query.question})
    return {'answer': result['result']}

# 运行: uvicorn main:app --host 0.0.0.0 --port 8000
```
