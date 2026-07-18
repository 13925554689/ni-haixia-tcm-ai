"""舌苔照片分析引擎 — LLM Vision 驱动的舌诊
支持：舌色、舌形、舌苔、舌下络脉、综合辨证建议
"""
import base64, json, os, urllib.request, urllib.error
from io import BytesIO

# ─── Vision API 配置（延迟加载，运行时读取环境变量）───


def _get_vision_config():
    """延迟读取 Vision API 配置（确保 dotenv 已加载）"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        _hermes_env = os.path.join(os.path.expanduser("~"), ".hermes", ".env")
        if os.path.exists(_hermes_env):
            load_dotenv(_hermes_env)
    except ImportError:
        pass

    # 0. 智谱 GLM-4V — 直连，免费额度
    glm_key = os.getenv("GLM_API_KEY", "")
    if glm_key:
        return glm_key, "https://open.bigmodel.cn/api/paas/v4", "glm-4v"

    # 1. AIFAST — 中转站，gemini-2.5-flash（备用）
    aifast_key = os.getenv("AIFAST_API_KEY", "")
    if aifast_key:
        return aifast_key, "https://www.aifast.club/v1", "gemini-2.5-flash"
    or_key = os.getenv("OPENROUTER_API_KEY", "")
    if not or_key:
        # 兼容：ANTHROPIC_API_KEY 可能存了 OpenRouter key
        anthro_key = os.getenv("ANTHROPIC_API_KEY", "")
        if anthro_key and anthro_key.startswith("sk-or"):
            or_key = anthro_key
    if or_key:
        return or_key, "https://openrouter.ai/api/v1", "google/gemini-2.5-flash"

    # 2. Anthropic 直连
    anthro_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthro_key and anthro_key.startswith("sk-ant"):
        return anthro_key, "https://api.anthropic.com", "claude-sonnet-4-20250514"

    # 4. DeepSeek（无 vision，降级）
    ds_key = os.getenv("DEEPSEEK_API_KEY", "")
    if ds_key:
        return ds_key, "https://api.deepseek.com", "deepseek-chat"

    return "", "", ""

TONGUE_PROMPT = """你是倪海厦中医舌诊专家。请分析这张舌苔照片，按以下格式输出（纯JSON，不要markdown）：

{
  "舌色": "淡白/淡红/红/绛红/紫暗/青紫中的一种",
  "舌形": "胖大/瘦薄/齿痕/裂纹/芒刺/正常 任选一到多个",
  "舌苔": "薄白/白厚/黄薄/黄厚/黄腻/白腻/灰黑/剥落/无苔/地图舌 中的一种",
  "舌苔厚度": "薄/厚",
  "舌苔润燥": "润/燥/滑/腻",
  "舌下络脉": "正常/青紫怒张/淡细 中的一种（如不可见填"无法判断"）",
  "中医辨证": "根据舌象得出的中医证型判断（如：脾胃湿热、气血两虚、肝郁气滞等）",
  "倪师解读": "用倪海厦的口语风格，一句话总结这个舌象说明什么问题",
  "建议关注": "建议用户补充哪方面症状（如：是否口苦、是否有胃胀、睡眠如何等，列2-3条）",
  "可信度": "高/中/低（照片清晰度、光线等因素影响）"
}

只输出JSON，不要任何其他文字。"""


def _call_vision_api(image_b64: str) -> dict:
    """调用 Vision API"""
    api_key, base_url, model = _get_vision_config()
    if not api_key:
        return {"error": "未配置 Vision API Key（需 GLM_API_KEY/DEEPSEEK_API_KEY）", "_fallback": True}

    # 构建 OpenAI-compatible vision 请求
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {"type": "text", "text": TONGUE_PROMPT},
            ]
        }],
        "temperature": 0.3,
        "max_tokens": 1500,
    }

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"]

            # 尝试解析 JSON（可能夹杂了 markdown 包裹）
            content = content.strip()
            if content.startswith("```"):
                # 移除 markdown 代码块
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

            parsed = json.loads(content)
            parsed["_vision_model"] = model
            return parsed

    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError,
            KeyError, TimeoutError) as e:
        return {"error": f"舌诊API调用失败: {e}", "_fallback": True}


def analyze_tongue_from_bytes(image_bytes: bytes) -> dict:
    """从图片字节流分析舌苔"""
    api_key, _, _ = _get_vision_config()
    if not api_key:
        return {
            "舌色": "无法判断",
            "舌形": "无法判断",
            "舌苔": "无法判断",
            "中医辨证": "未配置 Vision API Key（GLM_API_KEY），请设置环境变量后重试",
            "倪师解读": "舌诊功能需要配置视觉模型API",
            "可信度": "低",
            "_fallback": True,
        }

    # 压缩大图
    try:
        from PIL import Image
        img = Image.open(BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        # 压缩到最长边800px
        max_dim = 800
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=75)
        image_bytes = buf.getvalue()
    except ImportError:
        pass  # PIL 不可用时直接用原图
    except Exception as e:
        import logging
        logging.getLogger("tongue_analysis").warning(f"图片压缩失败(非致命): {e}")

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    return _call_vision_api(image_b64)


def analyze_tongue_from_base64(image_b64: str) -> dict:
    """从 base64 编码字符串分析舌苔"""
    api_key, _, _ = _get_vision_config()
    if not api_key:
        return {
            "舌色": "无法判断",
            "舌形": "无法判断",
            "舌苔": "无法判断",
            "中医辨证": "未配置 Vision API Key",
            "倪师解读": "舌诊功能需要配置视觉模型API",
            "可信度": "低",
            "_fallback": True,
        }
    return _call_vision_api(image_b64)


def merge_tongue_to_symptoms(tongue_result: dict) -> str:
    """将舌诊结果转换为症状描述，可合并到辨证输入"""
    parts = []
    if tongue_result.get("舌色"):
        parts.append(f"舌色{tongue_result['舌色']}")
    if tongue_result.get("舌苔"):
        parts.append(f"舌苔{tongue_result['舌苔']}")
    if tongue_result.get("舌形") and tongue_result["舌形"] != "正常":
        parts.append(f"舌形{tongue_result['舌形']}")
    if tongue_result.get("中医辨证"):
        parts.append(f"舌诊提示：{tongue_result['中医辨证']}")
    return "；".join(parts) if parts else ""
