"""倪海厦中医AI — 核心辩证诊断引擎
ponytail: ~220行，六经辨证+10问法+症状→证型→经方→药性分析+进化反馈
"""
import json
import re
import os
from engine.knowledge_base import (
    DIAGNOSIS_FRAMEWORK, HEALTH_BASELINE, FORMULA_DB, HERB_DB, DIAGNOSIS_TEMPLATE
)
from engine.diagnosis_formula import formula_diagnose, enrich_diagnosis_with_formula

# ponytail: evolution feedback — load learned patterns once at import time
_LEARNED_PATTERNS = {}
_HISTORY_PENALTY = set()
_PATTERNS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "learned_patterns.json")
_CHECKLIST_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "evolution_checklist.txt")
try:
    if os.path.exists(_PATTERNS_PATH):
        with open(_PATTERNS_PATH, encoding="utf-8") as f:
            _LEARNED_PATTERNS = json.load(f)
except (json.JSONDecodeError, OSError):
    pass

# ponytail: parse checklist for historically-failed formulas
try:
    if os.path.exists(_CHECKLIST_PATH):
        with open(_CHECKLIST_PATH, encoding="utf-8") as f:
            for line in f:
                m = re.search(r'→\s*(\S+)', line)
                if m:
                    _HISTORY_PENALTY.add(m.group(1))
except OSError:
    pass

# 症状→六经映射（关键词匹配）
_SYMPTOM_CHANNEL_MAP = [
    # 太阳
    (r"恶寒|怕冷|发冷|头项强|颈项强|后头痛|脉浮|身疼|无汗|有汗|小便不利|水入即吐|少腹满|少腹急结|如狂|项背强|发热而渴|不恶寒|咽痛|鼻鸣|干呕|鼻塞|身痛|腰痛",
     "太阳病"),
    # 阳明
    (r"大热|大汗|大渴|口渴甚|便秘|腹满|腹胀|谵语|胡言|潮热|日晡|心烦|懊憹|懊恼|失眠|不得眠|虚烦|身黄|黄疸|喜忘|屎硬|色黑|心中懊",
     "阳明病"),
    # 少阳
    (r"口苦|咽干|目眩|胸胁|胁痛|往来寒热|忽冷忽热|弦脉|默默不欲食|心烦喜呕|心下痞硬|胸胁满|但头汗出|胸满烦惊|一身尽重",
     "少阳病"),
    # 太阴
    (r"腹满时痛|食不下|呕吐清|下利清|拉肚子|脾|胃寒|腹胀便溏|完谷不化|脘腹胀满|不思饮食|嗳腐|肢体沉重|心下痞硬|兼表",
     "太阴病"),
    # 少阴
    (r"脉微细|欲寐|嗜睡|四肢厥|手脚冰冷|心悸|腰膝酸|但欲眠|精神萎|下利清谷|恶寒蜷卧|心中烦|不得卧|不得眠|口燥咽干|心下悸|头眩|身瞤动|四肢沉重|背恶寒|骨节痛|脉沉",
     "少阴病"),
    # 厥阴
    (r"消渴|气上撞|心中疼|饥不欲食|手足厥|厥热|蛔|巅顶痛|寒热错杂|脉细欲绝|手足厥寒|热利下重|便脓血|干呕|吐涎沫|头痛|久利",
     "厥阴病"),
]


