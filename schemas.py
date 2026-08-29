"""
schemas.py - Định nghĩa các Pydantic Model

Module này chứa tất cả các schema dữ liệu cho:
- API Request/Response
- Cấu trúc JSON đầu ra từ LLM (Structured Output)
- Dữ liệu sản phẩm đồng bộ từ Spring Boot
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# PRODUCT SCHEMAS - Dữ liệu sản phẩm
# =============================================================================


class ProductSyncRequest(BaseModel):
    """
    Schema cho request đồng bộ sản phẩm từ Spring Boot vào ChromaDB.
    Endpoint: POST /api/sync-product
    """

    id: int = Field(..., description="ID duy nhất của sản phẩm trong database chính")
    name: str = Field(..., description="Tên đầy đủ của laptop")
    brand: str = Field(..., description="Thương hiệu (Asus, Dell, HP, Lenovo, ...)")
    price: float = Field(..., gt=0, description="Giá bán (VND)")
    ram: int = Field(..., description="Dung lượng RAM (GB)")
    cpu: str = Field(..., description="Tên CPU (Intel Core i7-12700H, ...)")
    gpu: str = Field(default="", description="Tên GPU/Card đồ họa")
    storage: str = Field(..., description="Thông tin ổ cứng (512GB SSD, ...)")
    screen_size: Optional[float] = Field(
        default=None, alias="screenSize", description="Kích thước màn hình (inches)"
    )
    screen_resolution: Optional[str] = Field(
        default=None, alias="screenResolution", description="Độ phân giải màn hình (1920x1080, ...)"
    )
    battery_life: Optional[str] = Field(
        default=None, alias="batteryLife", description="Thời lượng pin ước tính"
    )
    weight: Optional[float] = Field(
        default=None, description="Trọng lượng máy (kg)"
    )
    operating_system: Optional[str] = Field(
        default=None, alias="operatingSystem", description="Hệ điều hành (Windows 11, macOS, ...)"
    )
    url: str = Field(default="", description="URL trang sản phẩm trên website chính")
    image_url: str = Field(default="", alias="imageUrl", description="URL ảnh đại diện sản phẩm")
    description: Optional[str] = Field(
        default=None, description="Mô tả chi tiết sản phẩm"
    )
    is_hot: bool = Field(
        default=False, alias="isHot", description="Sản phẩm có đang HOT/nổi bật không?"
    )
    use_case_tags: Optional[str] = Field(
        default=None,
        alias="useCaseTags",
        description="Tags dùng để phân loại mục đích sử dụng (gaming, office, design, ...)",
    )
    stock: int = Field(default=0, ge=0, description="Số lượng hàng trong kho")
    category: Optional[str] = Field(default=None, description="Danh mục sản phẩm")

    model_config = {"populate_by_name": True}

    def to_document_text(self) -> str:
        """
        Tạo văn bản mô tả đầy đủ để embedding vào Vector DB.
        Văn bản này đại diện cho ngữ nghĩa của sản phẩm.
        """
        parts = [
            f"Laptop {self.name} của thương hiệu {self.brand}.",
            f"Giá bán: {self.price:,.0f} VND.",
            f"Cấu hình: CPU {self.cpu}, RAM {self.ram}GB, Ổ cứng {self.storage}.",
        ]

        if self.gpu:
            parts.append(f"Card đồ họa: {self.gpu}.")

        if self.screen_size:
            screen_info = f"Màn hình {self.screen_size} inch"
            if self.screen_resolution:
                screen_info += f" độ phân giải {self.screen_resolution}"
            parts.append(screen_info + ".")

        if self.weight:
            parts.append(f"Trọng lượng {self.weight}kg.")

        if self.battery_life:
            parts.append(f"Pin: {self.battery_life}.")

        if self.operating_system:
            parts.append(f"Hệ điều hành: {self.operating_system}.")

        if self.use_case_tags:
            parts.append(f"Phù hợp cho: {self.use_case_tags}.")

        if self.description:
            parts.append(self.description)

        if self.is_hot:
            parts.append("Đây là sản phẩm bán chạy, được nhiều người dùng yêu thích.")

        return " ".join(parts)

    def to_metadata(self) -> dict:
        """
        Tạo dict metadata để lưu vào ChromaDB.
        Metadata dùng cho pre-filtering (lọc cứng).
        Lưu ý: ChromaDB chỉ hỗ trợ str, int, float, bool cho metadata.
        """
        return {
            "product_id": self.id,
            "name": self.name,
            "brand": self.brand.lower(),
            "price": float(self.price),
            "ram": self.ram,
            "cpu": self.cpu,
            "gpu": self.gpu or "",
            "storage": self.storage,
            "screen_size": self.screen_size or 0.0,
            "weight": self.weight or 0.0,
            "url": self.url,
            "image_url": self.image_url,
            "is_hot": self.is_hot,
            "use_case_tags": self.use_case_tags or "",
            "stock": self.stock,
            "category": self.category or "",
            "in_stock": self.stock > 0,
        }


# =============================================================================
# QUERY PARSING SCHEMAS - Phân tích câu hỏi
# =============================================================================


class ParsedQuery(BaseModel):
    """
    Kết quả phân tích câu hỏi tự nhiên của người dùng.
    Chứa cả tiêu chí lọc cứng, ý định ngữ nghĩa và chế độ so sánh/gợi ý.
    """

    # --- Tiêu chí lọc cứng (Hard Filters) ---
    max_price: Optional[float] = Field(
        default=None, alias="maxPrice", description="Giá tối đa người dùng muốn bỏ ra (VND)"
    )
    min_price: Optional[float] = Field(
        default=None, alias="minPrice", description="Giá tối thiểu (VND)"
    )
    brand: Optional[str] = Field(
        default=None, description="Thương hiệu yêu cầu (asus, dell, hp, ...)"
    )
    min_ram: Optional[int] = Field(
        default=None, alias="minRam", description="Dung lượng RAM tối thiểu (GB)"
    )
    cpu_keyword: Optional[str] = Field(
        default=None, alias="cpuKeyword", description="Từ khóa CPU (i7, ryzen 7, m2, ...)"
    )
    gpu_keyword: Optional[str] = Field(
        default=None, alias="gpuKeyword", description="Từ khóa GPU (rtx 4060, rx 6700m, ...)"
    )
    min_storage_gb: Optional[int] = Field(
        default=None, alias="minStorageGb", description="Dung lượng ổ cứng tối thiểu (GB)"
    )

    # --- Ý định ngữ nghĩa (Semantic Intent) ---
    semantic_query: str = Field(
        ...,
        alias="semanticQuery",
        description="Câu truy vấn ngữ nghĩa được tổng hợp để vector search",
    )
    use_case: Optional[str] = Field(
        default=None,
        alias="useCase",
        description="Mục đích sử dụng chính (gaming, office, design, student, ...)",
    )

    # --- Chế độ xử lý (Mode / Intent) ---
    mode: str = Field(
        default="recommendation",
        description="Chế độ xử lý: 'recommendation' (tư vấn/gợi ý) hoặc 'comparison' (so sánh cụ thể)",
    )
    comparison_products: list[str] = Field(
        default_factory=list,
        alias="comparisonProducts",
        description="Danh sách tên/model sản phẩm cần so sánh (chỉ dùng khi mode='comparison')",
    )

    # --- Debug ---
    raw_query: Optional[str] = Field(
        default=None,
        alias="rawQuery",
        description="Câu hỏi gốc của người dùng để debug",
    )

    model_config = {"populate_by_name": True}

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Đảm bảo mode chỉ có giá trị hợp lệ."""
        if v not in ("recommendation", "comparison"):
            return "recommendation"
        return v


