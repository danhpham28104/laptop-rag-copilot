"""
config.py - Quản lý cấu hình và biến môi trường

Module này đọc tất cả các biến cấu hình từ file .env
và cung cấp một đối tượng Settings duy nhất cho toàn bộ ứng dụng.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Lớp cấu hình ứng dụng, tự động đọc từ file .env.
    Sử dụng Pydantic BaseSettings để validation tự động.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== API Keys =====
    # Chọn một trong hai provider: "gemini" hoặc "openai"
    llm_provider: str = "gemini"

    # Chọn provider cho Embedding: "local", "gemini", hoặc "openai"
    embedding_provider: str = "gemini"

    # Google Gemini API Key
    google_api_key: str = ""

    # OpenAI API Key (dùng khi llm_provider = "openai")
    openai_api_key: str = ""

    # ===== Model Configuration =====
    # Tên LLM model sẽ sử dụng
    llm_model_name: str = "gemini-2.0-flash"

    # Tên Embedding model sẽ sử dụng
    embedding_model_name: str = "models/text-embedding-004"

    # ===== Vector Database Configuration =====
    # Đường dẫn lưu trữ ChromaDB trên máy local
    chroma_db_path: str = "./chroma_db"

    # Tên collection trong ChromaDB
    chroma_collection_name: str = "laptops"

    # ===== Server Configuration =====
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # ===== Mock Configuration =====
    # Sử dụng Mock Embedding và Mock LLM (không gọi API ngoài)
    mock_embeddings: bool = False

    # ===== RAG Configuration =====
    # Số lượng sản phẩm tối đa lấy ra từ Vector Search
    top_k_results: int = 10

    # Số lượng sản phẩm tối đa trả về trong kết quả cuối cùng
    max_recommended_products: int = 5

    # Ngưỡng confidence score tối thiểu (0.0 - 1.0)
    min_confidence_threshold: float = 0.3

    # ===== CORS Configuration =====
    # Danh sách origins được phép (ngăn cách bằng dấu phẩy)
    allowed_origins: str = "http://localhost:8080,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Chuyển đổi chuỗi origins thành danh sách."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    Trả về instance Settings duy nhất (Singleton pattern).
    Sử dụng lru_cache để đảm bảo chỉ khởi tạo một lần.
    """
    return Settings()


# Instance toàn cục để import trực tiếp
settings = get_settings()
