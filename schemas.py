from pydantic import BaseModel, Field

class SiteInput(BaseModel):
    site: str    = Field(..., example="youtube.com")
    minutes: int = Field(..., ge=0, example=47)

class AnalyzeRequest(BaseModel):
    sites: list[SiteInput]
    model_config = {
        "json_schema_extra": {
            "example": {
                "sites": [
                    {"site": "youtube.com",    "minutes": 47},
                    {"site": "github.com",     "minutes": 32},
                    {"site": "instagram.com",  "minutes": 28}
                ]
            }
        }
    }

class SiteResult(BaseModel):
    site:     str = Field(..., example="youtube.com")
    minutes:  int = Field(..., example=47)
    category: str = Field(..., example="развлечения")
    score:    int = Field(..., ge=1, le=10, example=4)

class AnalyzeResponse(BaseModel):
    summary:         str           = Field(..., example="День умеренно продуктивный")
    sites:           list[SiteResult]
    recommendations: list[str]     = Field(..., min_length=1, max_length=5)
