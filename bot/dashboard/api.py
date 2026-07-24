import time
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from bot.config import settings
from bot.database.manager import DatabaseManager

app = FastAPI(title="SafeNet Dashboard")
security = HTTPBearer()

db = DatabaseManager()


class LoginPayload(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class GuildSettings(BaseModel):
    guild_id: int
    automod_enabled: bool = True
    moderation_notifications: bool = True
    welcome_channel: Optional[int] = None


def create_access_token(subject: str, expires_in: int = 3600) -> str:
    payload = {
        "sub": subject,
        "exp": int(time.time()) + expires_in,
        "iss": "safenet-dashboard",
    }
    return jwt.encode(payload, settings.dashboard_secret, algorithm="HS256")


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.dashboard_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc
    return payload.get("sub")


@app.on_event("startup")
async def startup_event() -> None:
    await db.connect()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await db.close()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginPayload) -> TokenResponse:
    if payload.username != settings.dashboard_username or payload.password != settings.dashboard_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(payload.username)
    return TokenResponse(access_token=token, expires_in=3600)


@app.get("/guilds")
async def guilds(user: str = Depends(get_current_user)) -> List[Dict[str, Any]]:
    return [{"id": 0, "name": "SafeNet Demo Server", "permissions": ["moderate_members", "manage_roles"]}]


@app.get("/guilds/{guild_id}/moderation")
async def moderation_history(guild_id: int, user: str = Depends(get_current_user)) -> List[Dict[str, Any]]:
    return await db.get_documents("cases", {"guild_id": guild_id})


@app.get("/guilds/{guild_id}/automod")
async def automod_settings(guild_id: int, user: str = Depends(get_current_user)) -> GuildSettings:
    settings_doc = await db.find_one("settings", {"guild_id": guild_id})
    if not settings_doc:
        return GuildSettings(guild_id=guild_id)
    return GuildSettings(**settings_doc)


@app.get("/logs")
async def logs(user: str = Depends(get_current_user)) -> List[Dict[str, Any]]:
    return await db.get_documents("logs")


@app.get("/statistics")
async def statistics(user: str = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "uptime": int(time.time()),
        "guilds": 1,
        "active_members": 0,
        "cases": len(await db.get_documents("cases")),
    }


@app.get("/users/{user_id}")
async def user_profile(user_id: int, user: str = Depends(get_current_user)) -> Dict[str, Any]:
    return await db.find_one("users", {"user_id": user_id}) or {"user_id": user_id, "notes": []}
