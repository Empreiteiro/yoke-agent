"""Keep ``import ragas`` working with langchain-community >= 0.4.

Every ragas release (0.2 – 0.4) runs
``from langchain_community.chat_models.vertexai import ChatVertexAI`` at
import time, but langchain-community 0.4 removed that module, so a fresh
install crashed the backend on startup. ragas only uses the class in an
``isinstance`` check for Vertex models (which Yoke doesn't use), so a
placeholder class is enough. Importing this module is a no-op when the real
module is available.
"""

import sys
import types

try:
    import langchain_community.chat_models.vertexai  # noqa: F401
except ImportError:
    _shim = types.ModuleType("langchain_community.chat_models.vertexai")
    _shim.ChatVertexAI = type("ChatVertexAI", (), {})
    sys.modules[_shim.__name__] = _shim
