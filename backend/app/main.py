# main.py - AGORA AI Backend (FastAPI - 浼樺寲鐗?

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import asyncio

# 瀵煎叆閰嶇疆鍜屾ā鍧?
from .config import settings
from .utils.database import get_db, init_database, close_database
from .models import User, Debate, Agent, Speech, Score, AgentType, Side, DebateStatus, RefreshToken
from .services.auth import AuthManager, get_current_user
from .middleware import get_middleware
from .utils.logger import logger
from .utils.redis_client import redis_client
from .services.responses import ResponseBuilder, WSSpeechMessage, WSStatusMessage, WSScoreMessage
from .services.websocket_manager import ws_manager, heartbeat_manager
from .services.scoring import ScoreManager, generate_debate_scores
from .services.ai_adapters import initialize_adapters, AIAdapterFactory
from .services.debate_engine import DebateEngineManager

# ===== 搴旂敤鐢熷懡鍛ㄦ湡绠＄悊 =====


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting AGORA AI backend service...")

    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        msg = str(e)
        if "pg_type_typname_nsp_index" in msg or "duplicate key value violates unique constraint" in msg:
            logger.warning(f"Database init race detected, ignored: {e}")
        else:
            logger.error(f"Database init failed: {e}")
            raise

    try:
        await redis_client.init_pool()
        logger.info("Redis pool initialized")
    except Exception as e:
        logger.warning(f"Redis unavailable, cache features disabled: {e}")

    try:
        ai_config = {
            "deepseek": {"api_key": settings.DEEPSEEK_API_KEY, "model": settings.DEEPSEEK_MODEL},
        }
        if settings.OPENAI_API_KEY:
            ai_config["gpt-4"] = {"api_key": settings.OPENAI_API_KEY, "model": settings.OPENAI_MODEL}
        if settings.QWEN_API_KEY:
            ai_config["qwen"] = {"api_key": settings.QWEN_API_KEY, "model": settings.QWEN_MODEL}
        if settings.KIMI_API_KEY:
            ai_config["kimi"] = {"api_key": settings.KIMI_API_KEY, "model": settings.KIMI_MODEL}
        if settings.DOUBAO_API_KEY:
            ai_config["doubao"] = {"api_key": settings.DOUBAO_API_KEY, "model": settings.DOUBAO_MODEL}
        if settings.GEMINI_API_KEY:
            ai_config["gemini"] = {"api_key": settings.GEMINI_API_KEY, "model": settings.GEMINI_MODEL}
        if settings.GLM_API_KEY:
            ai_config["glm"] = {"api_key": settings.GLM_API_KEY, "model": settings.GLM_MODEL}

        await initialize_adapters(ai_config)
        logger.info(f"AI adapters initialized, available models: {AIAdapterFactory.list_available_models()}")
    except Exception as e:
        logger.error(f"AI adapter initialization failed: {e}")

    await heartbeat_manager.start()
    logger.info("Heartbeat manager started")

    yield

    logger.info("Shutting down AGORA AI backend service...")

    async def _safe_shutdown(name: str, fn):
        try:
            await fn()
            logger.info(f"{name} shutdown completed")
        except asyncio.CancelledError:
            logger.info(f"{name} shutdown cancelled")
        except Exception as exc:
            logger.warning(f"{name} shutdown failed: {exc}")

    await _safe_shutdown("DebateEngine", DebateEngineManager.cleanup_all)
    await _safe_shutdown("AIAdapterFactory", AIAdapterFactory.close_all)
    await _safe_shutdown("HeartbeatManager", heartbeat_manager.stop)
    await _safe_shutdown("WebSocketManager", ws_manager.close_all_connections)
    await _safe_shutdown("Redis", redis_client.close)
    await _safe_shutdown("Database", close_database)
    logger.info("Service shutdown completed")


# ===== 鍒涘缓搴旂敤瀹炰緥 =====

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    middleware=get_middleware()
)

# 瀹夊叏璁よ瘉
security = HTTPBearer()


# ===== 璇锋眰鍜屽搷搴旀ā鍨?=====


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="閭")
    password: str = Field(..., min_length=6, max_length=100, description="瀵嗙爜")


class UserLogin(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="瀵嗙爜")


class TokenRefresh(BaseModel):
    refresh_token: str = Field(..., description="鍒锋柊浠ょ墝")


class DebateCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="杈╄鏍囬")


class DebateUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="杈╄鏍囬")


