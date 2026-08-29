"""
main.py - FastAPI Application Entry Point

Định nghĩa tất cả các API endpoint:
- POST /api/chat         : Nhận câu hỏi và trả về JSON so sánh laptop
- POST /api/sync-product : Đồng bộ sản phẩm từ Spring Boot vào ChromaDB
- DELETE /api/sync-product/{id} : Xóa sản phẩm khỏi ChromaDB
- GET /health            : Health check endpoint
- GET /api/stats         : Thống kê hệ thống
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import ChromaDBManager, get_db_manager
from rag_service import RAGService
from schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    LLMStructuredOutput,
    ProductSyncRequest,
    SyncResponse,
    BulkSyncRequest,
    BulkSyncResponse,
    BulkSyncResultItem,
    ParsedQuery,
    SearchDebugResponse,
    SearchDebugCandidate,
    SearchDebugMetadata,
)

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# =============================================================================
# APPLICATION LIFECYCLE MANAGEMENT
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Quản lý vòng đời ứng dụng FastAPI.
    Code trước yield chạy khi khởi động,
    code sau yield chạy khi tắt.
    """
    logger.info("=" * 60)
    logger.info("🚀 Product-Comparison-RAG Microservice đang khởi động...")
    logger.info(f"   LLM Provider: {settings.llm_provider.capitalize()}")
    logger.info(f"   LLM Model: {settings.llm_model_name}")
    logger.info(f"   Embedding Provider: {settings.embedding_provider.lower()}")
    logger.info(f"   Embedding Model: {settings.embedding_model_name}")
    logger.info(f"   ChromaDB Path: {settings.chroma_db_path}")
    logger.info(f"   Server: {settings.host}:{settings.port}")
    logger.info("=" * 60)

    # Khởi tạo sẵn ChromaDB connection khi server bắt đầu
    # để tránh delay ở request đầu tiên
    try:
        db_manager = get_db_manager()
        total_products = db_manager.get_product_count()
        logger.info(
            f"✅ ChromaDB kết nối thành công. "
            f"Tổng sản phẩm: {total_products}"
        )
    except Exception as e:
        logger.error(f"❌ Lỗi khởi tạo ChromaDB: {e}")
        # Vẫn tiếp tục chạy, lỗi sẽ được xử lý ở request level

    logger.info("✅ Server sẵn sàng nhận request.")

    yield  # Ứng dụng đang chạy

    # Cleanup khi tắt
    logger.info("🛑 Server đang tắt...")


# =============================================================================
# FASTAPI APPLICATION INSTANCE
# =============================================================================

