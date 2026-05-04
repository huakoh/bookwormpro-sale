---
name: video-agent-expert
title: AI Video Editing Agent
description: >
  AI-powered video editing agent with Plan-Tool-Verify architecture.
  Natural language video editing, FFmpeg command generation via structured DSL,
  video transcoding, concatenation, subtitle burning, frame extraction,
  DaVinci Resolve integration, and video Agent architecture design.
  Use when: "视频编辑", "剪辑", "视频Agent", "FFmpeg", "视频处理",
  "转码", "video edit", "video agent", "cut video", "transcode".
version: 0.1.0
author: BookwormPRO
license: MIT
platforms: [windows, linux, macos]
dependencies: [ffmpeg, ffprobe]
prerequisites:
  commands: [ffmpeg, ffprobe]
metadata:
  bookworm:
    tags: [video, editing, ffmpeg, transcoding, dsl, agent, media, audio, subtitle, davinci]
    category: media
    related_skills: [youtube-content, audiocraft, creative-ideation, manim-video]
    requires_toolsets: [terminal, files]
---

# Video Agent Expert

AI 驱动的视频编辑 Agent，基�� Plan-Tool-Verify 架构，经过 7 轮 × 6 维 × 42 次专家评审。

## Core Architecture

```
User Request → Planner (LLM) → DSL v1.0 → Validator → FFmpeg Renderer → Verify → Output
```

**Key Design Decision**: LLM outputs structured JSON DSL (not raw FFmpeg commands).
This makes the pipeline auditable, rollbackable, and cacheable.

## Capabilities

### Video Editing
- Natural language to video edit commands
- Multi-segment concatenation with proper PTS handling
- Trim, crop, scale, speed change, fade transitions
- Subtitle burning and text overlays
- Audio mixing, muting, BGM replacement

### Video Processing
- Format conversion (MP4/WebM/MOV)
- Resolution scaling with codec optimization
- VFR → CFR normalization
- HDR/Dolby Vision detection and handling
- Audio sample rate normalization (48kHz)

### Agent Architecture
- DSL v1.0 with Zod strict schema validation
- Semantic validation (in < out, speed > 0.01, timeline overlap detection)
- FFmpeg via `execFile` (never shell) with path whitelist
- Tiered frame extraction (≤30min: adaptive, >30min: scene-detect + 128 cap)
- Verify layer: duration ±1s, resolution match, hash dedup, MAX_RETRY=3
- Outbox pattern with exponential backoff (100/500/2000ms)

## Security Baseline (6 Layers)

1. **Input**: AbortController + ffprobe validation + content moderation (fail-close)
2. **Planner**: DSL schema strict + semantic validator
3. **Auditor**: Cross-model black-box audit (GPT-4o Planner + Claude Auditor)
4. **Renderer**: execFile + restricted FFmpeg build + sandbox (ulimit 8GB, timeout 30min)
5. **Outbox**: PostgreSQL + isolated connection pool + credential redact
6. **Logs**: OpenTelemetry trace-context + regex redact sensitive fields

## Project Assets

- **Source Code**: `D:\projects\video-agent\` (TypeScript, 12 modules)
- **Design Doc**: `D:\projects\video-agent\DESIGN.md` (v4.3 final, 7-round reviewed)
- **Tests**: 8 files, 71 cases, 100% green
- **Local Bookworm Skill**: `~/.claude/skills/video-agent-expert/SKILL.md`

## Workflow

1. **Receive** user request (natural language video editing instruction)
2. **Probe** input video via ffprobe (validate duration, resolution, VFR, HDR)
3. **Plan** via LLM → output DSL v1.0 JSON
4. **Validate** DSL against Zod schema + semantic rules
5. **Audit** via independent LLM (black-box, cross-model)
6. **Render** via FFmpegRenderer (execFile, path whitelist, settb=AVTB)
7. **Verify** output (duration, resolution, hash dedup)
8. **Retry** if failed (max 3, with failure reason injection)
9. **Deliver** to outbox → storage → user

## Error Codes

| Range | Layer | Examples |
|-------|-------|---------|
| E1xxx | Input | E1003_HDR_UNSUPPORTED, E1004_NO_TIMEBASE |
| E2xxx | Planner | E2002_SCHEMA_INVALID, E2005_INTENT_BLOCKED |
| E3xxx | Renderer | E3002_TIMEOUT, E3004_DISK_FULL |
| E4xxx | Verify | E4002_MAX_RETRY_EXCEEDED |
| E5xxx | Outbox | E5001_OUTBOX_FAILED |
| E6xxx | Cost | E6001_TOKEN_BUDGET_EXCEEDED |

## Pricing Tiers

| Resolution | Max Budget |
|-----------|-----------|
| ≤ 2MP (1080p) | $20 |
| 2-8MP (2K-4K) | $40 |
| 8-24MP (4K-6K) | $60 |
| > 24MP (8K) | $120 |
| > 48MP | Rejected (E6002) |

## Review History

7 rounds × 6 dimensions = 42 expert reviews. Core architecture: **zero overturns**.

| Metric | v1.0 | v4.3 (final) |
|--------|------|-------------|
| Architecture | 70 | 85 |
| AI Engineering | 68 | 87 |
| Security (lower=safer) | 62 | 28 |
| Logic | 52 | 76 |
| Product | 65 | 87 |
| Delivery | 58 | 92 |

## Usage Examples

```
User: 把这个视频的前30秒剪掉，加个淡入效果
Agent: [Probe] → [Plan DSL: trim 30s + fade_in] ��� [Validate] → [Render] → [Verify] → Done

User: Convert this MOV to MP4, keep 1080p, add subtitle from srt file
Agent: [Probe] → [Plan DSL: transcode + subtitle] → [Validate] → [Render] → [Verify] → Done

User: 把3个视频拼接起来，每段之间加1秒转场
Agent: [Probe ×3] → [Plan DSL: concat + transitions] → [Validate] → [Render] → [Verify] → Done
```