def diagnose(symptoms: str) -> dict:
    """主入口：公式优先 → 关键词fallback → 辨证结果 → 经方建议 → 药性分析
    v2.0: 双引擎架构（nihaixia 公式引擎 + 原有关键词引擎）
    """
    symptoms = symptoms.strip()

    # ─── 引擎1: 公式优先 ───
    formula_result = formula_diagnose(symptoms)
    if formula_result and formula_result.get("置信度") in ("高",):
        # 高置信度公式匹配 → 直接返回公式结果 + 药性分析
        formula_name = formula_result.get("主方", "")
        formula_detail = FORMULA_DB.get(formula_name, {}) if formula_name else {}
        herb_analysis = _build_herb_analysis(formula_detail)
        return {
            "diagnosis": f"{formula_result['六经定位']} → {formula_name}",
            "六经定位": formula_result["六经定位"],
            "置信度": formula_result["置信度"],
            "主方": formula_name or "辨证选方中",
            "病机": SIX_CHANNEL_DISEASE.get(formula_result["六经定位"], ""),
            "治法": SIX_CHANNEL_TREATMENT.get(formula_result["六经定位"], ""),
            "药性分析": herb_analysis,
            "方剂详情": formula_detail or {},
            "煎服法": formula_detail.get("煎法", "") if formula_detail else "",
            "加减法": formula_detail.get("加减", {}) if formula_detail else {},
            "注意事项": formula_detail.get("禁忌", "") if formula_detail else "",
            "倪海厦诊疗思路": formula_result.get("鉴别提示", ""),
            "辨证公式": formula_result.get("辨证公式", ""),
            "辨证法则": formula_result.get("辨证法则", ""),
            "鉴别要点": formula_result.get("鉴别要点", []),
            "危险信号": formula_result.get("危险信号", ""),
            "问诊补充建议": _get_followup_questions(symptoms),
            "健康基线对比": _compare_health_baseline(symptoms),
            "引擎": "formula",
        }

    # ─── 引擎2: 关键词匹配（原有逻辑 + 公式增强）───
    _KW_CHANNELS = [
        ("太阳病", ["恶寒", "怕冷", "发冷", "头项强", "颈项强", "后头痛", "脉浮", "身疼", "无汗", "有汗", "小便不利", "水入即吐", "少腹满", "少腹急结", "如狂", "项背强", "发热而渴", "不恶寒", "咽痛", "鼻鸣", "干呕", "鼻塞", "身痛", "腰痛"]),
        ("阳明病", ["大热", "大汗", "大渴", "口渴甚", "便秘", "腹满", "腹胀", "谵语", "胡言", "潮热", "日晡", "心烦", "懊憹", "懊恼", "失眠", "不得眠", "虚烦", "身黄", "黄疸", "喜忘", "屎硬", "色黑", "心中懊"]),
        ("少阳病", ["口苦", "咽干", "目眩", "胸胁", "胁痛", "往来寒热", "忽冷忽热", "弦脉", "默默不欲食", "心烦喜呕", "心下痞硬", "胸胁满", "但头汗出", "胸满烦惊", "一身尽重"]),
        ("太阴病", ["腹满时痛", "食不下", "呕吐清", "下利清", "拉肚子", "脾", "胃寒", "腹胀便溏", "完谷不化", "脘腹胀满", "不思饮食", "嗳腐", "肢体沉重", "心下痞硬", "兼表", "拒按"]),
        ("少阴病", ["脉微细","脉细数","欲寐","嗜睡","四肢厥","手脚冰冷","心悸","腰膝酸","但欲眠","精神萎","但欲寐","下利清谷","恶寒蜷卧","心中烦","不得卧","不得眠","口燥咽干","口干咽燥","心下悸","头眩","身瞤动","四肢沉重","背恶寒","骨节痛","脉沉"]),
        ("厥阴病", ["消渴", "气上撞", "心中疼", "饥不欲食", "手足厥", "厥热", "蛔", "巅顶痛", "寒热错杂", "脉细欲绝", "手足厥寒", "热利下重", "便脓血", "干呕", "吐涎沫", "头痛", "久利"]),
    ]
    channel_scores = {}
    for channel, keywords in _KW_CHANNELS:
        score = sum(1 for kw in keywords if kw in symptoms)
        if score > 0:
            channel_scores[channel] = score

    if not channel_scores:
        return {
            "diagnosis": "信息不足",
            "六经定位": "无法确定",
            "置信度": "低",
            "建议": "请补充更多症状信息（最好覆盖以下10个方面）：" +
                     "、".join([q[0] for q in DIAGNOSIS_TEMPLATE]),
        }

    primary = max(channel_scores, key=channel_scores.get)
    secondary = sorted(channel_scores.items(), key=lambda x: -x[1])

    # 步骤2: 确定子类（根据额外关键词细化证型）
    frame = DIAGNOSIS_FRAMEWORK.get(primary, {})
    subtype = _match_subtype(symptoms, frame.get("子类", {}))

    # 步骤3: 选方
    formula_name = subtype["主方"] if subtype else None
    formula_detail = FORMULA_DB.get(formula_name, {}) if formula_name else None

    # ponytail: evolution feedback — warn if historically failed formula
    evolution_warning = ""
    if formula_name and formula_name in _HISTORY_PENALTY:
        evolution_warning = f"⚠ 系统历史记录中，「{formula_name}」对类似症状曾出现「无效」反馈。建议详细辨证确认。"

    # 步骤4: 药性分析
    herb_analysis = []
    if formula_detail:
        for herb, dose in formula_detail.get("组成", {}).items():
            info = HERB_DB.get(herb, {})
            herb_analysis.append({
                "药名": herb,
                "剂量": dose,
                "性味": info.get("性味", ""),
                "归经": info.get("归经", ""),
                "功效": info.get("功效", ""),
                "倪注": info.get("倪注", ""),
                "禁忌": info.get("禁忌", ""),
            })

    # ───────── Health-dimension confidence ─────────
    dim_score = sum(1 for name, pat in [
        ("睡眠", r"睡|眠|梦|醒|欲寐|嗜睡"),
        ("饮食", r"胃口|食欲|食|饿|胀"),
        ("寒热", r"怕冷|恶寒|发热|怕热|往来寒热|忽冷忽热|大热"),
        ("汗出", r"汗|无汗|有汗|大汗"),
        ("疼痛", r"痛|疼|强|苦|满|眩"),
        ("二便", r"大便|小便|便秘|腹泻|下利"),
        ("脉象", r"脉浮|脉沉|脉弦|脉微|脉细|脉大|脉数|脉洪"),
        ("手足", r"手|脚|四肢|厥|温|冷|冰"),
    ] if re.search(pat, symptoms))
    if dim_score >= 4:
        confidence = "高"
    elif dim_score >= 2:
        confidence = "中"
    else:
        confidence = "低"
    health_gaps = _compare_health_baseline(symptoms)

    return {
        "diagnosis": f"{primary} → {subtype.get('name', subtype.get('主方', '待定'))}" if subtype else primary,
        "六经定位": primary,
        "病机": frame.get("病机", ""),
        "治法": frame.get("治法", ""),
        "证型": subtype.get("name", "") if subtype else "进一步辨证中",
        "证型主症": subtype.get("主症", "") if subtype else "",
        "多经关联": [{"经": s[0], "得分": s[1]} for s in secondary[:3]],
        "主方": formula_name or "辨证选方中",
        "方剂详情": formula_detail or {},
        "药性分析": herb_analysis,
        "煎服法": formula_detail.get("煎法", "") if formula_detail else "",
        "加减法": formula_detail.get("加减", {}) if formula_detail else {},
        "注意事项": formula_detail.get("禁忌", "") if formula_detail else "",
        "健康基线对比": health_gaps,
        "倪海厦诊疗思路": _generate_ni_commentary(primary, symptoms, formula_name or ""),
        "问诊补充建议": _get_followup_questions(symptoms),
        "置信度": confidence,
    }


