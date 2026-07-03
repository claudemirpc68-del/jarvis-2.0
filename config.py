"""
Módulo de configuração do JARVIS 2.0
Centraliza todas as configurações e credenciais
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    """Configuração do banco de dados (futuro)"""
    url: str = "sqlite:///jarvis.db"
    
@dataclass
class APIConfig:
    """Configuração das APIs"""
    groq_api_key: str
    telegram_token: str
    tavily_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None  # Mantido para compatibilidade
    openrouter_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    
@dataclass
class GoogleConfig:
    """Configuração das APIs Google"""
    credentials_path: str
    token_path: str
    scopes: list = None
    
    def __post_init__(self):
        if self.scopes is None:
            self.scopes = [
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/gmail.modify',
                'https://www.googleapis.com/auth/gmail.compose',
                'https://www.googleapis.com/auth/contacts.readonly',
                'https://www.googleapis.com/auth/calendar'
            ]

@dataclass
class ServerConfig:
    """Configuração do servidor"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    reload: bool = False

@dataclass
class LoggingConfig:
    """Configuração de logging"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None

class Config:
    """Classe de configuração principal"""
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = env_file
        self.load_config()
        
        # Sub-configurações
        self.database = DatabaseConfig()
        self.api = APIConfig(
            groq_api_key=self._get_env("GROQ_API_KEY"),
            telegram_token=self._get_env("TELEGRAM_TOKEN"),
            tavily_api_key=self._get_env("TAVILY_API_KEY", None),
            openai_api_key=self._get_env("OPENAI_API_KEY", None),  # Opcional para compatibilidade
            openrouter_api_key=self._get_env("OPENROUTER_API_KEY", None),
            gemini_api_key=self._get_env("GEMINI_API_KEY", None)
        )
        self.google = GoogleConfig(
            credentials_path=self._get_env("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
            token_path=self._get_env("GOOGLE_TOKEN_PATH", "token.json")
        )
        self.server = ServerConfig(
            host=self._get_env("HOST", "0.0.0.0"),
            port=int(self._get_env("PORT", "8000")),
            debug=self._get_env("DEBUG", "false").lower() == "true",
            reload=self._get_env("RELOAD", "false").lower() == "true"
        )
        self.logging = LoggingConfig(
            level=self._get_env("LOG_LEVEL", "INFO"),
            file=self._get_env("LOG_FILE", None)
        )
        self.user = {
            "id": self._get_env("USER_ID"),
            "name": self._get_env("USER_NAME", "Usuário")
        }
    
    _MISSING = object()

    def _get_env(self, key: str, default: Any = _MISSING) -> Any:
        """Obter valor de variável de ambiente"""
        value = os.getenv(key)
        if value is not None:
            return value
        if default is not self._MISSING:
            return default
        raise ValueError(f"Variável de ambiente {key} não encontrada")
    
    def load_config(self) -> None:
        """Carregar configurações do arquivo .env (sem sobrescrever variáveis de ambiente existentes)"""
        env_path = Path(self.env_file)
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        k = key.strip()
                        v = value.strip()
                        if k not in os.environ:
                            os.environ[k] = v
    
    def validate_config(self) -> bool:
        """Validar configurações"""
        required_keys = [
            "GROQ_API_KEY",
            "TELEGRAM_TOKEN",
            "GOOGLE_CREDENTIALS_PATH",
            "USER_ID"
        ]
        
        missing = []
        for key in required_keys:
            if not self._get_env(key):
                missing.append(key)
        
        if missing:
            print(f"❌ Configuração faltando: {', '.join(missing)}")
            return False
        
        # Verificar arquivos existentes
        if not Path(self.google.credentials_path).exists():
            print(f"❌ Arquivo não encontrado: {self.google.credentials_path}")
            return False
        
        return True
    
    def get_gmail_scopes(self) -> list:
        """Obter escopos do Gmail"""
        return self.google.scopes
    
    def get_user_id(self) -> str:
        """Obter ID do usuário"""
        return self.user["id"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converter configuração para dicionário"""
        return {
            "database": self.database.__dict__,
            "api": self.api.__dict__,
            "google": self.google.__dict__,
            "server": self.server.__dict__,
            "logging": self.logging.__dict__,
            "user": self.user
        }

# Instância global
config = Config()