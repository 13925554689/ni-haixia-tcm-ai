"""倪海厦中医AI — 自我进化引擎
ponytail: 案例记录→模式提取→避坑更新→知识累积，闭环自进化
"""
import json
import os
import time
from datetime import datetime
from config import CASES_DIR, CHECKLIST_PATH, PATTERNS_PATH


def record_case(symptoms: str, diagnosis: dict, efficacy: str = "") -> str:
    """记录一次诊疗案例到持久化存储"""
    case_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    case = {
        "id": case_id,
        "timestamp": datetime.now().isoformat(),
        "symptoms": symptoms,
        "六经定位": diagnosis.get("六经定位", ""),
        "主方": diagnosis.get("主方", ""),
        "diagnosis": diagnosis.get("diagnosis", ""),
        "置信度": diagnosis.get("置信度", ""),
        "病机": diagnosis.get("病机", ""),
        "疗效反馈": efficacy,
        "方剂详情": diagnosis.get("方剂详情", {}),
    }
    path = os.path.join(CASES_DIR, f"{case_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)

    # 有疗效反馈时，触发模式提取
    if efficacy:
        _update_patterns(case)

    return case_id


def list_cases(limit: int = 50) -> list:
    """列出所有案例"""
    cases = []
    for fname in sorted(os.listdir(CASES_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CASES_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                cases.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return cases[:limit]


def search_cases(query: str) -> list:
    """搜索案例"""
    results = []
    for case in list_cases(500):
        text = case.get("symptoms", "") + case.get("diagnosis", "") + case.get("主方", "")
        if query in text:
            results.append(case)
    return results[:20]


def get_evolution_status() -> dict:
    """获取自进化状态摘要"""
    cases = list_cases(500)
    total = len(cases)
    with_efficacy = [c for c in cases if c.get("疗效反馈")]
    patterns = _load_patterns()

    formula_stats = patterns.get("formula_stats", {})
    top_formulas = sorted(formula_stats.items(), key=lambda x: -x[1])[:10]

    efficacy_stats = patterns.get("effectiveness", {})
    effective = efficacy_stats.get("有效", 0) + efficacy_stats.get("显效", 0)
    ineffective = efficacy_stats.get("无效", 0) + efficacy_stats.get("恶化", 0)

    checklist = _load_checklist()

    return {
        "总案例数": total,
        "有疗效反馈": len(with_efficacy),
        "有效率": f"{effective}/{effective+ineffective}" if (effective + ineffective) > 0 else "暂无数据",
        "高频方剂": top_formulas,
        "核心症状群": sorted(patterns.get("symptom_clusters", {}).items(), key=lambda x: -x[1])[:10],
        "避坑清单条目": len(checklist.split("\n")) if checklist else 0,
        "知识模式数": len(patterns.get("formula_stats", {})),
    }


def get_checklist() -> str:
    return _load_checklist()


def add_checklist_item(item: str):
    """人工追加避坑条目"""
    current = _load_checklist()
    if item not in current:
        _append_checklist(item)


# ───────── Internal helpers ─────────

def _load_patterns() -> dict:
    try:
        if os.path.exists(PATTERNS_PATH):
            with open(PATTERNS_PATH, encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {"formula_stats": {}, "symptom_clusters": {}, "effectiveness": {}}


def _save_patterns(patterns: dict):
    with open(PATTERNS_PATH, "w", encoding="utf-8") as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)


def _update_patterns(case: dict):
    """根据新案例更新学习到的模式"""
    from engine.diagnosis_engine import extract_patterns
    # 合并：新案例 + 已有模式
    patterns = _load_patterns()
    case_patterns = extract_patterns([case])

    for key in ["formula_stats", "symptom_clusters", "effectiveness"]:
        for k, v in case_patterns.get(key, {}).items():
            patterns[key][k] = patterns[key].get(k, 0) + v

    _save_patterns(patterns)
    # 同时生成避坑条目（如果无效）
    if case.get("疗效反馈") in ("无效", "恶化"):
        _append_checklist(
            f"[{case.get('id', '')}] {case.get('六经定位', '')} → {case.get('主方', '')} "
            f"疗效={case['疗效反馈']} | 症状：{case.get('symptoms', '')[:80]}"
        )


def _load_checklist() -> str:
    try:
        if os.path.exists(CHECKLIST_PATH):
            with open(CHECKLIST_PATH, encoding="utf-8") as f:
                return f.read().strip()
    except OSError:
        pass
    return ""


def _append_checklist(text: str):
    existing = set()
    if os.path.exists(CHECKLIST_PATH):
        with open(CHECKLIST_PATH, encoding="utf-8") as f:
            existing = {line.strip() for line in f.readlines() if line.strip()}
    new_lines = [l.strip() for l in text.split("\n") if l.strip() and l.strip() not in existing]
    if new_lines:
        with open(CHECKLIST_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
