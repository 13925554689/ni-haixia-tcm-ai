"""倪海厦中医AI智能体 — Flask Web应用
ponytail: 3个API端点 + 1个Web页面，完全自包含
"""
import os
import json
import time
from flask import Flask, request, jsonify, render_template

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from engine.diagnosis_engine import diagnose, DIAGNOSIS_TEMPLATE
from engine.knowledge_base import HEALTH_BASELINE, DIAGNOSIS_FRAMEWORK
from engine.evolution_engine import (
    record_case, list_cases, search_cases, get_evolution_status, get_checklist, add_checklist_item
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html",
                           health_baseline=HEALTH_BASELINE,
                           diagnosis_template=DIAGNOSIS_TEMPLATE,
                           channel_names=list(DIAGNOSIS_FRAMEWORK.keys()))


@app.route("/api/diagnose", methods=["POST"])
def api_diagnose():
    """症状文本 → 六经辨证 → 经方 → 药性分析"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请提供请求数据"}), 400

    symptoms = data.get("symptoms", "")
    if not symptoms or len(symptoms.strip()) < 3:
        return jsonify({"error": "请描述您的症状（至少3个字）"}), 400

    result = diagnose(symptoms.strip())

    # 如果置信度够高且LLM可用，增强分析
    if result.get("置信度") in ("高", "中") and LLM_API_KEY:
        try:
            enhanced = _llm_enhance(symptoms, result)
            result["llm_enhanced"] = enhanced
        except Exception:
            result["llm_enhanced"] = "LLM增强分析不可用"

    return jsonify({"success": True, **result})


@app.route("/api/diagnose/record", methods=["POST"])
def api_record_case():
    """记录诊疗案例到进化引擎"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请提供请求数据"}), 400

    symptoms = data.get("symptoms", "")
    diagnosis = data.get("diagnosis", {})
    efficacy = data.get("efficacy", "")

    if not symptoms or not diagnosis:
        return jsonify({"error": "缺少 symptoms 或 diagnosis"}), 400

    case_id = record_case(symptoms, diagnosis, efficacy)
    status = get_evolution_status()

    return jsonify({
        "success": True,
        "case_id": case_id,
        "evolution_status": status,
    })


@app.route("/api/evolution/status")
def api_evolution_status():
    return jsonify({"success": True, **get_evolution_status()})


@app.route("/api/evolution/cases")
def api_list_cases():
    limit = request.args.get("limit", 50, type=int)
    q = request.args.get("q", "")
    if q:
        cases = search_cases(q)
    else:
        cases = list_cases(limit)
    return jsonify({"success": True, "cases": cases, "count": len(cases)})


@app.route("/api/evolution/checklist")
def api_get_checklist():
    return jsonify({"success": True, "checklist": get_checklist()})


@app.route("/api/evolution/checklist/add", methods=["POST"])
def api_add_checklist():
    data = request.get_json()
    item = data.get("item", "")
    if not item:
        return jsonify({"error": "缺少item"}), 400
    add_checklist_item(item)
    return jsonify({"success": True, "checklist": get_checklist()})


@app.route("/api/health")
def api_health():
    status = get_evolution_status()
    return jsonify({
        "status": "ok",
        "llm_configured": bool(LLM_API_KEY),
        "cases": status["总案例数"],
        "channels": len(DIAGNOSIS_FRAMEWORK),
        "formulas": len(DIAGNOSIS_FRAMEWORK),
    })


# ───────── LLM增强 ─────────

def _llm_enhance(symptoms: str, diagnosis: dict) -> str:
    import urllib.request
    import urllib.error
    from config import LLM_PROVIDER

    prompt = f"""你是倪海厦中医传承AI。请根据以下辨证结果，用倪海厦的口语风格给出诊疗思路、用药解读和熬药提醒。

患者症状：{symptoms}

辨证结果：
- 六经定位：{diagnosis.get('六经定位')}
- 病机：{diagnosis.get('病机')}
- 主方：{diagnosis.get('主方')}
- 药性分析：{json.dumps(diagnosis.get('药性分析', []), ensure_ascii=False)[:500]}

请输出：
1. 为什么选这个方子（经方思路）
2. 每味药的作用
3. 熬药详细步骤
4. 服药后的反应（什么算好转，什么需警惕）
5. 饮食起居禁忌

用自然口语，像倪海厦在课堂上讲的一样。"""

    if LLM_PROVIDER == "anthropic":
        data = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": LLM_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    elif LLM_PROVIDER == "openrouter":
        data = json.dumps({
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5, "max_tokens": 1500
        }).encode()
        url = f"{LLM_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:5197",
            "X-Title": "倪海厦中医AI",
        }
    else:
        # DeepSeek / GLM / OpenAI-compatible
        data = json.dumps({
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5, "max_tokens": 1500
        }).encode()
        url = f"{LLM_BASE_URL}/chat/completions"
        headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
            if LLM_PROVIDER == "anthropic":
                return result["content"][0]["text"]
            return result["choices"][0]["message"]["content"]
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError):
        return "LLM增强不可用"


if __name__ == "__main__":
    print("\n🏥 倪海厦中医AI智能体启动中...")
    status = get_evolution_status()
    print(f"🌐 http://127.0.0.1:5197")
    print(f"📊 已学习案例: {status['总案例数']}")
    print(f"📚 六经辨证框架: {len(DIAGNOSIS_FRAMEWORK)} 经")
    print(f"💊 经方库: {len(DIAGNOSIS_FRAMEWORK)} 经覆盖")
    print(f"🤖 LLM: {'已配置' if LLM_API_KEY else '⚠ 未配置(规则引擎模式)'}")
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="127.0.0.1", port=5197)
