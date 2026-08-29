"""
database.py - Kết nối và quản lý ChromaDB Vector Database

Module này chịu trách nhiệm:
- Kết nối đến ChromaDB (lưu local)
- Khởi tạo Embedding Model (Gemini hoặc OpenAI)
- Thêm/cập nhật/xóa sản phẩm trong ChromaDB
- Truy vấn kết hợp Metadata Filtering + Vector Search
"""

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from config import settings
from schemas import ProductSyncRequest

logger = logging.getLogger(__name__)


# =============================================================================
# EMBEDDING MODEL FACTORY
# =============================================================================


def _create_embedding_model():
    """
    Factory function tạo Embedding Model dựa trên cấu hình provider.
    Hỗ trợ local, Gemini và OpenAI.
    """
    if settings.mock_embeddings:
        logger.info("Khởi tạo MOCK Embedding Model (dimension 768)...")
        class MockEmbeddings:
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 768 for _ in texts]
            def embed_query(self, text: str) -> list[float]:
                return [0.1] * 768
        return MockEmbeddings()

    provider = settings.embedding_provider.lower()

    if provider == "local":
        # Sử dụng Local HuggingFace / Sentence Transformers
        from langchain_huggingface import HuggingFaceEmbeddings
        logger.info(
            f"Khởi tạo Local Embedding: {settings.embedding_model_name}"
        )
        return HuggingFaceEmbeddings(
            model_name=settings.embedding_model_name,
        )

    elif provider == "gemini":
        # Sử dụng Google Gemini Embedding (text-embedding-004)
        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY chưa được cấu hình trong file .env "
                "khi sử dụng provider 'gemini'."
            )
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        logger.info(
            f"Khởi tạo Gemini Embedding: {settings.embedding_model_name}"
        )
        return GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model_name,
            google_api_key=settings.google_api_key,
        )

    elif provider == "openai":
        # Sử dụng OpenAI Embedding (text-embedding-3-small)
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY chưa được cấu hình trong file .env "
                "khi sử dụng provider 'openai'."
            )
        from langchain_openai import OpenAIEmbeddings

        logger.info(
            f"Khởi tạo OpenAI Embedding: {settings.embedding_model_name}"
        )
        return OpenAIEmbeddings(
            model=settings.embedding_model_name,
            api_key=settings.openai_api_key,
        )

    else:
        raise ValueError(
            f"Embedding Provider '{provider}' không được hỗ trợ. "
            "Chọn 'local', 'gemini' hoặc 'openai'."
        )


# =============================================================================
# CHROMA DATABASE MANAGER
# =============================================================================


