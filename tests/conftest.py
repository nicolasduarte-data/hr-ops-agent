"""Pytest session setup.

Disable Langfuse tracing for the entire test run, BEFORE any application import
triggers config's load_dotenv(). Tests exercise run_agent() against a mocked
Anthropic client, but the tracer is independent of that mock — with real
LANGFUSE_* keys present in .env, it would emit live traces to the *production*
observability backend on every test run (polluting the dashboard with fixtures
like "test" / "Trigger an error" / "Loop forever").

Forcing the keys empty here keeps the tracer a no-op. `load_dotenv(override=False)`
in config.py will not clobber these already-set values, so tests can never write
to production Langfuse.
"""

import os

os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""

# If the tracer singleton was somehow built before this ran, reset it so it
# rebuilds in the disabled state on the next get_tracer() call.
try:
    from src.agent import tracer as _tracer

    _tracer._tracer = None
except Exception:
    pass
