import os, sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ollama import AsyncClient

sys.path.append(str(Path(__file__).resolve().parents[2]))
from schemas import AnalyzeRequest, AnalyzeResponse

router = APIRouter()

@router.post("/", response_model=AnalyzeResponse, summary="Анализ сайтов")
async def analyze(request: AnalyzeRequest):
    text = "\n".join(
        f"{s.site} --- {s.minutes} минут" for s in request.sites
    )
    host  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "self-mind-ai")
    try:
        client   = AsyncClient(host=host)
        response = await client.chat(
            model=model,
            messages=[{"role": "user", "content": text}],
            format=AnalyzeResponse.model_json_schema(),
            options={"temperature": 0.2}
        )
        return AnalyzeResponse.model_validate_json(response.message.content)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama: {str(e)}")