def _match_subtype(symptoms: str, subtypes: dict) -> dict:
    """在六经子类中匹配最可能的证型（ponytail: exact beats fuzzy; multi-char kw prioritised）"""
    if not subtypes:
        return {}
    best = None
    best_exact = 0
    best_fuzzy = 0
    for name, info in subtypes.items():
        keywords_text = info.get("主症", "")
        keywords = [kw.strip() for kw in re.split(r"[、，,]", keywords_text) if kw.strip()]
        exact = sum(1 for kw in keywords if kw in symptoms)
        # ponytail: fuzzy fallback — only if no exact match found
        fuzzy = 0
        if exact == 0:
            for kw in keywords:
                if len(kw) >= 2:
                    kw_chars = set(kw)
                    sym_chars = set(symptoms)
                    if len(kw_chars & sym_chars) / len(kw_chars) >= 0.6:
                        fuzzy += 1
        # ponytail: exact always beats fuzzy; longer-keyword matches weigh more
        if (exact > best_exact) or (exact == best_exact and fuzzy > best_fuzzy):
            best_exact = exact
            best_fuzzy = fuzzy
            best = {"name": name, **info}
        # ponytail: tiebreaker — prefer subtype with longer total matched text
        elif exact == best_exact and exact > 0:
            # Sum length of matched keywords to break ties
            new_matched_len = sum(len(kw) for kw in keywords if kw in symptoms)
            old_kws = [k.strip() for k in re.split(r"[、，,]", best.get("主症", "")) if k.strip()]
            old_matched_len = sum(len(kw) for kw in old_kws if kw in symptoms)
            if new_matched_len > old_matched_len:
                best = {"name": name, **info}
    return best or {}


