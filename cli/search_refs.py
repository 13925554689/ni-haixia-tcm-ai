"""知识检索引擎 — 从 nihaisha-nishi-tcm 知识库检索课程原文 + 截图证据

架构：
- references/ 目录 → 按课程模块组织的 Markdown 参考文档
- screenshots/ 目录 → 按方名/穴位/课次索引的 WebP 截图
- pdf-cards/ 目录 → PDF 页级证据卡

检索策略：
1. 文件名关键词匹配（方名、穴位、症状、课程名）
2. 文件内容全文搜索（Markdown 正文）
3. 返回匹配摘要 + 文件路径 + 截图证据链接
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 知识库路径（相对于项目根目录）
_KB_ROOT = Path(__file__).parent.parent  # 倪海厦中医AI模型/
REFERENCES_DIR = _KB_ROOT / "references"
SCREENSHOTS_DIR = _KB_ROOT / "screenshots"

# 课程模块关键词映射
MODULE_KEYWORDS = {
    "伤寒论": ["伤寒", "太阳", "阳明", "少阳", "太阴", "少阴", "厥阴", "桂枝", "麻黄", "柴胡", "承气", "四逆", "理中"],
    "金匮要略": ["金匮", "百合", "狐惑", "疟病", "中风", "历节", "血痹", "虚劳", "肺痿", "胸痹", "腹满", "寒疝"],
    "黄帝内经": ["内经", "素问", "灵枢", "阴阳", "五行", "藏象", "经络", "气血"],
    "神农本草": ["本草", "药性", "四气", "五味", "上品", "中品", "下品"],
    "针灸大成": ["针灸", "穴位", "经络", "任督", "足三里", "合谷", "太冲", "百会", "关元", "气海", "涌泉"],
    "天纪": ["天纪", "命宫", "紫微", "斗数", "面相", "风水"],
    "八纲辨证": ["八纲", "阴阳", "表里", "寒热", "虚实"],
    "扶阳论坛": ["扶阳", "阳气", "附子", "火神"],
    "易筋经": ["易筋经", "导引", "吐纳"],
    "临床案例": ["案例", "医案", "诊疗日志"],
}


def _find_references_dir() -> Optional[Path]:
    """查找 references 目录（可能是 nihaisha-nishi-tcm-main/references/ 或 references/）"""
    candidates = [
        _KB_ROOT / "references",
        _KB_ROOT / "nihaisha-nishi-tcm-main" / "references",
        _KB_ROOT / "nihaisha-nishi-tcm-main",
    ]
    for d in candidates:
        if d.exists() and d.is_dir():
            return d
    return None


def _find_screenshots_dir() -> Optional[Path]:
    """查找截图目录"""
    candidates = [
        _KB_ROOT / "screenshots",
        _KB_ROOT / "nihaisha-nishi-tcm-main" / "screenshots",
        _KB_ROOT / "nihaisha-nishi-tcm-main" / "screenshot_evidence",
    ]
    for d in candidates:
        if d.exists() and d.is_dir():
            return d
    return None


def _normalize_query(query: str) -> str:
    """规范化查询文本（去标点、去空格）"""
    query = re.sub(r"[，,、。；;：:\s]+", "", query)
    return query.lower()


def search_by_keyword(query: str, module: Optional[str] = None, limit: int = 10) -> List[dict]:
    """关键词检索——按文件名 + 路径匹配"""
    refs_dir = _find_references_dir()
    screenshots_dir = _find_screenshots_dir()
    results = []

    if not refs_dir:
        return []

    q = _normalize_query(query)
    if not q:
        return []

    # 在 references 目录搜索 .md 文件
    md_files = list(refs_dir.rglob("*.md"))
    for f in md_files:
        # 文件名关键词匹配
        fname_lower = f.name.lower().replace("_", "").replace("-", "")
        rel_path = str(f.relative_to(refs_dir))

        # 如果指定了模块，过滤路径
        if module and module not in str(f):
            continue

        score = 0
        # 检查文件名包含查询词
        for char in q:
            if char in fname_lower:
                score += 1

        if score >= len(q) * 0.3:  # 30% 以上匹配
            # 提取文件摘要（前 200 字）
            try:
                content = f.read_text(encoding="utf-8")
                # 找包含关键词的段落
                lines = content.split("\n")
                snippets = []
                for i, line in enumerate(lines):
                    if q[:2] in line.lower() or q[:3] in line:
                        start = max(0, i - 1)
                        end = min(len(lines), i + 3)
                        snippet = "\n".join(lines[start:end])
                        snippets.append(snippet[:300])
                        if len(snippets) >= 3:
                            break
                summary = snippets[0] if snippets else lines[0][:200]
            except Exception:  # 文件读取失败，降级为仅文件名摘要
                summary = f"{f.name}"

            results.append({
                "source": rel_path,
                "name": f.name.replace(".md", ""),
                "type": "reference",
                "score": score,
                "summary": summary,
                "path": str(f),
            })

    # 文件名匹配失败时，fallback 到全文搜索
    if not results:
        for f in md_files[:50]:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:  # 文件编码/权限问题，跳过
                continue
            if query not in content:
                continue
            idx = content.find(query)
            start = max(0, idx - 100)
            end = min(len(content), idx + 300)
            snippet = content[start:end].replace("\n", " ")
            results.append({
                "source": f.relative_to(refs_dir).as_posix(),
                "name": f.name.replace(".md", ""),
                "type": "reference",
                "score": 1,
                "summary": f"...{snippet}...",
                "path": str(f),
            })

    # 截图搜索
    if screenshots_dir:
        ss_files = list(screenshots_dir.rglob("*.webp")) + list(screenshots_dir.rglob("*.png")) + list(screenshots_dir.rglob("*.jpg"))
        for f in ss_files[:500]:  # 限制扫描数量
            fname_lower = f.name.lower()
            score = sum(1 for char in q if char in fname_lower)
            if score >= len(q) * 0.3:
                results.append({
                    "source": str(f.relative_to(screenshots_dir)),
                    "name": f.name,
                    "type": "screenshot",
                    "score": score,
                    "summary": f"课程截图证据: {f.name}",
                    "path": str(f),
                })

    # 按分数排序
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def search_fulltext(query: str, limit: int = 10) -> List[dict]:
    """全文搜索——在 Markdown 正文中搜索关键词"""
    refs_dir = _find_references_dir()
    if not refs_dir:
        return []

    results = []
    md_files = list(refs_dir.rglob("*.md"))

    for f in md_files[:50]:  # 限制扫描文件数
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:  # 文件编码/权限问题，跳过
            continue

        # 检查是否包含查询词
        if query not in content:
            continue

        # 提取关键词所在段落
        idx = content.find(query)
        start = max(0, idx - 100)
        end = min(len(content), idx + 300)
        snippet = content[start:end].replace("\n", " ")[:300]

        results.append({
            "source": str(f.relative_to(refs_dir)),
            "name": f.name.replace(".md", ""),
            "type": "reference",
            "summary": f"...{snippet}...",
            "path": str(f),
        })

    return results[:limit]


def search_evidence(formula_name: str, limit: int = 5) -> dict:
    """为指定方剂检索课程证据（MD 参考 + 截图）"""
    ref_results = search_by_keyword(formula_name, limit=limit) + search_fulltext(formula_name, limit=3)
    screenshot_results = []

    screenshots_dir = _find_screenshots_dir()
    if screenshots_dir:
        ss_files = list(screenshots_dir.rglob("*.webp")) + list(screenshots_dir.rglob("*.png"))
        for f in ss_files[:300]:
            if formula_name in f.name or any(c in f.name for c in formula_name):
                screenshot_results.append({
                    "path": str(f),
                    "name": f.name,
                    "type": "screenshot",
                })

    # 去重
    seen = set()
    unique_refs = []
    for r in ref_results:
        if r["path"] not in seen:
            seen.add(r["path"])
            unique_refs.append(r)

    return {
        "formula": formula_name,
        "references": unique_refs[:limit],
        "screenshots": screenshot_results[:5],
        "total_refs": len(unique_refs),
        "total_screenshots": len(screenshot_results),
    }


def list_modules() -> List[str]:
    """列出可用的课程模块"""
    refs_dir = _find_references_dir()
    if not refs_dir:
        return list(MODULE_KEYWORDS.keys())

    modules = set()
    for f in refs_dir.rglob("*.md"):
        parts = str(f.relative_to(refs_dir)).split(os.sep)
        if parts[0]:
            modules.add(parts[0])

    return sorted(modules) if modules else list(MODULE_KEYWORDS.keys())


def get_module_stats() -> dict:
    """获取知识库统计信息"""
    refs_dir = _find_references_dir()
    screenshots_dir = _find_screenshots_dir()

    stats = {
        "modules_available": list_modules(),
        "reference_files": 0,
        "screenshot_files": 0,
        "total_size_mb": 0,
        "knowledge_base_loaded": False,
    }

    if refs_dir:
        md_files = list(refs_dir.rglob("*.md"))
        stats["reference_files"] = len(md_files)
        stats["knowledge_base_loaded"] = len(md_files) > 0
        try:
            stats["total_size_mb"] = round(sum(f.stat().st_size for f in md_files) / (1024 * 1024), 1)
        except Exception:  # 文件状态读取失败（非致命）
            pass

    if screenshots_dir:
        ss_files = list(screenshots_dir.rglob("*.webp")) + list(screenshots_dir.rglob("*.png"))
        stats["screenshot_files"] = len(ss_files)

    return stats


# ─── CLI 入口 ───
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python search_refs.py <关键词> [--module 模块名]")
        print("可用模块:", ", ".join(list_modules()))
        sys.exit(0)

    query = sys.argv[1]
    module = None

    if "--module" in sys.argv:
        idx = sys.argv.index("--module")
        if idx + 1 < len(sys.argv):
            module = sys.argv[idx + 1]

    results = search_by_keyword(query, module=module)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n共找到 {len(results)} 条结果")
