import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    print(f"Chat Interface & API available at: http://localhost:{settings.PORT}")
    print(f"API Docs available at: http://localhost:{settings.PORT}/docs")
    print("=" * 60)
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)

