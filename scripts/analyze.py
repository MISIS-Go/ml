import httpx
import os
import json
from schemas import DayData

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

async def analyze_day_with_ollama(data: DayData):
    activities_str = "\n".join([f"- {a.name} ({a.duration} min, {a.category})" for a in data.activities])
    
    prompt = (
        f"You are a personal productivity coach. Analyze the following daily activities for {data.date}:\n"
        f"{activities_str}\n\n"
        "Provide 3 concise, actionable recommendations to improve work-life balance and productivity. "
        "Return the result as a JSON list of strings."
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            result = response.json().get("response", "[]")
            
            # Ollama returns a string, we need to parse it if it's JSON
            recommendations = json.loads(result)
            if isinstance(recommendations, dict) and "recommendations" in recommendations:
                return recommendations["recommendations"]
            return recommendations
    except Exception as e:
        print(f"Ollama Error: {e}")
        return ["Could not reach Ollama for AI recommendations. Check if it's running."]

# Fallback for sync calls if needed
def analyze_day_sync(data: DayData):
    # Simple rules as fallback
    return ["AI Analysis is pending... (Run watcher with async)"]
