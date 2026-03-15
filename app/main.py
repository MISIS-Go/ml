from contextlib import asynccontextmanager
import os
import time
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from starlette.responses import JSONResponse, Response

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


REQUEST_COUNTER = Counter("ml_requests_total", "Total ML requests", ["endpoint"])
MODEL_SCORE = Gauge("ml_last_score", "Last generated score")
OLLAMA_REQUEST_COUNTER = Counter("ml_ollama_requests_total", "Total Ollama requests", ["status", "endpoint"])
START_TIME = time.time()


class PredictionRequest(BaseModel):
    team_name: str
    dataset_rows: int
    urgency: str = "normal"


class StackAdvice(BaseModel):
    summary: str
    suggested_stack: list[str]


class SiteAnalysisRequest(BaseModel):
    url: str
    time_spent: int = Field(ge=0)


class SiteAnalysisResponse(BaseModel):
    anxiety_level: int = Field(ge=0, le=100)
    content_type: str
    summary: str


def configure_tracing() -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return

    resource = Resource.create({"service.name": "ml-service"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def classify_url(url: str) -> tuple[str, int]:
    host = urlparse(url).netloc.lower()
    target = f"{host} {url.lower()}"

    categories = [
        ("news", 72, ("news", "press", "politics", "war", "breaking")),
        ("social_media", 68, ("social", "twitter", "x.com", "reddit", "tiktok", "instagram", "facebook")),
        ("forum", 58, ("forum", "community", "thread", "discussion")),
        ("video", 46, ("video", "youtube", "stream", "twitch")),
        ("shopping", 34, ("shop", "store", "market", "cart")),
        ("education", 24, ("learn", "docs", "course", "wiki", "edu")),
        ("wellbeing", 18, ("mind", "meditation", "calm", "health")),
    ]

    for content_type, anxiety_level, keywords in categories:
        if any(keyword in target for keyword in keywords):
            return content_type, anxiety_level
    return "general", 40


def heuristic_site_analysis(payload: SiteAnalysisRequest) -> SiteAnalysisResponse:
    content_type, baseline = classify_url(payload.url)
    extra = min(20, int(payload.time_spent / 180))
    anxiety_level = min(96, baseline + extra)

    if anxiety_level >= 75:
        summary = "Контент выглядит эмоционально нагруженным, лучше сократить сессию и переключиться на более спокойный формат."
    elif anxiety_level >= 55:
        summary = "Есть умеренная тревожная нагрузка, полезно контролировать длительность сессии и частоту уведомлений."
    else:
        summary = "Контент выглядит относительно спокойным, но длинные сессии все равно лучше разбивать перерывами."

    return SiteAnalysisResponse(
        anxiety_level=anxiety_level,
        content_type=content_type,
        summary=summary,
    )


async def ollama_json(endpoint: str, prompt: str, schema: dict) -> dict:
    ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ollama_host}/api/generate",
            json={
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": schema,
            },
        )
        response.raise_for_status()
        OLLAMA_REQUEST_COUNTER.labels(status="success", endpoint=endpoint).inc()
        return response.json()


async def generate_stack_advice(payload: PredictionRequest, score: float) -> dict:
    prompt = (
        "You are advising a hackathon team.\n"
        f"Team: {payload.team_name}\n"
        f"Dataset rows: {payload.dataset_rows}\n"
        f"Urgency: {payload.urgency}\n"
        f"Score: {round(score, 3)}\n"
        "Return a short recommendation with exactly two fields in JSON: "
        '"summary" as one sentence and "suggested_stack" as an array of 3 to 5 lowercase technologies.'
    )
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "suggested_stack": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 5,
            },
        },
        "required": ["summary", "suggested_stack"],
    }
    payload_json = await ollama_json("/predict", prompt, schema)
    return StackAdvice.model_validate_json(payload_json.get("response", "{}")).model_dump()


async def analyze_site_with_ollama(payload: SiteAnalysisRequest) -> SiteAnalysisResponse:
    content_type, baseline = classify_url(payload.url)
    prompt = (
        "You analyze how emotionally demanding a website is for a user.\n"
        f"URL: {payload.url}\n"
        f"Time spent in seconds: {payload.time_spent}\n"
        f"Heuristic content type: {content_type}\n"
        f"Heuristic anxiety baseline: {baseline}\n"
        "Return JSON with three fields only: "
        '"anxiety_level" as integer 0..100, "content_type" as one of '
        'news, social_media, entertainment, education, shopping, forum, wellbeing, video, general, '
        'and "summary" as one short Russian sentence.'
    )
    schema = {
        "type": "object",
        "properties": {
            "anxiety_level": {"type": "integer", "minimum": 0, "maximum": 100},
            "content_type": {
                "type": "string",
                "enum": [
                    "news",
                    "social_media",
                    "entertainment",
                    "education",
                    "shopping",
                    "forum",
                    "wellbeing",
                    "video",
                    "general",
                ],
            },
            "summary": {"type": "string"},
        },
        "required": ["anxiety_level", "content_type", "summary"],
    }
    payload_json = await ollama_json("/analyze-site", prompt, schema)
    return SiteAnalysisResponse.model_validate_json(payload_json.get("response", "{}"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_tracing()
    yield


app = FastAPI(title="SafeMind ML Service", version="0.2.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)


@app.get("/")
async def root() -> JSONResponse:
    REQUEST_COUNTER.labels(endpoint="/").inc()
    return JSONResponse({"service": "ml", "status": "ready"})


@app.get("/healthz")
async def healthz() -> JSONResponse:
    REQUEST_COUNTER.labels(endpoint="/healthz").inc()
    return JSONResponse(
        {
            "service": "ml",
            "status": "ok",
            "uptime_seconds": round(time.time() - START_TIME, 2),
        }
    )


@app.post("/predict")
async def predict(payload: PredictionRequest) -> JSONResponse:
    REQUEST_COUNTER.labels(endpoint="/predict").inc()

    urgency_weight = {"low": 0.8, "normal": 1.0, "high": 1.2}.get(payload.urgency, 1.0)
    score = min(0.99, ((payload.dataset_rows / 1000.0) * 0.35 + 0.55) * urgency_weight)
    MODEL_SCORE.set(score)

    result = {
        "team_name": payload.team_name,
        "score": round(score, 3),
        "suggested_stack": ["react", "zig", "fastapi", "traefik"],
        "risk": "moderate" if score < 0.8 else "low",
    }

    try:
        advice = await generate_stack_advice(payload, score)
        result["suggested_stack"] = advice["suggested_stack"]
        result["llm_summary"] = advice["summary"]
        result["llm_model"] = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    except (httpx.HTTPError, ValueError):
        OLLAMA_REQUEST_COUNTER.labels(status="error", endpoint="/predict").inc()

    return JSONResponse(result)


@app.post("/analyze-site")
async def analyze_site(payload: SiteAnalysisRequest) -> JSONResponse:
    REQUEST_COUNTER.labels(endpoint="/analyze-site").inc()

    heuristic = heuristic_site_analysis(payload)
    try:
        analyzed = await analyze_site_with_ollama(payload)
    except (httpx.HTTPError, ValueError):
        OLLAMA_REQUEST_COUNTER.labels(status="error", endpoint="/analyze-site").inc()
        analyzed = heuristic

    return JSONResponse(analyzed.model_dump())


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