class AgentParams(BaseModel):
    aggression: int = Field(50, ge=0, le=100, description="Aggression")
    logic: int = Field(50, ge=0, le=100, description="Logic")
    rhetoric: int = Field(50, ge=0, le=100, description="淇緸鑳藉姏")
    emotional: int = Field(50, ge=0, le=100, description="鎯呮劅璇夋眰")


class AgentConfig(BaseModel):
    agent_type: AgentType = Field(..., description="瑙掕壊绫诲瀷")
    position: str = Field(..., description="浣嶇疆")
    side: Side = Field(..., description="绔嬪満")
    name: str = Field(..., min_length=1, max_length=100, description="瑙掕壊鍚嶇О")
    ai_model: str = Field(..., description="AI妯″瀷")
    gender: Optional[str] = Field(None, description="鎬у埆")
    age: Optional[int] = Field(None, ge=1, le=120, description="骞撮緞")
    job: Optional[str] = Field(None, max_length=100, description="鑱屼笟")
    income: Optional[str] = Field(None, max_length=50, description="鏀跺叆姘村钩")
    mbti: Optional[str] = Field(None, max_length=10, description="MBTI绫诲瀷")
    params: Optional[AgentParams] = Field(None, description="鎬ф牸鍙傛暟")


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    ai_model: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = Field(None, ge=1, le=120)
    job: Optional[str] = Field(None, max_length=100)
    income: Optional[str] = Field(None, max_length=50)
    mbti: Optional[str] = Field(None, max_length=10)
    params: Optional[AgentParams] = None


class PublicSpeechGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="Debate topic")
    phase: str = Field(..., min_length=1, max_length=100, description="Debate phase")
    side: str = Field("neutral", description="pro / con / neutral")
    max_words: int = Field(300, ge=100, le=3200, description="Max output words")
    instruction: Optional[str] = Field(None, max_length=2000, description="Extra generation instruction")
    reference: Optional[str] = Field(None, max_length=8000, description="Reference context, e.g. opponent speech")
    agent: dict[str, Any] = Field(default_factory=dict, description="Agent profile")


# ===== 宸ュ叿鍑芥暟 =====


def build_system_prompt(agent_config: dict) -> str:
    """Build a system prompt from agent configuration."""
    params = agent_config.get("params", {})
    if isinstance(params, AgentParams):
        params = params.model_dump()

    aggression = params.get("aggression", 50)
    logic = params.get("logic", 50)
    rhetoric = params.get("rhetoric", 50)
    emotional = params.get("emotional", 50)

    aggression_desc = "aggressive" if aggression > 70 else "gentle" if aggression < 30 else "balanced"
    logic_desc = "rigorous" if logic > 70 else "intuitive" if logic < 30 else "balanced"
    rhetoric_desc = "eloquent" if rhetoric > 70 else "plain" if rhetoric < 30 else "balanced"
    emotional_desc = "emotional" if emotional > 70 else "rational" if emotional < 30 else "balanced"

    return f"""You are {agent_config.get('name', 'Agent')}, a {agent_config.get('age', 'unknown')}-year-old {agent_config.get('gender', 'unknown')}.
Profession: {agent_config.get('job', 'unknown')}
MBTI: {agent_config.get('mbti', 'INTJ')}
Income: {agent_config.get('income', 'middle')}

Personality profile:
- Aggression: {aggression}/100 ({aggression_desc})
- Logic: {logic}/100 ({logic_desc})
- Rhetoric: {rhetoric}/100 ({rhetoric_desc})
- Emotional appeal: {emotional}/100 ({emotional_desc})

Stay in character and keep your speaking style consistent with this profile."""


def duration_to_words(duration_seconds: int) -> int:
    """Convert duration (seconds) to target word count."""
    minutes = duration_seconds / 60
    return int(minutes * 225)


# ===== 杈╄娴佺▼瀹氫箟 =====

