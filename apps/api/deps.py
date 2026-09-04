from payops_core.config import get_settings
from payops_core.graph import build_graph


def get_orchestrator():
    get_settings()
    return build_graph()
