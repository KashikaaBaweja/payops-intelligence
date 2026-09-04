from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from payops_core.config import get_settings
from payops_core.data.seed import seed
from payops_core.graph import build_graph
from payops_core.rag.vector_store import build_store
from payops_core.tools.merchant_health import merchant_health

from apps.api.routers.investigations import router as investigations_router

settings = get_settings()
app = FastAPI(title="PayOps Intelligence", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(investigations_router)

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        seed()
        build_store()
        _graph = build_graph()
    return _graph


@app.on_event("startup")
def startup() -> None:
    get_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/merchants/{merchant_id}/health")
def merchant_health_endpoint(merchant_id: str) -> dict:
    item = merchant_health(merchant_id)
    return item.model_dump(mode="json")


@app.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str) -> dict:
    return {"evidence_id": evidence_id, "detail": "Evidence is returned inline on /investigations."}


def run() -> None:
    import uvicorn

    uvicorn.run("apps.api.main:app", host=settings.api_host, port=settings.api_port, reload=False)
