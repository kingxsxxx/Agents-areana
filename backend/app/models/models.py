from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class AgentType(PyEnum):
    HOST = "host"
    DEBATER = "debater"
    JUDGE = "judge"


class Side(PyEnum):
    PRO = "pro"
    CON = "con"
    NEUTRAL = "neutral"


class DebateStatus(PyEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    debates = relationship("Debate", back_populates="user", cascade="all, delete-orphan")


class Debate(Base):
    __tablename__ = "debates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    status = Column(Enum(DebateStatus), default=DebateStatus.DRAFT, index=True)
    current_phase = Column(String(100))
    current_step = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="debates")
    agents = relationship("Agent", back_populates="debate", cascade="all, delete-orphan")
    speeches = relationship("Speech", back_populates="debate", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="debate", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    debate_id = Column(Integer, ForeignKey("debates.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_type = Column(Enum(AgentType), nullable=False)
    position = Column(String(20))
    side = Column(Enum(Side))
    name = Column(String(100), nullable=False)
    ai_model = Column(String(50), nullable=False)
    gender = Column(String(20))
    age = Column(Integer)
    job = Column(String(100))
    income = Column(String(50))
    mbti = Column(String(10))
    params = Column(JSON)
    system_prompt = Column(Text)
    initialized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    debate = relationship("Debate", back_populates="agents")
    speeches = relationship("Speech", back_populates="agent", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="agent", cascade="all, delete-orphan")


class Speech(Base):
    __tablename__ = "speeches"

    id = Column(Integer, primary_key=True, index=True)
    debate_id = Column(Integer, ForeignKey("debates.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    phase = Column(String(100), nullable=False)
    step_index = Column(Integer, nullable=False)
    side = Column(Enum(Side))
    content = Column(Text, nullable=False)
    duration = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    debate = relationship("Debate", back_populates="speeches")
    agent = relationship("Agent", back_populates="speeches")


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    debate_id = Column(Integer, ForeignKey("debates.id", ondelete="CASCADE"), nullable=False, index=True)
    judge_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    pro_score = Column(Integer, default=0)
    con_score = Column(Integer, default=0)
    comments = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    debate = relationship("Debate", back_populates="scores")
    agent = relationship("Agent", back_populates="scores")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