# =============================================================================
# CHAT API SCHEMAS - Giao tiếp với client
# =============================================================================


class ChatRequest(BaseModel):
    """
    Schema cho request chat từ Spring Boot hoặc client.
    Endpoint: POST /api/chat
    """

    message: str = Field(
        ..., min_length=1, description="Câu hỏi/nhu cầu của người dùng"
    )
    session_id: Optional[str] = Field(
        default=None, description="ID phiên chat (tùy chọn, dùng cho context)"
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Số lượng sản phẩm tối đa cần trả về (mặc định theo config)",
    )


# =============================================================================
# LLM OUTPUT SCHEMAS - Cấu trúc JSON đầu ra từ LLM
# =============================================================================


class RecommendedProduct(BaseModel):
    """
    Thông tin một sản phẩm được đề xuất trong kết quả.
    Dùng trong mảng recommendedProducts của ChatResponse.
    """

    id: int = Field(..., description="ID sản phẩm trong database chính")
    name: str = Field(..., description="Tên đầy đủ của laptop")
    price: float = Field(..., description="Giá bán (VND)")
    url: str = Field(default="", description="URL trang sản phẩm")
    image_url: str = Field(
        default="",
        alias="imageUrl",
        description="URL ảnh đại diện",
    )
    reason: str = Field(
        ...,
        description="Lý do ngắn gọn tại sao laptop này phù hợp với nhu cầu",
    )

    model_config = {"populate_by_name": True}


