# config.py - 搴旂敤閰嶇疆绠＄悊
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """搴旂敤閰嶇疆绫?- 浠?.env 鏂囦欢鍔犺浇閰嶇疆"""

    # Pydantic 浼氳嚜鍔ㄤ粠 .env 鏂囦欢鍔犺浇鐜鍙橀噺
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False  # 涓嶅尯鍒嗗ぇ灏忓啓
    }

    # ==================== 搴旂敤鍩虹閰嶇疆 ====================
    APP_NAME: str = "AGORA AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    # ==================== 鏈嶅姟鍣ㄩ厤缃?====================
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    WORKERS: int = 4
    LOG_LEVEL: str = "INFO"

    # ==================== 鏁版嵁搴撻厤缃?(PostgreSQL) ====================
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_USER: str = "agora_user"
    DB_PASSWORD: str = ""
    DB_NAME: str = "agora_ai"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    # ==================== Redis 閰嶇疆 ====================
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_POOL_SIZE: int = 10
    REDIS_CACHE_TTL: int = 3600
    REDIS_TOKEN_TTL: int = 604800

    # ==================== JWT 璁よ瘉閰嶇疆 ====================
    SECRET_KEY: str = "your-super-secret-jwt-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ==================== 璇锋眰闄愭祦閰嶇疆 ====================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60

    # ==================== CORS 閰嶇疆 ====================
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list = ["Content-Type", "Authorization", "X-Requested-With"]

    # ==================== 鏃ュ織閰嶇疆 ====================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/app/logs/app.log"
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "30 days"

    # ==================== WebSocket 閰嶇疆 ====================
    WS_MAX_CONNECTIONS: int = 1000
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_CONNECTION_TIMEOUT: int = 300

    # ==================== AI 妯″瀷閰嶇疆 ====================
    AI_REQUEST_TIMEOUT: int = 60
    AI_MAX_RETRIES: int = 3

    # ==================== AI 妯″瀷 API 瀵嗛挜 ====================
    # DeepSeek API
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # OpenAI API
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # 闃块噷閫氫箟鍗冮棶 API
    QWEN_API_KEY: str = ""
    QWEN_API_BASE: str = "https://dashscope.aliyuncs.com/api/v1"
    QWEN_MODEL: str = "qwen-turbo"

    # 鏈堜箣鏆楅潰 Kimi API
    KIMI_API_KEY: str = ""
    KIMI_API_BASE: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-k2-turbo-preview"

    # 瀛楄妭璺冲姩璞嗗寘 API
    DOUBAO_API_KEY: str = ""
    DOUBAO_API_BASE: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = ""

    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_API_BASE: str = "https://generativelanguage.googleapis.com/v1"
    GEMINI_MODEL: str = "gemini-pro"

    # 鏅鸿氨 GLM API
    GLM_API_KEY: str = ""
    GLM_API_BASE: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4.7"

    # ==================== 灞炴€ф柟娉?====================
    @property
    def database_url(self) -> str:
        """鐢熸垚鏁版嵁搴撹繛鎺?URL"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url(self) -> str:
        """鐢熸垚 Redis 杩炴帴 URL"""
        auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# 鍏ㄥ眬閰嶇疆瀹炰緥
settings = Settings()
