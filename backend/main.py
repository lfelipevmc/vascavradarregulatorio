"""
Radar Regulatório - Backend entrypoint.
Run with: python main.py
Or with uvicorn directly: uvicorn app.api.main:app --reload
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level="info",
    )
