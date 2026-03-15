import sys
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Добавляем путь к папке scripts для импорта существующих функций
sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts"))

# Попытка импорта из оригинальных файлов
try:
    from stats import daily_stats, weekly_report, generate_charts, save_report
    from schemas import DailyStats, WeeklyReport
except ImportError:
    # Заглушки для обеспечения работы роутов без изменения оригинальных файлов
    class DailyStats(BaseModel):
        date: str
        total_minutes: int
        categories: dict
    
    class WeeklyReport(BaseModel):
        period: str
        average_score: float
        recommendations: list[str]

    def daily_stats(date): return {"date": date, "total_minutes": 0, "categories": {}}
    def weekly_report(end_date): return {"period": "last 7 days", "average_score": 0.0, "recommendations": []}
    def generate_charts(report): pass
    def save_report(report): pass

router = APIRouter()

@router.get(
    "/daily/{date}",
    response_model=DailyStats,
    summary="Статистика за день",
    description="Возвращает статистику по конкретному дню. Формат: **YYYY-MM-DD**"
)
async def get_daily(date: str):
    try:
        return daily_stats(date)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Данные за {date} не найдены в папке history/"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/daily/today",
    response_model=DailyStats,
    summary="Статистика за сегодня"
)
async def get_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return await get_daily(today)

@router.get(
    "/weekly",
    response_model=WeeklyReport,
    summary="Недельный отчёт",
    description="Отчёт за последние 7 дней с разбивкой по категориям и графиками"
)
async def get_weekly(
    end_date: str = Query(
        default=None,
        description="Конечная дата периода (YYYY-MM-DD). По умолчанию — сегодня",
        example="2026-03-15"
    )
):
    try:
        report = weekly_report(end_date)
        save_report(report)
        generate_charts(report)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/charts/{filename}",
    summary="Получить график",
    description="Возвращает PNG-график. Доступные файлы: **weekly_scores.png**, **category_pie.png**"
)
async def get_chart(filename: str):
    charts_dir = Path(__file__).resolve().parents[2] / "output" / "charts"
    path = charts_dir / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"График {filename} не найден. Сначала вызови GET /stats/weekly"
        )
    return FileResponse(path, media_type="image/png")