class LLMStructuredOutput(BaseModel):
    """
    Schema cho Structured Output của LLM.
    LangChain sẽ ép LLM trả về đúng cấu trúc này.
    """

    answer: str = Field(
        ...,
        description="Văn bản so sánh và tư vấn chi tiết các laptop bằng tiếng Việt tự nhiên, khách quan",
    )
    confidence_score: float = Field(
        ...,
        alias="confidenceScore",
        ge=0.0,
        le=1.0,
        description="Điểm tin cậy của câu trả lời từ 0.0 đến 1.0",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Danh sách trích dẫn nguồn gốc thông tin sản phẩm",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        alias="missingInformation",
        description="Các thông tin quan trọng khách hàng chưa cung cấp",
    )
    recommended_products: list[RecommendedProduct] = Field(
        default_factory=list,
        alias="recommendedProducts",
        description="Danh sách sản phẩm được đề xuất theo thứ tự ưu tiên",
    )

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    """
    Schema cho response trả về từ endpoint /api/chat.
    Kết hợp structured output của LLM với metadata request.
    """

    answer: str
    confidence_score: float = Field(alias="confidenceScore")
    citations: list[str]
    missing_information: list[str] = Field(alias="missingInformation")
    recommended_products: list[RecommendedProduct] = Field(
        alias="recommendedProducts"
    )

    model_config = {"populate_by_name": True}

    @classmethod
    def from_llm_output(cls, llm_output: LLMStructuredOutput) -> "ChatResponse":
        """Tạo ChatResponse từ LLMStructuredOutput."""
        return cls(
            answer=llm_output.answer,
            confidenceScore=llm_output.confidence_score,
            citations=llm_output.citations,
            missingInformation=llm_output.missing_information,
            recommendedProducts=llm_output.recommended_products,
        )


# =============================================================================
# SYNC API SCHEMAS - Đồng bộ dữ liệu
# =============================================================================


class SyncResponse(BaseModel):
    """Response cho các endpoint đồng bộ sản phẩm."""

    success: bool
    message: str
    product_id: Optional[int] = None


class ErrorResponse(BaseModel):
    """Schema cho response lỗi chuẩn."""

    error: str
    detail: Optional[str] = None
    status_code: int


# =============================================================================
# BULK SYNC & DEBUG SCHEMAS - Spring Boot Integration & Debugging
# =============================================================================


class BulkSyncRequest(BaseModel):
    """
    Schema cho request đồng bộ hàng loạt sản phẩm từ Spring Boot.
    Endpoint: POST /api/sync-product/bulk
    """
    products: list[ProductSyncRequest] = Field(..., description="Danh sách sản phẩm cần đồng bộ")


class BulkSyncResultItem(BaseModel):
    """Kết quả đồng bộ của từng sản phẩm trong batch."""
    id: int
    success: bool
    message: str


class BulkSyncResponse(BaseModel):
    """Response trả về khi đồng bộ hàng loạt."""
    success: bool
    total: int
    success_count: int = Field(alias="successCount")
    failed_count: int = Field(alias="failedCount")
    results: list[BulkSyncResultItem]

    model_config = {"populate_by_name": True}


class SearchDebugMetadata(BaseModel):
    """Metadata của sản phẩm trong search debug response dạng camelCase."""
    product_id: int = Field(alias="productId")
    name: str
    brand: str
    price: float
    ram: int
    cpu: str
    gpu: str
    storage: str
    screen_size: float = Field(alias="screenSize")
    weight: float
    url: str
    image_url: str = Field(alias="imageUrl")
    is_hot: bool = Field(alias="isHot")
    use_case_tags: str = Field(alias="useCaseTags")
    stock: int = Field(default=0)
    category: str = Field(default="")
    in_stock: bool = Field(alias="inStock", default=False)

    model_config = {"populate_by_name": True}


class SearchDebugCandidate(BaseModel):
    """Thông tin chi tiết của một sản phẩm ứng viên trong kết quả vector search debug."""
    doc_id: str = Field(alias="docId")
    document: str
    similarity_score: float = Field(alias="similarityScore")
    bonus_score: float = Field(alias="bonusScore")
    vector_score: float = Field(alias="vectorScore")
    total_score: float = Field(alias="totalScore")
    score_details: list[str] = Field(alias="scoreDetails")
    metadata: SearchDebugMetadata

    model_config = {"populate_by_name": True}


class SearchDebugResponse(BaseModel):
    """Response trả về khi debug quá trình tìm kiếm và xếp hạng."""
    parsed_query: ParsedQuery = Field(alias="parsedQuery")
    metadata_filter: Optional[dict] = Field(alias="metadataFilter")
    candidate_count: int = Field(alias="candidateCount")
    candidates: list[SearchDebugCandidate]

    model_config = {"populate_by_name": True}