def _compare_health_baseline(symptoms: str) -> list:
    gaps = []
    checks = [
        ("睡眠", r"失眠|多梦|易醒|难入睡|醒来|睡不好|熬夜"),
        ("饮食", r"没胃口|不饿|食欲|吃不下|纳差|胀满"),
        ("大小便", r"便秘|拉肚子|腹泻|便溏|稀|尿频|尿急|尿痛|小便.*黄|小便.*红"),
        ("手足温度", r"手脚冰|手脚冷|四肢冷|手足冷|四肢厥|冰凉"),
        ("口渴", r"口渴|口干|不渴|喜冷|喜热"),
    ]
    for name, pattern in checks:
        if re.search(pattern, symptoms):
            gaps.append({"维度": name, "健康标准": HEALTH_BASELINE.get(name, ""),
                         "偏差": re.search(pattern, symptoms).group(0)})
    return gaps


def _generate_ni_commentary(channel: str, symptoms: str, formula: str) -> str:
    """生成倪海厦风格的诊疗思路解读"""
    lines = []
    info = DIAGNOSIS_FRAMEWORK.get(channel, {})

    if channel == "太阳病":
        lines.append("外邪初犯，尚在表浅。倪师常说：「病在太阳，一剂而愈。」解表是第一要务。")
        if "有汗" in symptoms:
            lines.append("有汗→表虚→桂枝汤思路。汗出说明卫气已弱，不可再用麻黄强行发汗。")
        elif "无汗" in symptoms:
            lines.append("无汗→表实→麻黄汤思路。毛孔闭塞，需麻黄发阳打开。")

    elif channel == "阳明病":
        lines.append("邪已入里化热。倪师：「阳明无死证。」意思是及时清下可愈。")
        lines.append("关键判断：是否有便秘？有便秘→腑证（承气汤类）；无便秘→经证（白虎汤）。")

    elif channel == "少阳病":
        lines.append("邪在半表半里，三焦枢机不利。倪师：「柴胡剂是少阳专药，一升一降通三焦。」")
        lines.append("口苦=胆汁上逆；咽干=津不上承；目眩=少阳经气不利。三症具二即可辨为少阳。")

    elif channel == "太阴病":
        lines.append("脾胃虚寒。倪师：「理中者，理中焦也。」脾胃一虚，百病丛生。")
        lines.append("腹满时痛+食不下→理中汤。下利清谷→加干姜量。")

    elif channel == "少阴病":
        lines.append("病及心肾，正气大虚。倪师：「脉微细、但欲寐——这是生死关头。」")
        if "四肢厥" in symptoms or "手脚冷" in symptoms or "手脚冰" in symptoms:
            lines.append("四肢厥冷→寒化证→四逆汤回阳救逆。命门之火将熄，非附子不能挽回。")
        elif "烦" in symptoms and "不得" in symptoms:
            lines.append("心烦不得卧→热化证→黄连阿胶汤滋阴降火。")

    elif channel == "厥阴病":
        lines.append("阴阳失调、寒热错杂。倪师：「厥阴是最后一关，过了就出三阳，不过就入阴。」")
        lines.append("厥热胜复=阳气与阴邪拉锯战。乌梅丸清上温下，寒热并调。")

    return "\n".join(lines) if lines else "需要更详细的症状信息来确认辨证。"


