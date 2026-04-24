from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1 import models, analysis

app = FastAPI(
    title="KDeepMatrixAI API",
    description="빅데이터 분석·가시화 통합 플랫폼 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models.router, prefix="/api/v1", tags=["Models"])
app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
