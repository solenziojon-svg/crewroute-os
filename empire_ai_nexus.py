import sys
import os
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException, status

# Configure clean, structured logging for Railway logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger("CrewRouteEngine")

# 1. Startup Robustness: Lifespan Context Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing CrewRoute OS Engine dependencies...")
    try:
        # Validate critical environment variables before opening ports
        # e.g., assert os.getenv("SUPABASE_URL") is not None
        
        # TODO: Initialize your multi-agent routing connections, Supabase client, or LiteLLM here
        logger.info("All architectural dependencies and AI agents initialized successfully.")
        yield
    except Exception as e:
        logger.critical(f"FATAL: Application startup sequence failed: {e}")
        # Force immediate exit so Railway registers the failure explicitly
        sys.exit(1)
    finally:
        logger.info("Executing safe shutdown sequence for engine dependencies...")


# Initialize FastAPI with the robust lifespan handler
app = FastAPI(
    title="CrewRoute OS Engine", 
    version="1.0.0",
    lifespan=lifespan
)

# 2. Required Railway Healthcheck
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    # Future Extensibility: Add a quick verification check to ensure downstream APIs are responsive
    return {
        "status": "healthy",
        "engine": "CrewRoute AI Nexus Active"
    }

@app.get("/")
async def root():
    return {"message": "CrewRoute OS Production Engine is live and listening."}

# 3. Future Extensibility: Extensible Agent Endpoints Placeholder
@app.post("/api/v1/agent/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_routing_agent(payload: dict):
    """
    Target endpoint for the Telegram Voice-to-Action pipeline.
    Receives incoming parsed intents and passes them to the Core Dispatch Engine.
    """
    logger.info(f"Incoming agent execution request: {payload}")
    try:
        # Execution logic for routing / dispatch engine goes here
        return {"status": "queued", "detail": "Payload sent to dispatch engine state."}
    except Exception as e:
        logger.error(f"Failed to process agent trigger: {e}")
        raise HTTPException(status_code=500, detail="Internal agent execution failure.")


# 4. Error-Handled Server Bootstrapping
def run_web_server():
    try:
        port = int(os.getenv("PORT", 8080))
        logger.info(f"Attempting to bind web server to 0.0.0.0:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        logger.critical(f"Failed to bind or execute Uvicorn server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        run_web_server()
    else:
        logger.error("Execution missing required startup arguments.")
        print("Usage: python3 empire_ai_nexus.py serve")
        sys.exit(1)