def _get_followup_questions(symptoms: str) -> list:
    """基于输入症状，判断缺什么信息需要追问"""
    missing = []
    checks = {
        "睡眠": r"睡|眠|梦|醒",
        "饮食": r"胃口|食欲|食|饿|胀",
        "大便": r"大便|便秘|腹泻|便|拉",
        "小便": r"小便|尿",
        "口渴": r"渴|口[干燥]|饮",
        "寒热": r"怕冷|恶寒|怕热|发热|恶风|冷",
        "汗出": r"汗",
        "手足温度": r"手|脚|四肢|厥|温|冷|冰",
    }
    for name, pattern in checks.items():
        if not re.search(pattern, symptoms):
            q = [q[1] for q in DIAGNOSIS_TEMPLATE if q[0] == name]
            if q:
                missing.append(f"【{name}】{q[0]}")
    return missing


# ───────── 双引擎helper ─────────

# 六经病机/治法速查（供公式引擎使用）
SIX_CHANNEL_DISEASE = {
    "太阳病": "外邪袭表，卫气抗争",
    "阳明病": "邪热入里，胃肠燥实",
    "少阳病": "邪在半表半里，枢机不利",
    "太阴病": "脾虚寒湿，运化失常",
    "少阴病": "心肾阳虚，阴阳俱损",
    "厥阴病": "阴阳失调，寒热错杂",
}

SIX_CHANNEL_TREATMENT = {
    "太阳病": "解表",
    "阳明病": "清热/攻下",
    "少阳病": "和解",
    "太阴病": "温中散寒",
    "少阴病": "回阳救逆",
    "厥阴病": "寒热并调",
}


def _build_herb_analysis(formula_detail: dict) -> list:
    """构建药性分析列表"""
    if not formula_detail:
        return []
    result = []
    for herb, dose in formula_detail.get("组成", {}).items():
        info = HERB_DB.get(herb, {})
        result.append({
            "药名": herb,
            "剂量": dose,
            "性味": info.get("性味", ""),
            "归经": info.get("归经", ""),
            "功效": info.get("功效", ""),
            "倪注": info.get("倪注", ""),
            "禁忌": info.get("禁忌", ""),
        })
    return result


# ───────── Self-evolution layer ─────────

def extract_patterns(all_cases: list) -> dict:
    """从案例库中提取可复用模式（症状→方剂关联统计）"""
    patterns = {"formula_stats": {}, "symptom_clusters": {}, "effectiveness": {}}
    for case in all_cases:
        if not isinstance(case, dict):
            continue
        formula = case.get("主方", "")
        if formula:
            patterns["formula_stats"][formula] = patterns["formula_stats"].get(formula, 0) + 1
        for symptom in re.split(r"[，,、；;]", case.get("symptoms", "")):
            symptom = symptom.strip()
            if symptom:
                patterns["symptom_clusters"][symptom] = patterns["symptom_clusters"].get(symptom, 0) + 1
        efficacy = case.get("疗效反馈", "") or case.get("efficacy", "")
        if efficacy:
            patterns["effectiveness"][efficacy] = patterns["effectiveness"].get(efficacy, 0) + 1
    return patterns
