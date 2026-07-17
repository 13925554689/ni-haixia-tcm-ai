"""6经辨证回归测试 — 13个关键方证"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from engine.diagnosis_engine import diagnose
from engine.knowledge_base import DIAGNOSIS_FRAMEWORK, FORMULA_DB, HERB_DB

TESTS = [
    ("恶寒发热 无汗 头项强痛 脉浮紧 身体酸痛", "太阳病", "麻黄汤"),
    ("恶风 发热 汗出 脉浮缓 鼻鸣干呕", "太阳病", "桂枝汤"),
    ("项背强几几 无汗恶风 脉浮紧", "太阳病", "葛根汤"),
    ("发热恶寒 热多寒少 如疟状 面赤身痒 脉微缓", "太阳病", "桂枝麻黄各半汤"),
    ("大热 大汗 大渴 脉洪大 面赤心烦", "阳明病", "白虎汤"),
    ("潮热 谵语 腹满 大便硬 手足濈然汗出 脉沉实", "阳明病", "大承气汤"),
    ("口苦 咽干 目眩 胸胁苦满 往来寒热 心烦喜呕 默默不欲饮食", "少阳病", "小柴胡汤"),
    ("胸胁苦满 呕吐不止 郁郁微烦 心下急", "少阳病", "大柴胡汤"),
    ("腹满时痛 食不下 下利清谷 四肢不温", "太阴病", "理中汤"),
    ("手脚冰冷 欲寐 脉微细 精神萎靡 畏寒", "少阴病", "四逆汤"),
    ("心中烦 不得眠 口干咽燥 脉细数", "少阴病", "黄连阿胶汤"),
    ("消渴 心中疼热 饥不欲食 气上冲心", "厥阴病", "乌梅丸"),
    ("手足厥寒 脉细欲绝 四肢冰冷", "厥阴病", "当归四逆汤"),
]


def test_kb_integrity():
    n_sub = sum(len(v["子类"]) for v in DIAGNOSIS_FRAMEWORK.values())
    missing = [(k, h) for k, f in FORMULA_DB.items()
               for h in f.get("组成", {}) if h not in HERB_DB]
    assert len(DIAGNOSIS_FRAMEWORK) == 6, f"{len(DIAGNOSIS_FRAMEWORK)}经"
    assert n_sub >= 28, f"仅{n_sub}证"
    assert len(HERB_DB) >= 45, f"仅{len(HERB_DB)}味"
    assert not missing, f"药材缺失: {missing[:3]}"


def test_sweep():
    fails = []
    for s, ec, ef in TESTS:
        r = diagnose(s)
        if r["六经定位"] != ec or r["主方"] != ef:
            fails.append(f"{ec}→{ef}: got {r['六经定位']}→{r['主方']}")
    assert not fails, "\n".join(fails)


def test_confidence_tiers():
    r = diagnose("恶寒发热 无汗 头项强痛 脉浮紧")
    assert r["置信度"] in ("高", "中"), f"高置信度用例置信度={r['置信度']}"
    r2 = diagnose("手脚冰冷")
    assert r2["置信度"] in ("低",), f"低置信度用例置信度={r2['置信度']}"
