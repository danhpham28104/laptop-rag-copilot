# Product-Comparison-RAG 🤖💻

Microservice **RAG (Retrieval-Augmented Generation)** cho hệ thống **Tư vấn và So sánh Laptop**, xây dựng bằng Python (FastAPI, ChromaDB, LangChain, Google Gemini / OpenAI). 

Giao tiếp với hệ thống Web chính (**Java Spring Boot**) qua REST API chuẩn JSON.

---

## 🏗️ Kiến trúc hệ thống

```
Spring Boot (Backend Web chính)
        │
        │ REST API (JSON - Support camelCase & snake_case)
        ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI RAG Microservice                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Query Parser         ← Phân tích câu hỏi tự nhiên  │  │
│  │ 2. Metadata Filter      ← Lọc cứng (giá/brand/RAM)    │  │
│  │ 3. Vector Search        ← Tìm kiếm ngữ nghĩa (Chroma) │  │
│  │ 4. Scoring Engine       ← Chấm điểm & Re-ranking      │  │
│  │ 5. LLM Generator        ← Tạo câu trả lời JSON        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ChromaDB (Vector Database Local)                           │
│  Gemini / OpenAI (LLM & Embedding Models)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Cấu trúc dự án

```
Product-Comparison-RAG/
├── config.py          # Quản lý cấu hình & biến môi trường (Pydantic BaseSettings)
├── database.py        # ChromaDB Manager, Embedding Factory, CRUD & Vector Query
├── schemas.py         # Pydantic Models (API Requests/Responses, LLM Output Schemas)
├── rag_service.py     # RAG Pipeline chính (Query Parser, Filter, Search, Scoring, LLM)
├── main.py            # FastAPI Application & API Endpoints (8 endpoints)
├── seed_data.py       # Script nạp 15 mẫu dữ liệu laptop vào ChromaDB
├── generate_pdf.py    # Script xuất báo cáo đặc tả kỹ thuật PDF (ReportLab)
├── requirements.txt   # Các thư viện Python phụ thuộc
├── .env.example       # Mẫu biến môi trường
├── .gitignore
└── README.md          # Tài liệu hướng dẫn sử dụng
```

---

## ⚡ Cài đặt & Khởi chạy

### 1. Yêu cầu hệ thống
- **Python 3.10+**
- **Google Gemini API Key** (hoặc OpenAI API Key)
- *Lưu ý*: Có thể chạy chế độ **Offline / Demo (Mock Mode)** không cần API key.

### 2. Tạo môi trường ảo (Virtual Environment)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Cấu hình môi trường (`.env`)

Sao chép file cấu hình mẫu:
```bash
cp .env.example .env
```

Mở file `.env` và điền thông tin:

#### Lựa chọn A: Chạy với Google Gemini (Khuyên dùng)
```env
MOCK_EMBEDDINGS=false
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini
GOOGLE_API_KEY=your-actual-gemini-api-key
LLM_MODEL_NAME=gemini-2.0-flash
EMBEDDING_MODEL_NAME=models/text-embedding-004
```

#### Lựa chọn B: Chạy với OpenAI
```env
MOCK_EMBEDDINGS=false
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key
LLM_MODEL_NAME=gpt-4o-mini
EMBEDDING_MODEL_NAME=text-embedding-3-small
```

#### Lựa chọn C: Chạy Offline / Mock Mode (Không cần API Key)
```env
MOCK_EMBEDDINGS=true
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini
```

### 5. Chạy Server FastAPI

```bash
python main.py
```
Server khởi động tại địa chỉ: `http://localhost:8000`

### 6. Thêm dữ liệu mẫu (15 Laptop)

Mở một terminal mới (giữ nguyên server đang chạy):
```bash
python seed_data.py
```

---

## 🔌 Danh Sách API Endpoints (8 Endpoints)

| Method | Endpoint | Mô tả |
|---|---|---|
| `POST` | `/api/chat` | Tư vấn & so sánh Laptop dựa trên RAG Pipeline |
| `POST` | `/api/sync-product` | Đồng bộ (thêm/sửa) 1 sản phẩm vào Vector DB |
| `POST` | `/api/sync-product/bulk` | Đồng bộ hàng loạt sản phẩm vào Vector DB |
| `DELETE` | `/api/sync-product/{product_id}` | Xóa sản phẩm khỏi Vector DB |
| `POST` | `/api/parse-query-debug` | Debug kết quả phân tích câu hỏi (Query Parser) |
| `POST` | `/api/search-debug` | Debug kết quả Vector Search & Scoring Engine |
| `GET` | `/health` | Health Check kiểm tra trạng thái service |
| `GET` | `/api/stats` | Thống kê số lượng sản phẩm trong Vector DB |

