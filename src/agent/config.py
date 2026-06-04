import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
# Routing option for cost-sensitive paths: "claude-haiku-4-5"
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
MAX_TURNS: int = int(os.getenv("MAX_TURNS", "10"))
