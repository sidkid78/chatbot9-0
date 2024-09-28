# flake8: noqa: E402
import sys
import os

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from app.config import DATA_DIR

load_dotenv()

import logging
import uvicorn
from app.api.routers.chat import chat_router
from app.api.routers.chat_config import config_router
from app.api.routers.upload import file_upload_router
from app.observability import init_observability
from app.settings import init_settings
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.engine.engine import get_chat_engine
from pydantic import BaseModel 

app = FastAPI()

init_settings()
init_observability()

environment = os.getenv("ENVIRONMENT", "dev")  # Default to 'development' if not set
logger = logging.getLogger("uvicorn")

if environment == "dev":
    logger.warning("Running in development mode - allowing CORS for all origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
chat_engine = get_chat_engine()

class ChatMessage(BaseModel):
    content: str
    
@app.post('/api/chat')
async def chat(message: ChatMessage):
    logger.info(f"Received message: {message.content}")
    try:
        response = chat_engine.chat(message.content)
        return {'content': str(response)}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Redirect to documentation page when accessing base URL
@app.get("/")
async def redirect_to_docs():
    return RedirectResponse(url="/docs")


def mount_static_files(directory, path):
    if os.path.exists(directory):
        logger.info(f"Mounting static files '{directory}' at '{path}'")
        app.mount(
            path,
            StaticFiles(directory=directory, check_dir=False),
            name=f"{directory}-static",
        )


# Mount the data files to serve the file viewer
mount_static_files(DATA_DIR, "/api/files/data")
# Mount the output files from tools
mount_static_files("output", "/api/files/output")

app.include_router(chat_router, prefix="/api/chat")
app.include_router(config_router, prefix="/api/chat/config")
app.include_router(file_upload_router, prefix="/api/chat/upload")

if environment == "production":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("FRONTEND_URL", "https://your-frontend-url.vercel.app")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if __name__ == "__main__":
    app_host = os.getenv("APP_HOST", "0.0.0.0")
    app_port = int(os.getenv("APP_PORT", "8000"))
    reload = True if environment == "dev" else False

    uvicorn.run(app="main:app", host=app_host, port=app_port, reload=reload)