DEBATE_STEPS = [
    {"phase": "opening_statement", "speaker": "pro-1", "duration": 180, "side": "pro"},
    {"phase": "opening_statement", "speaker": "con-1", "duration": 180, "side": "con"},
    {"phase": "鏀昏京鐜妭", "speaker": "pro-2", "duration": 120, "side": "pro", "target": "con"},
    {"phase": "鏀昏京鐜妭", "speaker": "con-2", "duration": 120, "side": "con", "target": "pro"},
    {"phase": "鏀昏京鐜妭", "speaker": "pro-3", "duration": 120, "side": "pro", "target": "con"},
    {"phase": "鏀昏京鐜妭", "speaker": "con-3", "duration": 120, "side": "con", "target": "pro"},
    {"phase": "鏀昏京灏忕粨", "speaker": "pro-1", "duration": 120, "side": "pro"},
    {"phase": "鏀昏京灏忕粨", "speaker": "con-1", "duration": 120, "side": "con"},
    {"phase": "鑷敱杈╄", "speaker": "free", "duration": 300, "side": "both"},
    {"phase": "鎬荤粨闄堣瘝", "speaker": "con-4", "duration": 240, "side": "con"},
    {"phase": "鎬荤粨闄堣瘝", "speaker": "pro-4", "duration": 240, "side": "pro"},
    {"phase": "璇勫鎵撳垎", "speaker": "judges", "duration": 0, "side": "neutral"}
]


# ===== 鍩虹璺敱 =====


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/health")
async def api_health_check():
    return {"status": "healthy"}


@app.post("/api/public/generate-speech")
async def public_generate_speech(data: PublicSpeechGenerateRequest):
    """
    Generate one real speech using configured AI adapters.
    This endpoint is intentionally unauthenticated for local frontend runtime.
    """
    try:
        agent_profile = data.agent or {}
        params = agent_profile.get("params", {})
        if isinstance(params, AgentParams):
            params = params.model_dump()

        agent_config: dict[str, Any] = {
            "name": agent_profile.get("name", "Debater"),
            "side": data.side or agent_profile.get("side", "neutral"),
            "gender": agent_profile.get("gender", "unknown"),
            "age": agent_profile.get("age", 30),
            "job": agent_profile.get("job", "debater"),
            "income": agent_profile.get("income", "middle"),
            "mbti": agent_profile.get("mbti", "INTJ"),
            "params": params or {
                "aggression": 50,
                "logic": 50,
                "rhetoric": 50,
                "emotional": 50,
            },
        }
        agent_config["system_prompt"] = build_system_prompt(agent_config)

        model_name = str(agent_profile.get("aiModel") or agent_profile.get("ai_model") or "").strip()
        model_candidates: list[str] = []
        if model_name:
            model_candidates.append(model_name)
        model_candidates.extend([m for m in AIAdapterFactory.list_available_models() if m not in model_candidates])

        context_payload = {
            "topic": data.topic,
            "phase": data.phase,
            "side": data.side,
            "instruction": data.instruction or "",
            "reference": data.reference or "",
            "constraints": [
                "禁止套话、寒暄、敬语堆砌。",
                "结论必须配论据，至少包含一个可核验信息点。",
                "存在参考发言时必须正面回应其关键漏洞或证据。",
                "允许非常规切入与类比，不要固定句式。",
            ],
        }
        phase_text = (data.phase or "").lower()
        is_opening = ("立论" in phase_text) or ("opening" in phase_text)
        if ("自由" in phase_text) or ("free" in phase_text):
            temperature = 1.05
        elif ("盘问" in phase_text) or ("cross" in phase_text):
            temperature = 1.0
        elif ("总结" in phase_text) or ("summary" in phase_text):
            temperature = 0.9
        else:
            temperature = 0.95

        last_error: Optional[str] = None
        content: Optional[str] = None
        used_model: Optional[str] = None
        for candidate in model_candidates:
            try:
                adapter = await AIAdapterFactory.get_adapter(candidate)
                generated = await adapter.generate_speech(
                    agent_config=agent_config,
                    context=context_payload,
                    max_words=data.max_words,
                    temperature=temperature,
                )
                if generated and generated.strip():
                    content = generated.strip()
                    if is_opening and len(content) < 900:
                        expand_context = {
                            **context_payload,
                            "instruction": (context_payload.get("instruction") or "")
                            + "\n当前立论过短，请扩写为完整长篇立论：至少1200字，按“定义与判准-核心论证-证据链-预判反驳-阶段结论”展开。"
                        }
                        expanded = await adapter.generate_speech(
                            agent_config=agent_config,
                            context=expand_context,
                            max_words=max(1800, data.max_words),
                            temperature=max(temperature, 0.98),
                        )
                        if expanded and len(expanded.strip()) > len(content):
                            content = expanded.strip()
                    used_model = adapter.model
                    break
            except Exception as e:
                last_error = str(e)
                continue

        if not content:
            raise RuntimeError(last_error or "No model generated content")

        return ResponseBuilder.success(
            data={"content": content, "model": used_model},
            message="Speech generated",
        )
    except Exception as e:
        logger.error(f"Public speech generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech generation failed: {str(e)}",
        )


