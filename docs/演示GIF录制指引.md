# 演示 GIF 录制指引

## 推荐流程（30 秒）

使用 ScreenToGif (Windows) 或 Kap (Mac) 录制以下流程：

### 场景：从下载到首次使用

```
[0-3s]   解压 bookwormpro-sale.zip，打开文件夹
[3-6s]   双击 install.bat → 终端打开，彩色 Banner 出现
[6-12s]  选择 [1] 新手模式 → 填入 DeepSeek API Key → 回车
[12-20s] 进度条动画（技能包复制中 ████████░░ 75%）
[20-24s] 安装完成 ✅ → 显示"下一步"
[24-28s] 打开 AI 助手，输入 bookworm自检
[28-30s] 绿色体检报告出现 🎉
```

### 工具推荐

| 平台 | 工具 | 下载 |
|------|------|------|
| Windows | ScreenToGif | https://www.screentogif.com |
| Mac | Kap | https://getkap.co |
| Linux | Peek | `sudo apt install peek` |

### 录制设置

- 分辨率：1280×720（过高会导致文件太大）
- 帧率：15 FPS（GIF 不需要 30fps）
- 格式：GIF（也可以录 MP4 再转 GIF）
- 大小目标：< 5MB（方便在 README 中加载）

### 存放到

```
docs/demo.gif
```

然后在 README.md 顶部引用：

```markdown
![BookwormPRO 安装演示](docs/demo.gif)
```

## 快速替代方案

如果不能录 GIF，可以用终端录屏生成 ascii 字符画演示：

```bash
# 用 asciinema 录制终端会话
pip install asciinema
asciinema rec docs/demo.cast

# 上传到 asciinema.org 生成可嵌入的播放器
asciinema upload docs/demo.cast
```
