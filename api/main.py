from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.analyze import router

app = FastAPI(
    title="🧠 Self Mind ML",
    description="Принимает JSON → прогоняет через qwen2.5:3b → возвращает советы",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/analyze", tags=["🤖 Анализ"])

@app.get("/health", tags=["🔧 System"])
async def health():
    return {"status": "ok"}
