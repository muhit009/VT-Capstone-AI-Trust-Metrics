import uuid
from sqlalchemy import Column, String, Float, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from database import Base

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True)
    team_name = Column(String(100), index=True)
    role = Column(String(50))
    queries = relationship("Query", back_populates="user")

class Query(Base, TimestampMixin):
    __tablename__ = "queries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    prompt = Column(Text, nullable=False)
    model_name = Column(String(100), index=True)
    params = Column(JSONB) # Store temperature, top_p, etc.
    
    user = relationship("User", back_populates="queries")
    answers = relationship("Answer", back_populates="query")

class Answer(Base, TimestampMixin):
    __tablename__ = "answers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id"), nullable=False)
    generated_text = Column(Text, nullable=False)
    metadata_json = Column(JSONB)
    
    query = relationship("Query", back_populates="answers")
    signals = relationship("ConfidenceSignal", back_populates="answer")
    evidence = relationship("Evidence", back_populates="answer")
    decisions = relationship("Decision", back_populates="answer")

class ConfidenceSignal(Base, TimestampMixin):
    __tablename__ = "confidence_signals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_id = Column(UUID(as_uuid=True), ForeignKey("answers.id"), nullable=False)
    score = Column(Float, index=True)
    method = Column(String(100))
    explanation = Column(Text)
    
    answer = relationship("Answer", back_populates="signals")

class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_id = Column(UUID(as_uuid=True), ForeignKey("answers.id"), nullable=False)
    content = Column(Text)
    source_uri = Column(String(512))
    relevance_score = Column(Float)
    
    answer = relationship("Answer", back_populates="evidence")

class Decision(Base, TimestampMixin):
    __tablename__ = "decisions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_id = Column(UUID(as_uuid=True), ForeignKey("answers.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    status = Column(String(50)) # e.g., "approved", "flagged"
    rationale = Column(Text)
    
    answer = relationship("Answer", back_populates="decisions")