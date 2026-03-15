from contextlib import asynccontextmanager
import os
import time

from fastapi import FastAPI
from pydantic import BaseModel
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
START_TIME = time.time()


class PredictionRequest(BaseModel):
    team_name: str
    dataset_rows: int
    urgency: str = "normal"


def configure_tracing() -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return

    resource = Resource.create({"service.name": "ml-service"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_tracing()
    yield


app = FastAPI(title="Hackathon ML Service", version="0.1.0", lifespan=lifespan)
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
    return JSONResponse(result)


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
