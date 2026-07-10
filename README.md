[![Banners](docs/images/banner.png)](https://github.com/dairoot/xiaozhi-webrtc)

[English](README.en.md) | 简体中文

# XiaoZhi WebRTC

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

一个基于 **WebRTC** 的 AI 实时音视频互动项目，致力于打造你的专属、贴心且充满温度的情感伴侣。

---

## ✨ 功能特性
- **XiaoZhi 核心能力**：融合视觉多模态理解、智能问答与 MCP 控制，带来更强大的交互与处理能力。
- **实时音视频沟通**：超低延迟与高清体验，让交流顺畅自然。
- **Live2D 动态呈现**：拟真互动与沉浸式表现，提升亲和力与互动感。
---

## 🎯  在线体验

[https://xiaozhi.dairoot.cn](https://xiaozhi.dairoot.cn)

> 💡 **提示**: 由于部署在海外服务器，访问会稍微卡顿（仅体验）

https://github.com/user-attachments/assets/d985aacc-b07d-4874-a10a-c2139bd6c4bf

---

## 🚀 快速开始

```bash
# 克隆项目
git clone https://github.com/dairoot/xiaozhi-webrtc.git
cd xiaozhi-webrtc
```

#### 方法一：使用 uv（推荐）

```bash
# 安装 uv
pip install uv

# 安装项目依赖
uv sync

# 运行项目
uv run main.py
```

#### 方法二：使用 Docker

```bash
# 使用 Docker Compose 运行
docker compose up
```

#### 方法三：传统 pip 安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .

# 运行项目
python main.py
```
---

## ⚙️ 部署要求

### 端口要求

WebRTC 需要以下端口用于实时音视频通信：

| 端口 | 协议 | 用途 |
|------|------|------|
| 3478 | UDP | STUN 服务 |
| 49152–65535 | UDP | WebRTC 媒体流端口（默认） |

**注意：** 确保防火墙允许这些端口的通信，特别是在生产环境中部署时。


### HTTPS 要求

**线上环境必须使用 HTTPS**：WebRTC 需要访问摄像头和麦克风，现代浏览器出于安全考虑只允许在 HTTPS 环境下使用这些功能。

## 📖 使用说明

1. **启动服务**: 运行项目后，服务将在 `http://localhost:51000` 或者 `https://yourdomain.com`  启动
2. **访问页面**: 在浏览器中打开上述地址
3. **授权权限**: 允许浏览器访问摄像头和麦克风
4. **开始通信**: 点击开始按钮建立 WebRTC 连接

**注意**: 生产环境必须使用 HTTPS，否则 WebRTC 功能将无法正常工作。

---
## 🫡 致敬
- 虾哥 [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) 项目
# esgtest