# ===== 璁よ瘉妯″潡 =====


@app.post("/api/auth/register")
async def register(user: UserRegister, session: AsyncSession = Depends(get_db)):
    """鐢ㄦ埛娉ㄥ唽"""
    # 妫€鏌ョ敤鎴峰悕鏄惁宸插瓨鍦?
    result = await session.execute(
        select(User).where(User.username == user.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="鐢ㄦ埛鍚嶅凡瀛樺湪"
        )

    # 妫€鏌ラ偖绠辨槸鍚﹀凡瀛樺湪
    result = await session.execute(
        select(User).where(User.email == user.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="閭宸茶浣跨敤"
        )

    # 鍒涘缓鏂扮敤鎴?
    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=AuthManager.hash_password(user.password)
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    # 鍒涘缓浠ょ墝
    access_token = AuthManager.create_access_token(new_user.id)
    refresh_token = AuthManager.create_refresh_token(new_user.id)

    # 淇濆瓨鍒锋柊浠ょ墝璁板綍
    await AuthManager.create_refresh_token_record(new_user.id, refresh_token, session)

    logger.info(f"鏂扮敤鎴锋敞鍐屾垚鍔? {user.username}")

    return ResponseBuilder.success(
        data={
            "user_id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "access_token": access_token,
            "refresh_token": refresh_token
        },
        message="娉ㄥ唽鎴愬姛"
    )


@app.post("/api/auth/login")
async def login(credentials: UserLogin, session: AsyncSession = Depends(get_db)):
    """鐢ㄦ埛鐧诲綍"""
    # 鏌ユ壘鐢ㄦ埛
    result = await session.execute(
        select(User).where(User.username == credentials.username)
    )
    user = result.scalar_one_or_none()

    if not user or not AuthManager.verify_password(credentials.password, user.password_hash):
        logger.warning(f"鐧诲綍澶辫触: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="鐢ㄦ埛鍚嶆垨瀵嗙爜閿欒"
        )

    # 鍒涘缓浠ょ墝
    access_token = AuthManager.create_access_token(user.id)
    refresh_token = AuthManager.create_refresh_token(user.id)

    # 淇濆瓨鍒锋柊浠ょ墝璁板綍
    await AuthManager.create_refresh_token_record(user.id, refresh_token, session)

    logger.info(f"鐢ㄦ埛鐧诲綍鎴愬姛: {user.username}")

    return ResponseBuilder.success(
        data={
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "access_token": access_token,
            "refresh_token": refresh_token
        },
        message="鐧诲綍鎴愬姛"
    )


@app.post("/api/auth/refresh")
async def refresh_tokens(
    data: TokenRefresh,
    session: AsyncSession = Depends(get_db)
):
    """鍒锋柊浠ょ墝"""
    try:
        access_token, refresh_token = await AuthManager.refresh_tokens(
            data.refresh_token,
            session
        )

        user = await AuthManager.verify_access_token(access_token, session)

        return ResponseBuilder.success(
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user_id": user.id
            },
            message="浠ょ墝鍒锋柊鎴愬姛"
        )
    except Exception as e:
        logger.error(f"浠ょ墝鍒锋柊澶辫触: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="浠ょ墝鍒锋柊澶辫触"
        )


@app.post("/api/auth/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
):
    """鐢ㄦ埛鐧诲嚭"""
    await AuthManager.logout(credentials.credentials, session=session)
    return ResponseBuilder.success(message="鐧诲嚭鎴愬姛")


@app.get("/api/auth/me")
async def get_current_user_info(
    user: User = Depends(get_current_user)
):
    """鑾峰彇褰撳墠鐢ㄦ埛淇℃伅"""
    return ResponseBuilder.success(
        data={
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat()
        }
    )


# ===== 杈╄绠＄悊妯″潡 =====


@app.post("/api/debates")
async def create_debate(
    debate: DebateCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鍒涘缓杈╄"""
    new_debate = Debate(
        user_id=user.id,
        title=debate.title,
        status=DebateStatus.DRAFT
    )
    session.add(new_debate)
    await session.commit()
    await session.refresh(new_debate)

    # 娓呴櫎鐩稿叧缂撳瓨
    await redis_client.delete(f"debates:user:{user.id}")

    logger.info(f"鐢ㄦ埛 {user.username} 鍒涘缓浜嗚京璁? {debate.title}")

    return ResponseBuilder.success(
        data={
            "debate_id": new_debate.id,
            "title": new_debate.title,
            "status": new_debate.status.value,
            "created_at": new_debate.created_at.isoformat()
        },
        message="杈╄鍒涘缓鎴愬姛"
    )


@app.get("/api/debates")
async def get_debates(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鑾峰彇鐢ㄦ埛鐨勮京璁哄垪琛?"""
    # 灏濊瘯浠庣紦瀛樿幏鍙?
    cache_key = f"debates:user:{user.id}"
    cached_data = await redis_client.get_json(cache_key)
    if cached_data:
        return ResponseBuilder.success(data=cached_data)

    # 浠庢暟鎹簱鏌ヨ
    result = await session.execute(
        select(Debate).where(Debate.user_id == user.id).order_by(Debate.created_at.desc())
    )
    debates = result.scalars().all()

    debates_data = [
        {
            "debate_id": d.id,
            "title": d.title,
            "status": d.status.value,
            "created_at": d.created_at.isoformat(),
            "started_at": d.started_at.isoformat() if d.started_at else None,
            "finished_at": d.finished_at.isoformat() if d.finished_at else None,
            "current_phase": d.current_phase,
            "current_step": d.current_step,
            "agents_count": len(d.agents)
        }
        for d in debates
    ]

    # 瀛樺叆缂撳瓨
    await redis_client.set_json(cache_key, debates_data)

    return ResponseBuilder.success(data=debates_data)


@app.get("/api/debates/{debate_id}")
async def get_debate(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鑾峰彇杈╄璇︽儏"""
    # 灏濊瘯浠庣紦瀛樿幏鍙?
    cache_key = f"debate:{debate_id}"
    cached_data = await redis_client.get_json(cache_key)
    if cached_data:
        return ResponseBuilder.success(data=cached_data)

    # 浠庢暟鎹簱鏌ヨ
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈璁块棶姝よ京璁鸿禌"
        )

    debate_data = {
        "debate_id": debate.id,
        "title": debate.title,
        "status": debate.status.value,
        "current_phase": debate.current_phase,
        "current_step": debate.current_step,
        "created_at": debate.created_at.isoformat(),
        "started_at": debate.started_at.isoformat() if debate.started_at else None,
        "finished_at": debate.finished_at.isoformat() if debate.finished_at else None,
        "agents": [
            {
                "agent_id": a.id,
                "position": a.position,
                "name": a.name,
                "agent_type": a.agent_type.value,
                "side": a.side.value if a.side else None,
                "initialized": a.initialized
            }
            for a in debate.agents
        ],
        "speeches_count": len(debate.speeches),
        "scores_count": len(debate.scores)
    }

    # 瀛樺叆缂撳瓨
    await redis_client.set_json(cache_key, debate_data)

    return ResponseBuilder.success(data=debate_data)


@app.put("/api/debates/{debate_id}")
async def update_debate(
    debate_id: int,
    update: DebateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鏇存柊杈╄"""
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈淇敼姝よ京璁鸿禌"
        )

    if update.title:
        debate.title = update.title

    await session.commit()

    # 娓呴櫎鐩稿叧缂撳瓨
    await redis_client.delete(f"debate:{debate_id}")
    await redis_client.delete(f"debates:user:{user.id}")

    return ResponseBuilder.success(
        data={
            "debate_id": debate_id,
            "title": debate.title
        },
        message="杈╄鏇存柊鎴愬姛"
    )


@app.delete("/api/debates/{debate_id}")
async def delete_debate(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鍒犻櫎杈╄"""
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鍒犻櫎姝よ京璁鸿禌"
        )

    await session.delete(debate)
    await session.commit()

    # 娓呴櫎鐩稿叧缂撳瓨
    await redis_client.delete(f"debate:{debate_id}")
    await redis_client.delete(f"debates:user:{user.id}")

    logger.info(f"鐢ㄦ埛 {user.username} 鍒犻櫎浜嗚京璁? {debate.title}")

    return ResponseBuilder.success(message="杈╄璧涘凡鍒犻櫎")


# ===== AI瑙掕壊閰嶇疆妯″潡 =====


@app.post("/api/debates/{debate_id}/agents")
async def create_agent(
    debate_id: int,
    agent: AgentConfig,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鍒涘缓AI瑙掕壊"""
    # 妫€鏌ヨ京璁烘槸鍚﹀瓨鍦?
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈閰嶇疆姝よ京璁鸿禌"
        )

    # 鍒涘缓瑙掕壊
    agent_dict = agent.model_dump()
    agent_dict["system_prompt"] = build_system_prompt(agent_dict)
    if agent_dict["params"]:
        agent_dict["params"] = agent_dict["params"].model_dump()

    new_agent = Agent(
        debate_id=debate_id,
        **agent_dict,
        initialized=True
    )
    session.add(new_agent)
    await session.commit()
    await session.refresh(new_agent)

    # 娓呴櫎鐩稿叧缂撳瓨
    await redis_client.delete(f"debate:{debate_id}")

    return ResponseBuilder.success(
        data={
            "agent_id": new_agent.id,
            "position": new_agent.position,
            "name": new_agent.name,
            "agent_type": new_agent.agent_type.value,
            "side": new_agent.side.value if new_agent.side else None,
            "initialized": True,
            "system_preview": new_agent.system_prompt[:100] + "..."
        },
        message="瑙掕壊鍒涘缓鎴愬姛"
    )


@app.put("/api/debates/{debate_id}/agents/{agent_id}")
async def update_agent(
    debate_id: int,
    agent_id: int,
    update: AgentUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鏇存柊AI瑙掕壊"""
    # 妫€鏌ヨ京璁?
    debate_result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = debate_result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈淇敼姝よ鑹?"
        )

    # 妫€鏌ヨ鑹?
    agent_result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.debate_id == debate_id)
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="瑙掕壊涓嶅瓨鍦?"
        )

    # 鏇存柊瀛楁
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "params" and value:
            value = value.model_dump()
        setattr(agent, field, value)

    # 閲嶆柊鐢熸垚绯荤粺鎻愮ず璇?
    agent_dict = agent.__dict__.copy()
    agent_dict["system_prompt"] = build_system_prompt(agent_dict)

    await session.commit()

    # 娓呴櫎鐩稿叧缂撳瓨
    await redis_client.delete(f"debate:{debate_id}")

    return ResponseBuilder.success(
        data={
            "agent_id": agent_id,
            "name": agent.name,
            "initialized": True
        },
        message="瑙掕壊鏇存柊鎴愬姛"
    )


@app.delete("/api/debates/{debate_id}/agents/{agent_id}")
async def delete_agent(
    debate_id: int,
    agent_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鍒犻櫎AI瑙掕壊"""
    # 妫€鏌ヨ京璁?
    debate_result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = debate_result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鍒犻櫎姝よ鑹?"
        )

    # 妫€鏌ヨ鑹?
    agent_result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.debate_id == debate_id)
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="瑙掕壊涓嶅瓨鍦?"
        )

    await session.delete(agent)
    await session.commit()

    # 娓呴櫎鐩稿叧缂撳瓨
    await redis_client.delete(f"debate:{debate_id}")

    return ResponseBuilder.success(message="瑙掕壊宸插垹闄?")


