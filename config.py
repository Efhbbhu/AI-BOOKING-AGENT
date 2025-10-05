# Environment validation and configuration management
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class ConfigurationError(Exception):
    """Raised when configuration is invalid"""
    pass

class Config:
    """Application configuration management"""
    
    def __init__(self):
        load_dotenv()
        self._validate_required_env_vars()
    
    def _validate_required_env_vars(self):
        """Validate that all required environment variables are set"""
        required_vars = [
            'GROQ_API_KEY',
            'FIREBASE_PROJECT_ID',
            'FIREBASE_SERVICE_ACCOUNT'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
    
    @property
    def groq_api_key(self) -> str:
        return os.getenv('GROQ_API_KEY')
    
    @property
    def groq_api_url(self) -> str:
        return os.getenv('GROQ_API_URL', 'https://api.groq.com/openai/v1/chat/completions')
    
    @property
    def firebase_project_id(self) -> str:
        return os.getenv('FIREBASE_PROJECT_ID')
    
    @property
    def firebase_service_account(self) -> str:
        return os.getenv('FIREBASE_SERVICE_ACCOUNT')
    
    @property
    def flask_env(self) -> str:
        return os.getenv('FLASK_ENV', 'production')
    
    @property
    def flask_debug(self) -> bool:
        return os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    @property
    def port(self) -> int:
        return int(os.getenv('PORT', 8080))
    
    @property
    def sender_email(self) -> Optional[str]:
        return os.getenv('SENDER_EMAIL')
    
    @property
    def sender_password(self) -> Optional[str]:
        return os.getenv('SENDER_PASSWORD')

# Global config instance
config = Config()