---

## 📝 Chi Tiết Các API Chính

### 1. Chat - Tư vấn Laptop (`POST /api/chat`)

**Request:**
```json
{
  "message": "Tôi cần laptop gaming dưới 25 triệu, RAM 16GB, thương hiệu Asus hoặc MSI",
  "session_id": "user-123"
}
```

**Response (camelCase):**
```json
{
  "answer": "Dựa trên nhu cầu gaming của bạn với ngân sách 25 triệu...",
  "confidenceScore": 0.87,
  "citations": [
    "Thông số kỹ thuật MSI Katana 15 từ TechStore ID #2",
    "Thông số kỹ thuật Lenovo LOQ 15 từ TechStore ID #3"
  ],
  "missingInformation": [
    "Bạn ưu tiên màn hình 15.6 inch hay 14 inch mỏng nhẹ?",
    "Bạn có cần thời lượng pin lâu không?"
  ],
  "recommendedProducts": [
    {
      "id": 2,
      "name": "MSI Katana 15 B13VFK",
      "price": 24990000,
      "url": "/product/2",
      "imageUrl": "/images/msi-katana-15.jpg",
      "reason": "RTX 4060 mạnh nhất trong tầm giá, i7-13620H hiệu năng cao"
    }
  ]
}
```

---

### 2. Đồng bộ 1 sản phẩm (`POST /api/sync-product`)

Hỗ trợ cả chuẩn `camelCase` (từ Spring Boot) và `snake_case`.

**Request:**
```json
{
  "id": 16,
  "name": "Asus TUF Gaming F15 FX507ZC4",
  "brand": "Asus",
  "price": 18990000,
  "ram": 8,
  "cpu": "Intel Core i5-12500H",
  "gpu": "NVIDIA GeForce RTX 3050 4GB",
  "storage": "512GB NVMe SSD",
  "screenSize": 15.6,
  "screenResolution": "1920x1080",
  "batteryLife": "4-5 giờ",
  "weight": 2.2,
  "operatingSystem": "Windows 11 Home",
  "isHot": false,
  "useCaseTags": "gaming",
  "stock": 10,
  "category": "Gaming Laptop",
  "url": "/product/16",
  "imageUrl": "/images/asus-tuf-f15.jpg",
  "description": "Laptop gaming quốc dân phân khúc tầm trung."
}
```

---

### 3. Đồng bộ hàng loạt sản phẩm (`POST /api/sync-product/bulk`)

**Request:**
```json
{
  "products": [
    {
      "id": 101,
      "name": "Dell XPS 13 9320",
      "brand": "Dell",
      "price": 35000000,
      "ram": 16,
      "cpu": "Intel Core i7-1360P",
      "storage": "512GB SSD",
      "useCaseTags": "office,lightweight"
    },
    {
      "id": 102,
      "name": "MacBook Air M2",
      "brand": "Apple",
      "price": 26990000,
      "ram": 8,
      "cpu": "Apple M2 8-core",
      "storage": "256GB SSD",
      "useCaseTags": "office,student,lightweight"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "total": 2,
  "successCount": 2,
  "failedCount": 0,
  "results": [
    {"id": 101, "success": true, "message": "Synced successfully"},
    {"id": 102, "success": true, "message": "Synced successfully"}
  ]
}
```

---

### 4. Debug Vector Search & Scoring (`POST /api/search-debug`)

Endpoint dùng để soi chi tiết quá trình Query Parsing, Metadata Filtering, Vector Similarity Score và Bonus Re-ranking Score cho từng ứng viên.

**Request:**
```json
{
  "message": "Laptop gaming dưới 25 triệu"
}
```

---

## 🧠 Chi Tiết RAG Pipeline

```
Câu hỏi: "Tôi cần laptop gaming dưới 25 triệu RAM 16GB"
          │
          ▼
┌─────────────────────────────────────────┐
│ 1. QUERY PARSER (Rule-based Regex)      │
│    - max_price: 25,000,000 VND          │
│    - min_ram: 16 GB                     │
│    - intent/use_case: "gaming"          │
│    - semantic_query: "laptop gaming..." │
└─────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│ 2. METADATA FILTER (ChromaDB Where)     │
│    { price: {$lte: 25000000},           │
│      ram: {$gte: 16} }                  │
└─────────────────────────────────────────┘
          │ Tập sản phẩm đã lọc cứng
          ▼
┌─────────────────────────────────────────┐
│ 3. VECTOR SEARCH (Semantic Similarity)  │
│    Embedding Query → Top-K tương đồng  │
└─────────────────────────────────────────┘
          │ Candidates
          ▼
┌─────────────────────────────────────────┐
│ 4. SCORING ENGINE (Re-ranking Engine)   │
│    + Vector Similarity Weight × 5       │
│    + Brand Match: +3 điểm               │
│    + Price Match: +2 điểm               │
│    + CPU Match: +2 điểm                 │
│    + HOT Product: +1 điểm               │
└─────────────────────────────────────────┘
          │ Top-5 ranked products
          ▼
┌─────────────────────────────────────────┐
│ 5. LLM GENERATION (Gemini/OpenAI)       │
│    Structured Output (Pydantic)         │
│    → Trả JSON có cấu trúc               │
└─────────────────────────────────────────┘
```

