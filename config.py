"""倪海厦中医AI智能体 - 配置"""
import os
from dotenv import load_dotenv

# ponytail: load project .env first, then main Hermes .env as fallback for API keys
load_dotenv()
_main_hermes_env = os.path.join(os.path.expanduser("~"), ".hermes", ".env")
if os.path.exists(_main_hermes_env):
    load_dotenv(_main_hermes_env)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ponytail: try DeepSeek → OpenRouter(Anthropic) → GLM → None
LLM_API_KEY = ""
LLM_BASE_URL = ""
LLM_MODEL = ""
LLM_PROVIDER = "none"

_ds_key = os.getenv("DEEPSEEK_API_KEY", "")
_anthro_key = os.getenv("ANTHROPIC_API_KEY", "")
_glm_key = os.getenv("GLM_API_KEY", "")

if _ds_key:
    LLM_API_KEY = _ds_key
    LLM_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_PROVIDER = "deepseek"
elif _anthro_key and _anthro_key.startswith("sk-or"):
    # OpenRouter key stored as ANTHROPIC_API_KEY
    LLM_API_KEY = _anthro_key
    LLM_BASE_URL = "https://openrouter.ai/api/v1"
    LLM_MODEL = "anthropic/claude-sonnet-4"
    LLM_PROVIDER = "openrouter"
elif _anthro_key and _anthro_key.startswith("sk-ant"):
    LLM_API_KEY = _anthro_key
    LLM_BASE_URL = "https://api.anthropic.com"
    LLM_MODEL = "claude-sonnet-4-20250514"
    LLM_PROVIDER = "anthropic"
elif _glm_key:
    LLM_API_KEY = _glm_key
    LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    LLM_MODEL = "glm-4-flash"
    LLM_PROVIDER = "glm"

DATA_DIR = os.path.join(BASE_DIR, "data")
CASES_DIR = os.path.join(DATA_DIR, "cases")
CHECKLIST_PATH = os.path.join(DATA_DIR, "evolution_checklist.txt")
PATTERNS_PATH = os.path.join(DATA_DIR, "learned_patterns.json")

os.makedirs(CASES_DIR, exist_ok=True)