# ===== 杈╄鎵ц妯″潡 =====


@app.post("/api/debates/{debate_id}/start")
async def start_debate(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鍚姩杈╄"""
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鍚姩姝よ京璁鸿禌"
        )

    if len(debate.agents) < 14:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="瑙掕壊閰嶇疆鏈畬鎴?"
        )

    debate.status = DebateStatus.RUNNING
    debate.started_at = datetime.utcnow()
    debate.current_step = 0

    await session.commit()

    # 鍙戦€?WebSocket 閫氱煡
    await ws_manager.send_notification(
        debate_id,
        "debate_started",
        f"杈╄ '{debate.title}' 宸插紑濮?"
    )

    # 鍚姩杈╄寮曟搸
    try:
        await DebateEngineManager.start_debate(debate_id, session)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    logger.info(f"鐢ㄦ埛 {user.username} 鍚姩浜嗚京璁? {debate.title}")

    return ResponseBuilder.success(
        data={
            "debate_id": debate_id,
            "status": debate.status.value,
            "started_at": debate.started_at.isoformat()
        },
        message="杈╄宸插惎鍔?"
    )


@app.post("/api/debates/{debate_id}/pause")
async def pause_debate(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鏆傚仠杈╄"""
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鏆傚仠姝よ京璁鸿禌"
        )

    debate.status = DebateStatus.PAUSED
    await session.commit()

    # 鏆傚仠杈╄寮曟搸
    await DebateEngineManager.pause_debate(debate_id)

    # 鍙戦€?WebSocket 閫氱煡
    await ws_manager.send_notification(
        debate_id,
        "debate_paused",
        f"杈╄ '{debate.title}' 宸叉殏鍋?"
    )

    return ResponseBuilder.success(
        data={
            "debate_id": debate_id,
            "status": debate.status.value
        },
        message="杈╄宸叉殏鍋?"
    )


