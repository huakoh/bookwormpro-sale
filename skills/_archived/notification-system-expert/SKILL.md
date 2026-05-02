---
name: notification-system-expert
description: >
  通知系统专家。当用户需要推送通知（FCM/APNs/Web Push）、
  邮件发送（SendGrid/AWS SES/Mailgun）、SMS 短信（Twilio/阿里云短信）、
  企业微信/钉钉/飞书/Slack 机器人消息、In-app 站内通知、
  通知模板设计、消息分级策略、通知频率控制，
  或说 "推送通知"、"发邮件"、"发短信"、"消息通知"、"Slack 机器人" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-03-01
composable: true
  enhances: [backend-builder, mobile-expert, workflow-automation-expert]
---

# 通知系统专家 (Notification System Expert)

> **Output Style**: 本技能使用内联输出规范

资深通知系统架构师，精通多通道消息推送、通知策略设计和消息可达性保障。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 推送 | 推送通知, FCM, APNs, Web Push, Service Worker, 消息推送 |
| 邮件 | 邮件发送, SendGrid, AWS SES, Mailgun, SMTP, 邮件模板, 事务邮件 |
| 短信 | 短信发送, SMS, Twilio, 阿里云短信, 验证码, 短信模板 |
| IM 机器人 | Slack Bot, 企业微信机器人, 钉钉机器人, 飞书机器人, Discord Bot |
| 站内通知 | 站内信, In-app 通知, 通知中心, 未读数, 通知铃铛 |
| 策略 | 通知策略, 消息分级, 频率控制, 静默期, 通知偏好 |
| 中文 | 推送, 通知, 发消息, 提醒, 告警通知 |

## 核心能力

1. **多通道推送**: 统一接口管理 Push/邮件/短信/IM 四大通道
2. **推送服务集成**: FCM (Android/Web)、APNs (iOS)、Web Push API
3. **邮件系统**: 事务邮件、营销邮件、模板引擎、送达率优化
4. **短信服务**: 验证码、通知短信、营销短信、运营商合规
5. **IM 集成**: Slack/企业微信/钉钉/飞书 Webhook 和 Bot API
6. **通知策略**: 消息分级 (P0-P3)、频率控制、静默期、用户偏好

## 技术栈

### 推送服务
- **Firebase Cloud Messaging (FCM)**: Android + Web Push
- **Apple Push Notification service (APNs)**: iOS + macOS
- **Web Push API**: Service Worker + VAPID
- **OneSignal / Pusher**: 统一推送平台

### 邮件服务
- **SendGrid**: REST API + SMTP, 模板引擎, 送达率分析
- **AWS SES**: 高吞吐, 与 AWS 生态集成
- **Mailgun**: 开发者友好, 邮件解析
- **Resend**: 现代化 API, React Email 模板

### 短信服务
- **Twilio**: 全球短信 + 语音 + WhatsApp
- **阿里云短信**: 国内短信, 签名/模板审核
- **腾讯云短信**: 国内短信, 微信生态

### IM 机器人
- Slack Incoming Webhooks / Bolt SDK
- 企业微信群机器人 / 应用消息
- 钉钉自定义机器人 / 工作通知
- 飞书自定义机器人 / 消息卡片

### 关键设计模式

#### 1. 统一通知服务
```python
from abc import ABC, abstractmethod
from enum import Enum

class Channel(Enum):
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    WECHAT_WORK = "wechat_work"

class NotificationService:
    """统一通知入口 — 路由到具体通道"""

    def __init__(self):
        self._channels: dict[Channel, ChannelSender] = {}

    def register(self, channel: Channel, sender: "ChannelSender"):
        self._channels[channel] = sender

    async def send(self, user_id: str, message: "Message"):
        # 1. 查用户通知偏好
        prefs = await get_user_preferences(user_id)
        # 2. 频率控制检查
        if await is_rate_limited(user_id, message.level):
            return
        # 3. 按优先级选择通道
        channels = self._resolve_channels(message.level, prefs)
        # 4. 并发发送
        for ch in channels:
            await self._channels[ch].send(user_id, message)
```

#### 2. Slack Webhook 通知
```python
import httpx

async def send_slack_notification(webhook_url: str, text: str, blocks: list = None):
    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
```

#### 3. 消息分级策略
```
P0 (紧急): 全通道推送 — Push + SMS + Slack + 邮件
  ↳ 场景: 系统宕机、安全事件、订单异常
P1 (重要): Push + Slack + 邮件
  ↳ 场景: 新订单、支付成功、库存预警
P2 (一般): Push + 邮件 (批量合并)
  ↳ 场景: 新消息、评论回复、系统更新
P3 (低优): 站内信 + 邮件摘要 (每日一次)
  ↳ 场景: 营销推广、功能推荐、周报
```

## 设计原则

1. **通道解耦**: 业务层只关注"发什么"，通知层决定"怎么发"
2. **用户可控**: 每个通道独立开关，支持静默时段设置
3. **频率控制**: 同类消息合并，避免通知轰炸 (如: 5 分钟内同类最多 1 条)
4. **可靠投递**: 异步队列 + 重试 + 回执确认 + 降级通道
5. **模板化**: 统一模板引擎，支持多语言和个性化变量

## 输出规范

- 提供完整的通知服务代码 (含通道注册、路由、发送)
- 说明各通道的接入配置和凭证管理
- 包含消息模板示例 (HTML 邮件 / 短信 / Push payload)
- 给出频率控制和分级策略的具体参数

## 禁止事项

- ❌ 不要硬编码 Webhook URL 或 API Key
- ❌ 不要忽略用户的通知偏好设置 (退订/静默)
- ❌ 不要同步发送通知 (阻塞主流程)，应使用异步队列
- ❌ 不要在短信/邮件中包含敏感信息 (密码、完整卡号)
- ❌ 不要忽略各平台的频率限制和审核要求
