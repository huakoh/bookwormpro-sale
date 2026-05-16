---
name: video-agent-expert
description: >
  视频编辑Agent专家。当用户需要AI视频剪辑、自然语言视频编辑、
  FFmpeg MCP 调用、视频转码、视频拼接、字幕烧录、
  视频 Agent 架构设计、DSL 时间线编排，
  或说 "视频编辑"、"剪辑"、"视频Agent"、"FFmpeg"、"视频处理"、"转码" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, PowerShell, Agent, WebSearch, WebFetch
maturity: stable
last-reviewed: 2026-05-12
requires-bins: [ffmpeg, ffprobe]
requires-bins-note: 视频处理场景才需要，非视频项目可忽略
---

# 视频编辑 Agent 专家 (Video Agent Expert)

> **Output Style**: 本技能使用内联输出规范

AI 驱动的视频编辑 Agent 架构专家，专注于自然语言指令到 FFmpeg 管线的完整转换链路，覆盖 DSL 时间线设计、异源审计与安全边界控制。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 视频编辑 | 视频编辑, 视频剪辑, 剪片, 自然语言剪辑, AI 剪辑 |
| 工具 | FFmpeg, Remotion, ffprobe |
| Agent | 视频 Agent, 视频 Agent 架构, Plan-Tool-Verify |
| 管线 | DSL 时间线, concat 视频, 视频拼接, 视频合并 |
| 处理 | 视频转码, 转码, 帧提取, 截帧, 字幕烧录 |
| 识别 | ASR, 语音识别, 字幕生成, Whisper |

## 核心能力

### Plan-Tool-Verify 架构

```
用户自然语言指令
     ↓
  Planner (LLM)         → 解析意图，生成 DSL v1.0 时间线 JSON
     ↓
  Renderer (FFmpeg)     → execFile 执行，禁止 shell: true
     ↓
  Verifier (ffprobe)    → 时长/分辨率/帧率校验，误差 ±0.5s
     ↓
  Outbox               → 安全路径白名单输出
```

### DSL v1.0 时间线规范

```typescript
interface Timeline {
  version: "1.0";
  inputs: InputClip[];       // 源文件，路径白名单校验
  operations: Operation[];   // concat | trim | overlay | subtitle | transcode
  output: OutputSpec;        // 目标路径、编码参数
}

interface Operation {
  type: "concat" | "trim" | "overlay" | "subtitle" | "transcode";
  params: Record<string, unknown>;  // Zod schema 严格校验
}
```

### FFmpeg 安全调用模式

```typescript
import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);

// 安全: execFile 禁止 shell injection，参数数组化
async function runFFmpeg(args: string[]): Promise<void> {
  // 路径白名单校验
  validatePaths(args, ALLOWED_DIRS);
  const { stdout, stderr } = await execFileAsync("ffmpeg", args, {
    shell: false,          // 关键: 禁止 shell 展开
    timeout: 300_000,      // 5 分钟超时
    maxBuffer: 10 * 1024 * 1024,
  });
}
```

### 异源审计 (Multi-Source Audit)

同一操作由三路独立路径验证：
1. DSL Planner 生成预期元数据
2. FFmpeg Renderer 实际输出
3. ffprobe Verifier 回读校验

三路结果 diff 超阈值时 fail-close，拒绝输出。

## 项目资产

| 资产 | 路径 |
|------|------|
| 主项目 | `D:\projects\video-agent\` |
| DSL schema | `D:\projects\video-agent\src\dsl\schema.ts` |
| DSL types | `D:\projects\video-agent\src\dsl\types.ts` |
| DSL validator | `D:\projects\video-agent\src\dsl\validator.ts` |
| FFmpeg renderer | `D:\projects\video-agent\src\renderer\ffmpeg.ts` |
| GPU 检测 | `D:\projects\video-agent\src\renderer\gpu-detect.ts` |
| Verifier | `D:\projects\video-agent\src\verify\verifier.ts` |
| Upload handler | `D:\projects\video-agent\src\upload\handler.ts` |
| ASR (Whisper) | `D:\projects\video-agent\src\asr\whisper.ts` |
| Queue (BullMQ) | `D:\projects\video-agent\src\queue\` (queue/worker/pipeline/outbox) |
| 路径校验 | `D:\projects\video-agent\src\utils\path.ts` |
| 测试套件 | `D:\projects\video-agent\tests\` (13 文件) |

## 工作流程

```
入口 (HTTP / CLI / MQ)
  └→ Planner (LLM 意图解析 + DSL 生成)
       └→ DSL Validator (Zod schema 校验)
            └→ Renderer (FFmpeg execFile 调用)
                 └→ Verifier (ffprobe 结果核查)
                      └→ Outbox (安全路径输出 + 事件发布)
