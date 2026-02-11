from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    solana_network: str = "devnet"
    rpc_url: str = "https://api.devnet.solana.com"
    wallet_path: str = "./wallet.json"
    spread_percentage: float = 0.5
    order_size: float = 0.1
    min_balance: float = 1.0
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra env vars used by other modules via os.getenv()


settings = Settings()
