# 倪海厦中医AI — 微信中医问诊路由器

当通过 WeChat（微信）收到消息时：

## 中医问诊处理

用户发送症状描述 → 调用后端 TCM API 辨证：

```python
import urllib.request, json

def tcm_diagnose(symptoms):
    """调用倪海厦中医AI进行六经辨证"""
    req = urllib.request.Request(
        "http://127.0.0.1:5197/api/diagnose",
        data=json.dumps({"symptoms": symptoms}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())
```

## 回复格式

收到微信消息后：
1. 如果是中医相关症状描述 → 调用 `tcm_diagnose()` → 返回辨证结果（六经定位/主方/药性分析/LLM增强解读）
2. 如果是图片（舌苔照片） → 下载图片 → 用 vision 分析 → 纳入辨证 → 返回结果
3. 如果是"帮助"或"菜单" → 返回功能说明
4. 其他消息 → 当作普通聊天回复

## 服务依赖

- TCM API: http://127.0.0.1:5197 （Flask，需运行）
- 测试: `cd D:\倪海厦中医AI模型 && python app.py` 或验证 `curl http://127.0.0.1:5197/api/health`
- 微信适配器通过 Hermes gateway 的 weixin platform 收发消息