app = FastAPI(
    title="Product-Comparison-RAG API",
    description=(
        "Microservice tư vấn và so sánh Laptop sử dụng RAG (Retrieval-Augmented Generation). "
        "Tích hợp ChromaDB Vector Database và Google Gemini / OpenAI LLM."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# CORS - Cho phép Spring Boot và Frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# GZip compression để giảm kích thước response
app.add_middleware(GZipMiddleware, minimum_size=1000)


# =============================================================================
# DEPENDENCY INJECTION - RAG Service
# =============================================================================


def get_rag_service(
    db_manager: ChromaDBManager = Depends(get_db_manager),
) -> RAGService:
    """
    Dependency injection function cho RAGService.
    FastAPI sẽ tự động inject db_manager vào đây.
    """
    return RAGService(db_manager=db_manager)


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Xử lý HTTPException và trả về format chuẩn."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            status_code=exc.status_code,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Xử lý các lỗi không mong đợi."""
    logger.error(f"Lỗi không xử lý được: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Lỗi hệ thống nội bộ",
            detail=str(exc),
            status_code=500,
        ).model_dump(),
    )


# =============================================================================
# API ENDPOINTS
# =============================================================================


# ---- Health Check ----

@app.get(
    "/health",
    tags=["System"],
    summary="Health Check",
    description="Kiểm tra trạng thái hoạt động của server.",
)
async def health_check():
    """
    Endpoint kiểm tra sức khỏe của service.
    Spring Boot Actuator hoặc load balancer có thể gọi endpoint này.
    """
    return {
        "status": "healthy",
        "service": "Product-Comparison-RAG",
        "version": "1.0.0",
        "provider": settings.llm_provider,
        "llm_model": settings.llm_model_name,
    }


# ---- System Stats ----

@app.get(
    "/api/stats",
    tags=["System"],
    summary="Thống kê hệ thống",
    description="Thông tin về số lượng sản phẩm trong vector database.",
)
async def get_stats(
    db_manager: ChromaDBManager = Depends(get_db_manager),
):
    """Trả về thống kê về ChromaDB collection."""
    try:
        total_products = db_manager.get_product_count()
        return {
            "total_products_in_vector_db": total_products,
            "collection_name": settings.chroma_collection_name,
            "chroma_db_path": settings.chroma_db_path,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model_name,
            "embedding_model": settings.embedding_model_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy stats: {str(e)}")


# ---- ENDPOINT 1: Chat / So sánh Laptop ----

@app.post(
    "/api/chat",
    response_model=ChatResponse,
    response_model_by_alias=True,   # [P0-FIX] Serialize theo alias camelCase
    tags=["RAG"],
    summary="Tư vấn và so sánh Laptop",
    description=(
        "Nhận câu hỏi tự nhiên của người dùng, "
        "thực hiện RAG pipeline và trả về JSON có cấu trúc "
        "chứa văn bản so sánh, điểm tin cậy và danh sách sản phẩm đề xuất."
    ),
    responses={
        200: {
            "description": "Kết quả tư vấn thành công",
            "content": {
                "application/json": {
                    "example": {
                        "answer": "Dựa trên nhu cầu gaming của bạn với ngân sách 30 triệu...",
                        "confidenceScore": 0.85,
                        "citations": ["Thông số từ TechStore ID #12"],
                        "missingInformation": ["Bạn cần màn hình bao nhiêu inch?"],
                        "recommendedProducts": [
                            {
                                "id": 12,
                                "name": "Asus ROG Zephyrus G14",
                                "price": 29990000,
                                "url": "/product/12",
                                "imageUrl": "/images/asus-rog.jpg",
                                "reason": "Phù hợp gaming với RTX 4060",
                            }
                        ],
                    }
                }
            },
        },
        422: {"description": "Dữ liệu đầu vào không hợp lệ"},
        500: {"description": "Lỗi hệ thống nội bộ"},
    },
)
async def chat(
    request: ChatRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> ChatResponse:
    """
    Xử lý câu hỏi tư vấn laptop từ khách hàng.

    **Luồng xử lý:**
    1. Phân tích câu hỏi → trích xuất tiêu chí lọc
    2. Lọc sản phẩm theo Metadata trong ChromaDB
    3. Vector Search tìm sản phẩm tương đồng ngữ nghĩa
    4. Chấm điểm & xếp hạng lại (Re-ranking)
    5. Gọi LLM (Gemini/OpenAI) tạo câu trả lời JSON có cấu trúc
    """
    start_time = time.time()

    logger.info(
        f"[CHAT] Nhận request: '{request.message[:100]}' | "
        f"Session: {request.session_id}"
    )

    try:
        # Gọi RAG pipeline
        result: LLMStructuredOutput = rag_service.process_chat(request)

        # Chuyển đổi sang ChatResponse
        response = ChatResponse.from_llm_output(result)

        elapsed = time.time() - start_time
        logger.info(
            f"[CHAT] Hoàn thành trong {elapsed:.2f}s | "
            f"Confidence: {response.confidence_score} | "
            f"Sản phẩm: {len(response.recommended_products)}"
        )

        return response

    except ValueError as e:
        # Lỗi validation dữ liệu
        logger.warning(f"[CHAT] ValueError: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"[CHAT] Lỗi không mong đợi: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi xử lý chat: {str(e)}",
        )


# ---- ENDPOINT 2: Đồng bộ sản phẩm từ Spring Boot ----

@app.post(
    "/api/sync-product",
    response_model=SyncResponse,
    tags=["Sync"],
    summary="Đồng bộ sản phẩm vào Vector DB",
    description=(
        "Nhận thông tin sản phẩm từ Spring Boot và đồng bộ vào ChromaDB. "
        "Nếu sản phẩm đã tồn tại (cùng ID), sẽ cập nhật thay vì thêm mới."
    ),
    status_code=200,
    responses={
        200: {"description": "Đồng bộ sản phẩm thành công"},
        422: {"description": "Thông tin sản phẩm không hợp lệ"},
        500: {"description": "Lỗi khi lưu vào vector database"},
    },
)
async def sync_product(
    product: ProductSyncRequest,
    db_manager: ChromaDBManager = Depends(get_db_manager),
) -> SyncResponse:
    """
    Đồng bộ (thêm mới hoặc cập nhật) thông tin sản phẩm vào ChromaDB.

    **Quy trình:**
    1. Nhận thông tin sản phẩm từ Spring Boot (sau khi admin thêm/sửa sản phẩm)
    2. Tạo văn bản mô tả ngữ nghĩa và embedding vector
    3. Upsert vào ChromaDB (thêm mới hoặc ghi đè nếu ID đã tồn tại)
    """
    logger.info(
        f"[SYNC] Nhận yêu cầu sync sản phẩm ID={product.id}: {product.name}"
    )

    try:
        success = db_manager.upsert_product(product)

        if success:
            logger.info(f"[SYNC] Sync sản phẩm ID={product.id} thành công.")
            return SyncResponse(
                success=True,
                message=f"Đồng bộ sản phẩm '{product.name}' (ID={product.id}) thành công.",
                product_id=product.id,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi lưu sản phẩm ID={product.id} vào vector database.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[SYNC] Lỗi không mong đợi khi sync sản phẩm ID={product.id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi hệ thống khi đồng bộ sản phẩm: {str(e)}",
        )


# ---- ENDPOINT 3: Xóa sản phẩm khỏi Vector DB ----

@app.delete(
    "/api/sync-product/{product_id}",
    response_model=SyncResponse,
    tags=["Sync"],
    summary="Xóa sản phẩm khỏi Vector DB",
    description=(
        "Xóa thông tin sản phẩm khỏi ChromaDB khi sản phẩm bị xóa "
        "trên hệ thống Spring Boot chính."
    ),
    responses={
        200: {"description": "Xóa sản phẩm thành công"},
        404: {"description": "Sản phẩm không tồn tại trong vector DB"},
        500: {"description": "Lỗi khi xóa khỏi vector database"},
    },
)
async def delete_product(
    product_id: int = Path(
        ..., gt=0, description="ID sản phẩm cần xóa khỏi vector database"
    ),
    db_manager: ChromaDBManager = Depends(get_db_manager),
) -> SyncResponse:
    """
    Xóa sản phẩm khỏi ChromaDB.

    **Lưu ý:** Endpoint này nên được gọi từ Spring Boot mỗi khi
    admin xóa sản phẩm khỏi hệ thống chính.
    """
    logger.info(f"[DELETE] Nhận yêu cầu xóa sản phẩm ID={product_id}")

    try:
        # Kiểm tra sự tồn tại trong ChromaDB trước khi xóa
        doc_id = f"product_{product_id}"
        existing = db_manager.collection.get(ids=[doc_id])
        if not existing or not existing.get("ids"):
            raise HTTPException(
                status_code=404,
                detail=f"Sản phẩm ID={product_id} không tồn tại trong vector database.",
            )

        success = db_manager.delete_product(product_id)

        if success:
            logger.info(f"[DELETE] Xóa sản phẩm ID={product_id} thành công.")
            return SyncResponse(
                success=True,
                message=f"Đã xóa sản phẩm ID={product_id} khỏi vector database.",
                product_id=product_id,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi xóa sản phẩm ID={product_id}.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[DELETE] Lỗi không mong đợi khi xóa sản phẩm ID={product_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi hệ thống khi xóa sản phẩm: {str(e)}",
        )


# ---- ENDPOINT 4: Đồng bộ hàng loạt sản phẩm (Bulk Sync) ----

@app.post(
    "/api/sync-product/bulk",
    response_model=BulkSyncResponse,
    response_model_by_alias=True,
    tags=["Sync"],
    summary="Đồng bộ hàng loạt sản phẩm vào Vector DB",
    description="Đồng bộ nhiều sản phẩm cùng một lúc từ Spring Boot vào ChromaDB. Lỗi ở một sản phẩm không làm ảnh hưởng đến các sản phẩm khác.",
)
async def sync_product_bulk(
    request: BulkSyncRequest,
    db_manager: ChromaDBManager = Depends(get_db_manager),
) -> BulkSyncResponse:
    """
    Đồng bộ hàng loạt sản phẩm từ Spring Boot vào ChromaDB.
    Nếu một sản phẩm lỗi, các sản phẩm khác vẫn tiếp tục được xử lý.
    """
    logger.info(f"[BULK-SYNC] Nhận yêu cầu sync {len(request.products)} sản phẩm.")
    results = []
    success_count = 0
    failed_count = 0

    for prod in request.products:
        try:
            success = db_manager.upsert_product(prod)
            if success:
                results.append(
                    BulkSyncResultItem(
                        id=prod.id,
                        success=True,
                        message="Synced successfully",
                    )
                )
                success_count += 1
            else:
                results.append(
                    BulkSyncResultItem(
                        id=prod.id,
                        success=False,
                        message=f"Failed to sync product ID={prod.id} to ChromaDB",
                    )
                )
                failed_count += 1
        except Exception as e:
            logger.error(f"[BULK-SYNC] Lỗi khi sync sản phẩm ID={prod.id}: {e}")
            results.append(
                BulkSyncResultItem(
                    id=prod.id,
                    success=False,
                    message=str(e),
                )
            )
            failed_count += 1

    return BulkSyncResponse(
        success=True,
        total=len(request.products),
        successCount=success_count,
        failedCount=failed_count,
        results=results,
    )


# ---- ENDPOINT 5: Debug phân tích câu hỏi (Query Parser Debug) ----

@app.post(
    "/api/parse-query-debug",
    response_model=ParsedQuery,
    response_model_by_alias=True,
    tags=["Debug"],
    summary="Debug Query Parser",
    description="Nhận ChatRequest và trả về kết quả phân tích câu hỏi (ParsedQuery) dạng camelCase.",
)
async def parse_query_debug(
    request: ChatRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> ParsedQuery:
    """Trả về kết quả phân tích câu hỏi dạng cấu trúc để debug."""
    logger.info(f"[DEBUG-PARSE] Nhận request: '{request.message[:100]}'")
    try:
        parsed_query = rag_service.query_parser.parse(request.message)
        return parsed_query
    except Exception as e:
        logger.error(f"[DEBUG-PARSE] Lỗi: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi phân tích câu hỏi: {str(e)}",
        )


# ---- ENDPOINT 6: Debug tìm kiếm và xếp hạng (Search & Scoring Debug) ----

@app.post(
    "/api/search-debug",
    response_model=SearchDebugResponse,
    response_model_by_alias=True,
    tags=["Debug"],
    summary="Debug Vector Search & Scoring",
    description="Trả về thông tin chi tiết về quá trình truy vấn ChromaDB và tính điểm của các laptop ứng viên.",
)
async def search_debug(
    request: ChatRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> SearchDebugResponse:
    """Trả về chi tiết các ứng viên và điểm số để debug tại sao laptop A xếp cao hơn laptop B."""
    logger.info(f"[DEBUG-SEARCH] Nhận request: '{request.message[:100]}'")
    try:
        user_query = request.message
        
        # 1. Parse query
        parsed_query = rag_service.query_parser.parse(user_query)
        
        # 2. Metadata filter
        metadata_filter = rag_service.db_manager.build_metadata_filter(
            {
                "brand": parsed_query.brand,
                "max_price": parsed_query.max_price,
                "min_price": parsed_query.min_price,
                "min_ram": parsed_query.min_ram,
            }
        )
        logger.info(f"[DEBUG-SEARCH] Metadata filter: {metadata_filter}")
        
        # 3. Query ChromaDB
        n_results = min(
            settings.top_k_results * 2,
            50,
        )
        candidates = rag_service.db_manager.query_with_filter(
            query_text=parsed_query.semantic_query,
            metadata_filter=metadata_filter,
            n_results=n_results,
        )
        
        # Fallback if filtered results are empty
        if not candidates and metadata_filter:
            logger.info("[DEBUG-SEARCH] Không tìm thấy kết quả với filter, thử lại không có filter...")
            candidates = rag_service.db_manager.query_with_filter(
                query_text=parsed_query.semantic_query,
                metadata_filter=None,
                n_results=settings.top_k_results,
            )
            
        # 4. Score candidates
        ranked_products = rag_service.scoring_engine.score_candidates(
            candidates=candidates,
            parsed_query=parsed_query,
        )
        
        # 5. Build response objects
        debug_candidates = []
        for d in ranked_products:
            meta = d.get("metadata", {})
            metadata_obj = SearchDebugMetadata(
                productId=meta.get("product_id"),
                name=meta.get("name"),
                brand=meta.get("brand"),
                price=meta.get("price"),
                ram=meta.get("ram"),
                cpu=meta.get("cpu"),
                gpu=meta.get("gpu", ""),
                storage=meta.get("storage"),
                screenSize=meta.get("screen_size", 0.0),
                weight=meta.get("weight", 0.0),
                url=meta.get("url", ""),
                imageUrl=meta.get("image_url", ""),
                isHot=meta.get("is_hot", False),
                useCaseTags=meta.get("use_case_tags", ""),
                stock=meta.get("stock", 0),
                category=meta.get("category", ""),
                inStock=meta.get("in_stock", meta.get("stock", 0) > 0),
            )
            debug_candidates.append(
                SearchDebugCandidate(
                    docId=d.get("doc_id"),
                    document=d.get("document", ""),
                    similarityScore=d.get("similarity_score", 0.0),
                    bonusScore=d.get("bonus_score", 0.0),
                    vectorScore=d.get("vector_score", 0.0),
                    totalScore=d.get("total_score", 0.0),
                    scoreDetails=d.get("score_details", []),
                    metadata=metadata_obj,
                )
            )
            
        return SearchDebugResponse(
            parsedQuery=parsed_query,
            metadataFilter=metadata_filter,
            candidateCount=len(debug_candidates),
            candidates=debug_candidates,
        )
        
    except Exception as e:
        logger.error(f"[DEBUG-SEARCH] Lỗi: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi debug search: {str(e)}",
        )


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        access_log=True,
    )
