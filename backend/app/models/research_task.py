from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class ResearchTask(Base):
    """Research task model"""
    __tablename__ = "research_tasks"
    
    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    prompt_hash = Column(String(64), nullable=False, index=True)
    agent = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    usage = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'prompt': self.prompt,
            'agent': self.agent,
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'usage': self.usage,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