@app.post("/api/debates/{debate_id}/resume")
async def resume_debate(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鎭㈠杈╄"""
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈鎭㈠姝よ京璁鸿禌"
        )

    debate.status = DebateStatus.RUNNING
    await session.commit()

    # 鎭㈠杈╄寮曟搸
    await DebateEngineManager.resume_debate(debate_id)

    # 鍙戦€?WebSocket 閫氱煡
    await ws_manager.send_notification(
        debate_id,
        "debate_resumed",
        f"杈╄ '{debate.title}' 宸叉仮澶?"
    )

    return ResponseBuilder.success(
        data={
            "debate_id": debate_id,
            "status": debate.status.value
        },
        message="杈╄宸叉仮澶?"
    )


@app.post("/api/debates/{debate_id}/stop")
async def stop_debate(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """缁堟杈╄"""
    result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈缁堟姝よ京璁鸿禌"
        )

    debate.status = DebateStatus.FINISHED
    debate.finished_at = datetime.utcnow()
    await session.commit()

    # 鍋滄杈╄寮曟搸
    await DebateEngineManager.stop_debate(debate_id)
    await DebateEngineManager.remove_engine(debate_id)

    # 鍙戦€?WebSocket 閫氱煡
    await ws_manager.send_notification(
        debate_id,
        "debate_finished",
        f"杈╄ '{debate.title}' 宸茬粨鏉?"
    )

    logger.info(f"鐢ㄦ埛 {user.username} 缁堟浜嗚京璁? {debate.title}")

    return ResponseBuilder.success(
        data={
            "debate_id": debate_id,
            "status": debate.status.value,
            "finished_at": debate.finished_at.isoformat()
        },
        message="杈╄宸茬粨鏉?"
    )


# ===== 鍙戣█璁板綍妯″潡 =====


@app.get("/api/debates/{debate_id}/speeches")
async def get_speeches(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鑾峰彇鍙戣█璁板綍"""
    # 楠岃瘉杈╄鏉冮檺
    debate_result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = debate_result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈璁块棶姝よ京璁鸿禌"
        )

    # 灏濊瘯浠庣紦瀛樿幏鍙?
    cache_key = f"speeches:debate:{debate_id}"
    cached_data = await redis_client.get_json(cache_key)
    if cached_data:
        return ResponseBuilder.success(data=cached_data)

    # 浠庢暟鎹簱鏌ヨ
    result = await session.execute(
        select(Speech)
        .where(Speech.debate_id == debate_id)
        .order_by(Speech.created_at.asc())
    )
    speeches = result.scalars().all()

    speeches_data = [
        {
            "speech_id": s.id,
            "agent_id": s.agent_id,
            "phase": s.phase,
            "step_index": s.step_index,
            "side": s.side.value if s.side else None,
            "content": s.content,
            "duration": s.duration,
            "created_at": s.created_at.isoformat()
        }
        for s in speeches
    ]

    # 瀛樺叆缂撳瓨
    await redis_client.set_json(cache_key, speeches_data)

    return ResponseBuilder.success(data=speeches_data)