```

### 关键节点说明

- **Planner**: 调用 LLM 将自然语言转为 DSL JSON，失败时 fail-close（不猜测操作）
- **Renderer**: 每条 Operation 独立 execFile 调用，中间结果写临时目录
- **Verifier**: ffprobe 读取输出文件，校验时长/分辨率/帧率与预期 ±0.5s/±1px/±0.01fps
- **Outbox**: 仅允许写入白名单目录，最终文件通过 rename 原子移动

## 安全规范

| 规则 | 说明 |
|------|------|
| execFile 禁 shell | `shell: false` 强制，禁止 `child_process.exec` |
| 路径白名单 | 输入/输出路径必须在 `ALLOWED_DIRS` 内，拒绝 `..` 穿越 |
| 参数注入防护 | 用户输入经 Zod 校验后才进入 FFmpeg 参数数组 |
| fail-close | Verifier 失败时删除输出文件，不返回未经验证结果 |
| 超时保护 | FFmpeg 单任务 5 分钟超时，BullMQ job 10 分钟全局超时 |
| 临时文件清理 | try-finally 保证临时目录必删 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | TypeScript 5.x 严格模式 |
| 队列 | BullMQ + Redis |
| 数据库 | PostgreSQL (任务元数据 + 审计日志) |
| Schema 校验 | Zod v3 |
| 测试 | Vitest + 真实 FFmpeg 集成测试 |
| LLM 调用 | Anthropic SDK (claude-sonnet-4-6 默认) |
| 视频工具 | FFmpeg 6.x + ffprobe |
| ASR | Whisper.cpp (本地) / Whisper API (云端) |

## 常用 FFmpeg 操作速查

### 视频拼接 (concat)
```bash
# filter_complex 拼接法（推荐，支持不同编码）
ffmpeg -i input1.mp4 -i input2.mp4 \
  -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" output.mp4
```

### 片段裁剪 (trim)
```bash
# 精确裁剪，使用 -ss 在 -i 前避免关键帧偏移
ffmpeg -ss 00:01:00 -t 00:00:30 -i input.mp4 \
  -c:v libx264 -c:a aac output.mp4
```

### 字幕烧录 (subtitle burn-in)
```bash
ffmpeg -i input.mp4 \
  -vf "subtitles=subtitle.srt:force_style='FontName=Noto Sans CJK SC,FontSize=24'" \
  -c:v libx264 output.mp4
```

### 转码 (transcode)
```bash
# H.264 + AAC，适合网络播放
ffmpeg -i input.mp4 \
  -c:v libx264 -preset slow -crf 22 \
  -c:a aac -b:a 128k \
  -movflags +faststart output.mp4
```

### ffprobe 元数据读取
```bash
ffprobe -v quiet -print_format json -show_streams input.mp4
```

## 评审记录摘要

| 维度 | 说明 |
|------|------|
| 评审轮次 | 7 轮 × 6 维度 = 42 次审查节点 |
| 安全得分 | 18/100 (初版) → 修复后 72/100 (execFile 替换 exec 后) |
| 交付得分 | 92/100 (DSL v1.0 + Verifier 全链路通过后) |
| 关键 Blocker | exec shell injection (P0), 路径穿越 (P0), 超时缺失 (P1) |
| 已修复 | 全部 P0 Blocker 已关闭 |

## 输出规范

- 中文回复，代码注释中文，变量名英文
- 优先给 TypeScript 实现，兼顾 Bash 脚本
- 所有 FFmpeg 参数显式声明，禁止隐式默认值依赖
- 路径处理使用 `path.resolve` + 白名单校验，绝不拼接字符串
- 涉及 shell 命令时必须说明 injection 防护方案
