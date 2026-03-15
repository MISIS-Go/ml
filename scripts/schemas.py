from pydantic import BaseModel
from typing import List, Optional

class Activity(BaseModel):
    name: str
    duration: int
    category: str

class DayData(BaseModel):
    date: str
    activities: List[Activity]