class ChromaDBManager:
    """
    Quản lý kết nối và các thao tác với ChromaDB.

    Sử dụng Singleton pattern để đảm bảo chỉ có một kết nối DB
    trong suốt vòng đời ứng dụng.
    """

    _instance: Optional["ChromaDBManager"] = None

    def __new__(cls) -> "ChromaDBManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Tránh khởi tạo lại nếu đã tồn tại
        if self._initialized:
            return

        logger.info("Khởi tạo ChromaDB Manager...")

        # Tạo embedding model
        self.embedding_model = _create_embedding_model()

        # Tạo ChromaDB client với persistent storage
        self.chroma_client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Tạo LangChain Chroma wrapper để tích hợp dễ dàng
        self.vector_store = Chroma(
            client=self.chroma_client,
            collection_name=settings.chroma_collection_name,
            embedding_function=self.embedding_model,
            collection_metadata={"hnsw:space": "cosine"},
        )

        # Lấy raw collection để thực hiện các thao tác nâng cao
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Kiểm tra lệch dimension giữa DB hiện tại và embedding model
        try:
            # Lấy vector test từ embedding model để đo dimension mong muốn
            test_vector = self.embedding_model.embed_query("test")
            model_dimension = len(test_vector)

            # Thử lấy 1 sản phẩm có chứa embeddings trong DB
            existing_data = self.collection.get(limit=1, include=["embeddings"])
            if existing_data is not None:
                embeddings_list = existing_data.get("embeddings")
                if embeddings_list is not None and len(embeddings_list) > 0:
                    db_embedding = embeddings_list[0]
                    if db_embedding is not None and len(db_embedding) > 0:
                        db_dimension = len(db_embedding)
                        if db_dimension != model_dimension:
                            error_msg = (
                                f"\n[LỖI LỆCH DIMENSION VECTOR / VECTOR DIMENSION MISMATCH]\n"
                                f"ChromaDB collection '{settings.chroma_collection_name}' đang chứa các vector có dimension {db_dimension},\n"
                                f"nhưng model embedding được cấu hình '{settings.embedding_model_name}' ({settings.embedding_provider}) sinh ra vector có dimension {model_dimension}.\n"
                                f"Để khắc phục, vui lòng thực hiện:\n"
                                f"  1. Xóa thư mục cơ sở dữ liệu cũ: '{settings.chroma_db_path}' (ví dụ: xóa thư mục 'chroma_db' ở thư mục gốc project)\n"
                                f"  2. Khởi động lại server và chạy lại seed_data.py để rebuild dữ liệu với model mới.\n"
                            )
                            logger.critical(error_msg)
                            raise ValueError(error_msg)
            logger.info(f"Đã xác minh dimension embedding khớp thành công: {model_dimension}")
        except Exception as e:
            if isinstance(e, ValueError) and "LỖI LỆCH DIMENSION VECTOR" in str(e):
                raise e
            logger.warning(f"Không thể kiểm tra dimension: {e}")

        self._initialized = True
        logger.info(
            f"ChromaDB đã kết nối thành công. "
            f"Collection: '{settings.chroma_collection_name}', "
            f"Path: '{settings.chroma_db_path}'"
        )

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def upsert_product(self, product: ProductSyncRequest) -> bool:
        """
        Thêm hoặc cập nhật sản phẩm trong ChromaDB.

        Quy trình:
        1. Tạo văn bản mô tả từ thông tin sản phẩm
        2. Tạo embedding vector cho văn bản
        3. Lưu vector + metadata vào ChromaDB

        Args:
            product: Thông tin sản phẩm cần đồng bộ

        Returns:
            True nếu thành công, False nếu lỗi
        """
        try:
            # ID trong ChromaDB dùng định dạng string
            doc_id = f"product_{product.id}"

            # Tạo văn bản đại diện ngữ nghĩa của sản phẩm
            document_text = product.to_document_text()

            # Tạo metadata để lọc cứng
            metadata = product.to_metadata()

            logger.info(
                f"Đang upsert sản phẩm ID={product.id}: {product.name}"
            )

            # [P0-FIX] Tạo embedding tường minh bằng model đã cấu hình (Gemini/OpenAI)
            # Không để ChromaDB tự embed bằng default model (all-MiniLM-L6-v2)
            # vì sẽ gây embedding mismatch giữa upsert và query.
            embedding_vector = self.embedding_model.embed_documents([document_text])[0]

            # ChromaDB upsert: thêm mới hoặc cập nhật nếu ID đã tồn tại
            self.collection.upsert(
                ids=[doc_id],
                embeddings=[embedding_vector],   # ← truyền embedding tường minh
                documents=[document_text],
                metadatas=[metadata],
            )

            logger.info(f"Upsert sản phẩm ID={product.id} thành công.")
            return True

        except Exception as e:
            logger.error(
                f"Lỗi khi upsert sản phẩm ID={product.id}: {e}",
                exc_info=True,
            )
            return False

    def delete_product(self, product_id: int) -> bool:
        """
        Xóa sản phẩm khỏi ChromaDB theo product_id.

        Args:
            product_id: ID sản phẩm cần xóa

        Returns:
            True nếu thành công, False nếu lỗi
        """
        try:
            doc_id = f"product_{product_id}"
            logger.info(f"Đang xóa sản phẩm ID={product_id}...")

            self.collection.delete(ids=[doc_id])

            logger.info(f"Xóa sản phẩm ID={product_id} thành công.")
            return True

        except Exception as e:
            logger.error(
                f"Lỗi khi xóa sản phẩm ID={product_id}: {e}", exc_info=True
            )
            return False

    def get_product_count(self) -> int:
        """Trả về tổng số sản phẩm trong collection."""
        return self.collection.count()

    # -------------------------------------------------------------------------
    # Query Operations - Core của RAG Pipeline
    # -------------------------------------------------------------------------

    def query_with_filter(
        self,
        query_text: str,
        metadata_filter: Optional[dict] = None,
        n_results: int = 10,
    ) -> list[dict]:
        """
        Thực hiện truy vấn kết hợp Metadata Filtering + Vector Search.

        Đây là hàm cốt lõi của RAG Pipeline:
        - Bước 1 (Pre-filter): Lọc theo metadata để thu hẹp không gian tìm kiếm
        - Bước 2 (Vector Search): Tìm kiếm ngữ nghĩa trên tập đã lọc

        Args:
            query_text: Câu truy vấn ngữ nghĩa
            metadata_filter: Điều kiện lọc ChromaDB (where clause)
            n_results: Số kết quả tối đa cần lấy

        Returns:
            Danh sách dict chứa thông tin sản phẩm và độ tương đồng
        """
        try:
            # Kiểm tra collection có dữ liệu không
            total_products = self.collection.count()
            if total_products == 0:
                logger.warning("ChromaDB collection trống, không có dữ liệu.")
                return []

            # Giới hạn n_results không vượt quá tổng số sản phẩm
            n_results = min(n_results, total_products)

            logger.info(
                f"Truy vấn: '{query_text[:50]}...', "
                f"Filter: {metadata_filter}, "
                f"N={n_results}"
            )

            # [P0-FIX] Tạo query embedding tường minh bằng model đã cấu hình (Gemini/OpenAI)
            # Phải dùng embed_query() (không phải embed_documents()) vì query và document
            # đôi khi dùng instruction embedding khác nhau (ví dụ: Gemini task_type).
            query_embedding = self.embedding_model.embed_query(query_text)

            # Thực hiện query với hoặc không có filter
            query_kwargs = {
                "query_embeddings": [query_embedding],  # ← dùng embedding tường minh
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
            }

            if metadata_filter:
                query_kwargs["where"] = metadata_filter

            results = self.collection.query(**query_kwargs)

            # Chuyển đổi kết quả về định dạng thống nhất
            processed_results = []

            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    document = results["documents"][0][i]
                    # ChromaDB trả về distance (0=giống nhau, 2=khác nhau với cosine)
                    # Chuyển đổi distance thành similarity score (0-1)
                    distance = results["distances"][0][i]
                    similarity_score = max(0.0, 1.0 - (distance / 2.0))

                    processed_results.append(
                        {
                            "doc_id": doc_id,
                            "document": document,
                            "metadata": metadata,
                            "similarity_score": similarity_score,
                        }
                    )

            logger.info(
                f"Tìm thấy {len(processed_results)} kết quả sau khi query."
            )
            return processed_results

        except Exception as e:
            logger.error(f"Lỗi khi query ChromaDB: {e}", exc_info=True)
            return []

    def build_metadata_filter(self, parsed_criteria: dict) -> Optional[dict]:
        """
        Xây dựng điều kiện lọc ChromaDB từ các tiêu chí đã parse.

        ChromaDB hỗ trợ các toán tử: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
        Kết hợp với: $and, $or

        Args:
            parsed_criteria: Dict chứa các tiêu chí lọc

        Returns:
            Where clause cho ChromaDB, hoặc None nếu không có filter
        """
        conditions = []

        # Lọc theo thương hiệu (case-insensitive)
        if parsed_criteria.get("brand"):
            conditions.append(
                {"brand": {"$eq": parsed_criteria["brand"].lower()}}
            )

        # Lọc theo giá tối đa
        if parsed_criteria.get("max_price"):
            conditions.append(
                {"price": {"$lte": float(parsed_criteria["max_price"])}}
            )

        # Lọc theo giá tối thiểu
        if parsed_criteria.get("min_price"):
            conditions.append(
                {"price": {"$gte": float(parsed_criteria["min_price"])}}
            )

        # Lọc theo RAM tối thiểu
        if parsed_criteria.get("min_ram"):
            conditions.append(
                {"ram": {"$gte": int(parsed_criteria["min_ram"])}}
            )

        # Nếu không có điều kiện nào, trả về None (lấy tất cả)
        if not conditions:
            return None

        # Nếu chỉ có một điều kiện, không cần $and
        if len(conditions) == 1:
            return conditions[0]

        # Nhiều điều kiện: kết hợp bằng $and
        return {"$and": conditions}


# Singleton instance - sẽ được khởi tạo khi import lần đầu
_db_manager: Optional[ChromaDBManager] = None


def get_db_manager() -> ChromaDBManager:
    """
    Dependency injection function cho FastAPI.
    Trả về instance ChromaDBManager duy nhất.
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = ChromaDBManager()
    return _db_manager
