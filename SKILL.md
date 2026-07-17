---
name: ni-haixia-tcm
description: "倪海厦中医AI智能体 — 六经辨证 + 舌诊Vision + 课程知识库检索。通过自然语言对话实现中医面诊，支持语音输入、舌苔拍照分析、经方推荐、课程原文溯源。"
version: 1.0.0
author: Hermes + DAP Developer
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [tcm, chinese-medicine, diagnosis, tongue-analysis, ni-haixia, herb-formula]
    homepage: https://github.com/13925554689/ni-haixia-tcm-ai
    auto_evolve: true
    triggers:
      - "中医问诊"
      - "辨证"
      - "舌诊"
      - "经方"
      - "倪海厦"
      - "伤寒论"
      - "针灸"
      - "中药"
      - "nihaisha"
---

# 倪海厦中医AI智能体 (ni-haixia-tcm)

基于倪海厦经方医学体系的 AI 中医辨证系统。支持六经辨证、舌诊 Vision 分析、课程知识库检索和对话式面诊。

## 前置条件

- Python >= 3.10
- Flask + PIL（`pip install flask pillow`）
- 运行服务：`cd D:\倪海厦中医AI模型 && python app.py`
- 服务地址：`http://127.0.0.1:5197`

## 可用命令

### 辨证诊断
```bash
# 直接调 API
curl -X POST http://127.0.0.1:5197/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{"symptoms": "恶寒发热 头痛项强 无汗 脉浮紧 身体酸痛"}'
```

### 舌苔分析
```bash
# 上传舌苔照片
curl -X POST http://127.0.0.1:5197/api/tongue/upload \
  -F "image=@tongue.jpg"
```

### 知识库检索
```bash
# 搜索课程原文
python cli/search_refs.py "桂枝汤"              # 关键词搜索
python cli/search_refs.py "足三里" --module 针灸  # 按模块过滤
```

### 系统状态
```bash
curl http://127.0.0.1:5197/api/health
curl http://127.0.0.1:5197/api/evolution/status
```

## 知识库结构

```
references/     ← 课程参考文档（46份Markdown）
  ├── shang-han-lun/   ← 伤寒论
  ├── jin-kui/         ← 金匮要略
  ├── nei-jing/        ← 黄帝内经
  ├── ben-cao/         ← 神农本草
  ├── zhen-jiu/        ← 针灸大成
  ├── tian-ji/         ← 天纪
  └── clinical/        ← 临床案例

screenshots/     ← 课程板书截图证据（2,986张 WebP）
  └── 按方名/穴位/课次索引
```

## 核心API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/diagnose` | POST | 症状→六经辨证→经方推荐 |
| `/api/tongue/upload` | POST | 上传舌苔照片→Vision分析 |
| `/api/tongue/analyze` | POST | base64图片+症状→综合辨证 |
| `/api/evidence/:formula` | GET | 方剂课程原文溯源 |
| `/api/evolution/status` | GET | 进化引擎状态 |
| `/api/health` | GET | 系统健康检查 |

## 交互式面诊

打开浏览器访问 http://127.0.0.1:5197 进入对话式面诊界面：
- 🎤 语音输入症状
- 📷 拍照上传舌苔
- 💬 AI 十问法逐步追问
- 📊 六经辨证结果 + 药性分析

## 微信集成

通过 Hermes Gateway 的 Weixin 平台接收微信消息，自动路由到辨证 API。
配置方式：`hermes gateway setup` → 选择 Weixin → 扫码登录 → 配对审批。

## 注意事项

- 本系统为**课程学习与中医理论整理辅助工具**
- 不做个人医疗诊断，不给处方剂量建议
- 所有辨证结果仅供学习参考
- AI 分析（LLM增强 / 舌诊 Vision）依赖第三方 API，结果可能有误