---

## 🔗 Tích Hợp Với Java Spring Boot

Ví dụ client gọi RAG Microservice từ Spring Boot:

```java
@Service
public class ProductRAGClient {

    @Value("${rag.service.url:http://localhost:8000}")
    private String ragServiceUrl;

    private final RestTemplate restTemplate;

    public ProductRAGClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    // 1. Gọi API Chat Tư vấn
    public RAGChatResponse chat(String userMessage, String sessionId) {
        Map<String, Object> request = Map.of(
            "message", userMessage,
            "session_id", sessionId
        );
        return restTemplate.postForObject(
            ragServiceUrl + "/api/chat",
            request,
            RAGChatResponse.class
        );
    }

    // 2. Đồng bộ 1 sản phẩm
    public SyncResponse syncProduct(ProductDTO product) {
        return restTemplate.postForObject(
            ragServiceUrl + "/api/sync-product",
            product,
            SyncResponse.class
        );
    }

    // 3. Đồng bộ hàng loạt sản phẩm
    public BulkSyncResponse syncProductBulk(List<ProductDTO> products) {
        Map<String, Object> request = Map.of("products", products);
        return restTemplate.postForObject(
            ragServiceUrl + "/api/sync-product/bulk",
            request,
            BulkSyncResponse.class
        );
    }

    // 4. Xóa sản phẩm khỏi Vector DB
    public void deleteProduct(Long productId) {
        restTemplate.delete(ragServiceUrl + "/api/sync-product/" + productId);
    }
}
```

---

## ⚙️ Bảng Tra Cứu Biến Môi Trường (`.env`)

| Biến môi trường | Mặc định | Mô tả |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | Nhà cung cấp LLM: `gemini` hoặc `openai` |
| `EMBEDDING_PROVIDER` | `gemini` | Nhà cung cấp Embedding: `gemini`, `openai`, hoặc `local` |
| `GOOGLE_API_KEY` | `""` | Google Gemini API Key |
| `OPENAI_API_KEY` | `""` | OpenAI API Key |
| `LLM_MODEL_NAME` | `gemini-2.0-flash` | Tên mô hình LLM |
| `EMBEDDING_MODEL_NAME` | `models/text-embedding-004` | Tên mô hình Embedding |
| `MOCK_EMBEDDINGS` | `false` | Bật/tắt chế độ Mock Embedding (Offline test) |
| `CHROMA_DB_PATH` | `./chroma_db` | Đường dẫn thư mục lưu ChromaDB local |
| `CHROMA_COLLECTION_NAME` | `laptops` | Tên collection lưu sản phẩm |
| `TOP_K_RESULTS` | `10` | Số sản phẩm tối đa lấy từ Vector Search |
| `MAX_RECOMMENDED_PRODUCTS` | `5` | Số sản phẩm đề xuất tối đa trả về |
| `MIN_CONFIDENCE_THRESHOLD` | `0.3` | Ngưỡng điểm tin cậy tối thiểu |
| `ALLOWED_ORIGINS` | `http://localhost:8080,http://localhost:3000` | Danh sách domain CORS được phép kết nối |
| `HOST` | `0.0.0.0` | IP Host khởi chạy FastAPI |
| `PORT` | `8000` | Port khởi chạy FastAPI |
| `DEBUG` | `false` | Bật/Tắt log debug chi tiết |

---

## 📑 Tiện Ích Xuất Báo Cáo PDF Technical Specification

Dự án tích hợp sẵn script `generate_pdf.py` để tạo tài liệu đặc tả kỹ thuật PDF chuẩn doanh nghiệp:

```bash
python generate_pdf.py
```
File `Bao_Cao_Ky_Thuat_Product_Comparison_RAG.pdf` sẽ được tạo tự động với font tiếng Việt, bao gồm đầy đủ sơ đồ kiến trúc, tài liệu API, bảng cấu hình và mã nguồn tích hợp Java.

---

## 📖 Swagger Documentation

Khi server đang khởi chạy, truy cập tài liệu API tương tác tại:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
#   l a p t o p - r a g - c o p i l o t  
 