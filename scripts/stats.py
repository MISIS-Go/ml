from schemas import DayData

def generate_stats(data: DayData):
    total_duration = sum(a.duration for a in data.activities)
    category_counts = {}
    for a in data.activities:
        category_counts[a.category] = category_counts.get(a.category, 0) + a.duration
        
    return {
        "date": data.date,
        "total_minutes": total_duration,
        "categories": category_counts
    }