# ===== 璇勫垎妯″潡 =====


@app.get("/api/debates/{debate_id}/scores")
async def get_scores(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鑾峰彇杈╄璇勫垎"""
    # 楠岃瘉杈╄鏉冮檺
    debate_result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = debate_result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈璁块棶姝よ京璁鸿禌"
        )

    # 浠庢暟鎹簱鏌ヨ
    result = await session.execute(
        select(Score).where(Score.debate_id == debate_id)
    )
    scores = result.scalars().all()

    scores_data = [
        {
            "score_id": s.id,
            "judge_id": s.judge_id,
            "pro_score": s.pro_score,
            "con_score": s.con_score,
            "comments": s.comments,
            "created_at": s.created_at.isoformat()
        }
        for s in scores
    ]

    # 璁＄畻鎬诲垎鍜屽钩鍧囧垎
    if scores:
        pro_total = sum(s.pro_score for s in scores)
        con_total = sum(s.con_score for s in scores)
        pro_avg = round(pro_total / len(scores), 2)
        con_avg = round(con_total / len(scores), 2)
    else:
        pro_total = con_total = 0
        pro_avg = con_avg = 0

    # 纭畾鑾疯儨鏂?
    winner = "pro" if pro_avg > con_avg else "con" if con_avg > pro_avg else "draw"

    return ResponseBuilder.success(data={
        "scores": scores_data,
        "pro_total": pro_total,
        "con_total": con_total,
        "pro_avg": pro_avg,
        "con_avg": con_avg,
        "winner": winner,
        "judge_count": len(scores)
    })


@app.post("/api/debates/{debate_id}/scores/generate")
async def generate_scores(
    debate_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """鐢熸垚杈╄璇勫垎"""
    # 楠岃瘉杈╄鏉冮檺
    debate_result = await session.execute(
        select(Debate).where(Debate.id == debate_id)
    )
    debate = debate_result.scalar_one_or_none()

    if not debate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="杈╄璧涗笉瀛樺湪"
        )

    if debate.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="鏃犳潈璁块棶姝よ京璁鸿禌"
        )

    # 妫€鏌ヨ京璁烘槸鍚﹀凡缁撴潫
    if debate.status != DebateStatus.FINISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="璇峰厛缁撴潫杈╄鍐嶈繘琛岃瘎鍒?"
        )

    try:
        # 浣跨敤渚挎嵎鍑芥暟鐢熸垚璇勫垎
        result = await generate_debate_scores(debate_id, session)

        # 鍙戦€?WebSocket 閫氱煡
        await ws_manager.send_notification(
            debate_id,
            "scores_generated",
            f"杈╄ '{debate.title}' 璇勫垎宸茬敓鎴?"
        )

        logger.info(f"鐢ㄦ埛 {user.username} 涓鸿京璁?{debate.title} 鐢熸垚浜嗚瘎鍒?")

        return ResponseBuilder.success(
            data=result,
            message="璇勫垎鐢熸垚鎴愬姛"
        )
    except Exception as e:
        logger.error(f"璇勫垎鐢熸垚澶辫触: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"璇勫垎鐢熸垚澶辫触: {str(e)}"
        )


# ===== WebSocket 绔偣 =====


@app.websocket("/ws/debates/{debate_id}")
async def websocket_endpoint(websocket: WebSocket, debate_id: int):
    """WebSocket 杩炴帴绔偣"""
    # 鑾峰彇鐢ㄦ埛 ID锛堜粠鏌ヨ鍙傛暟鎴栦护鐗屼腑锛?
    token = websocket.query_params.get("token")
    user_id = None

    if token:
        try:
            payload = AuthManager.decode_token(token)
            user_id = payload.get("user_id")
        except:
            pass

    # 杩炴帴 WebSocket
    await ws_manager.connect(websocket, debate_id, user_id)

    try:
        while True:
            data = await websocket.receive_text()

            # 澶勭悊蹇冭烦
            if data == "ping":
                await websocket.send_text("pong")
                await heartbeat_manager.update(websocket, debate_id)

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, debate_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket 閿欒: {e}")
        await ws_manager.disconnect(websocket, debate_id, user_id)


# ===== 缁熻璺敱 =====


@app.get("/api/stats")
async def get_stats(session: AsyncSession = Depends(get_db)):
    """鑾峰彇绯荤粺缁熻淇℃伅"""
    # 鐢ㄦ埛鎬绘暟
    user_count_result = await session.execute(select(func.count(User.id)))
    user_count = user_count_result.scalar()

    # 杈╄鎬绘暟
    debate_count_result = await session.execute(select(func.count(Debate.id)))
    debate_count = debate_count_result.scalar()

    # 瑙掕壊鎬绘暟
    agent_count_result = await session.execute(select(func.count(Agent.id)))
    agent_count = agent_count_result.scalar()

    # 鍙戣█鎬绘暟
    speech_count_result = await session.execute(select(func.count(Speech.id)))
    speech_count = speech_count_result.scalar()

    return ResponseBuilder.success(
        data={
            "users": user_count,
            "debates": debate_count,
            "agents": agent_count,
            "speeches": speech_count
        }
    )


# ===== 鍚姩搴旂敤 =====

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )

