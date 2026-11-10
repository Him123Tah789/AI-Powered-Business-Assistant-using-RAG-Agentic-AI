import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.api_client import api_client
from app.agent.chatbot_agent import chatbot_agent
from app.rag.policy_engine import policy_engine
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user message to process")
    auth_token: Optional[str] = Field(None, description="Bearer access token for passenger API")
    user_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Session user context and permissions")
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Recent conversation turns")

class LoginRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    company_id: Optional[str] = None

@router.post("/api/chat")
async def chat_endpoint(payload: ChatRequest):
    """
    Main Chat interaction endpoint combining RAG, Agentic tool execution,
    and security authorization checks.
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # If no token is provided, attempt auto-login with default credentials for seamless UX
    token = payload.auth_token
    if not token:
        login_res = api_client.login()
        if login_res.get("success"):
            token = login_res.get("token")

    result = chatbot_agent.process_message(
        user_message=payload.message,
        conversation_history=payload.history,
        auth_token=token,
        user_context=payload.user_context
    )

    return {
        "success": True,
        "token_used": bool(token),
        **result
    }

@router.post("/api/auth/login")
async def login_endpoint(payload: LoginRequest):
    """
    Authenticates with the existing Passenger REST API.
    """
    res = api_client.login(
        email=payload.email,
        password=payload.password,
        company_id=payload.company_id
    )
    if not res.get("success"):
        raise HTTPException(status_code=401, detail=res.get("error", "Login failed"))
    return res

@router.get("/api/auth/profile")
async def profile_endpoint(token: Optional[str] = None):
    """
    Directly retrieves the authenticated user's profile.
    """
    active_token = token
    if not active_token:
        login_res = api_client.login()
        active_token = login_res.get("token")

    if not active_token:
        raise HTTPException(status_code=401, detail="No valid authentication token available.")

    res = api_client.get_profile(active_token)
    if not res.get("success"):
        raise HTTPException(status_code=res.get("status_code", 400), detail=res.get("error"))
    return res

@router.get("/api/policy/info")
async def policy_info():
    """
    Returns metadata about the indexed policy document.
    """
    if not policy_engine.is_initialized:
        policy_engine.initialize()
    return {
        "document": "service_policy.pdf",
        "policy_reference": "SRV-POL-001",
        "effective_date": "01 January 2026",
        "owner": "Business Operations Department",
        "total_chunks_indexed": len(policy_engine.vector_store.chunks),
        "is_ready": policy_engine.is_initialized
    }

@router.get("/api/health")
async def health_check():
    """
    Health check endpoint reporting system state.
    """
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "model": settings.GEMINI_MODEL,
        "passenger_api": settings.PASSENGER_API_BASE_URL,
        "policy_engine_initialized": policy_engine.is_initialized
    }
