"""
rag_service.py - Xử lý luồng RAG Pipeline chính

Module này điều phối toàn bộ quy trình:
1. Phân tích câu hỏi (Query Parser) - Module 1
2. Xây dựng metadata filter - Module 3
3. Tìm kiếm vector + metadata filtering - Module 4
4. Chấm điểm & xếp hạng (Re-ranking) - Module 5
5. Gọi LLM tạo câu trả lời JSON có cấu trúc - Module 6
"""

import logging
import re
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from config import settings
from database import ChromaDBManager
from schemas import (
    ChatRequest,
    LLMStructuredOutput,
    ParsedQuery,
    ProductSyncRequest,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MODULE 1: QUERY PARSER - Phân tích câu hỏi tự nhiên
# =============================================================================


class QueryParser:
    """
    Phân tích câu hỏi tự nhiên của khách hàng thành:
    - Tiêu chí lọc cứng: giá, thương hiệu, RAM, CPU keyword...
    - Ý định ngữ nghĩa: gaming, đồ họa, văn phòng, sinh viên...
    """

    # Từ điển thương hiệu laptop phổ biến
    BRAND_KEYWORDS = {
        "asus": "asus",
        "dell": "dell",
        "hp": "hp",
        "lenovo": "lenovo",
        "acer": "acer",
        "msi": "msi",
        "apple": "apple",
        "macbook": "apple",
        "mac": "apple",
        "microsoft": "microsoft",
        "surface": "microsoft",
        "lg": "lg",
        "samsung": "samsung",
        "razer": "razer",
        "gigabyte": "gigabyte",
        "huawei": "huawei",
    }

    # Từ điển mục đích sử dụng
    USE_CASE_KEYWORDS = {
        "gaming": ["gaming", "game", "chơi game", "fps", "esport", "rtx", "rx"],
        "design": [
            "thiết kế",
            "đồ họa",
            "photoshop",
            "illustrator",
            "premiere",
            "video",
            "render",
            "4k",
        ],
        "office": [
            "văn phòng",
            "office",
            "word",
            "excel",
            "powerpoint",
            "zoom",
            "họp",
        ],
        "student": ["sinh viên", "học", "study", "university", "đại học", "học sinh"],
        "programming": ["lập trình", "coding", "developer", "dev", "code", "python"],
        "lightweight": ["mỏng nhẹ", "di chuyển", "portable", "nhẹ", "ultrabook"],
    }

    # Từ điển đơn vị tiền tệ sang VND
    CURRENCY_MULTIPLIERS = {
        "triệu": 1_000_000,
        "tr": 1_000_000,
        "m": 1_000_000,
        "nghìn": 1_000,
        "k": 1_000,
    }

    def parse(self, query: str) -> ParsedQuery:
        """
        Phân tích câu hỏi tự nhiên và trích xuất các tiêu chí.

        Sử dụng rule-based parsing kết hợp với regex để
        đảm bảo tốc độ và không tốn thêm API call.

        Args:
            query: Câu hỏi tự nhiên của người dùng

        Returns:
            ParsedQuery chứa các tiêu chí đã phân tích
        """
        query_lower = query.lower()

        # --- Phân tích giá ---
        # 'khoảng/tầm X triệu' → range ±15%
        price_range = self._extract_approximate_price_range(query_lower)
        if price_range:
            extracted_min_price, extracted_max_price = price_range
        else:
            # Logic cũ: 'dưới', 'trên', 'từ...'
            extracted_min_price = self._extract_min_price(query_lower)
            extracted_max_price = self._extract_max_price(query_lower)

        # --- Phân tích mode & comparison products ---
        mode = self._detect_mode(query_lower)
        comparison_products = (
            self._extract_comparison_products(query, query_lower)
            if mode == "comparison"
            else []
        )

        return ParsedQuery(
            max_price=extracted_max_price,
            min_price=extracted_min_price,
            brand=self._extract_brand(query_lower),
            min_ram=self._extract_min_ram(query_lower),
            cpu_keyword=self._extract_cpu_keyword(query_lower),
            gpu_keyword=self._extract_gpu_keyword(query_lower),
            min_storage_gb=self._extract_min_storage(query_lower),
            semantic_query=self._build_semantic_query(query, query_lower),
            use_case=self._detect_use_case(query_lower),
            mode=mode,
            comparison_products=comparison_products,
            raw_query=query,
        )

    def _extract_approximate_price_range(
        self, text: str
    ) -> Optional[tuple[float, float]]:
        """
        Trích xuất khoảng giá ±15% từ các biểu thức 'khoảng/tầm X triệu'.

        Ví dụ:
            'khoảng 30 triệu'  → (25_500_000, 34_500_000)
            'tầm 20 triệu'     → (17_000_000, 23_000_000)
            'khoảng 25tr'      → (21_250_000, 28_750_000)

        Returns:
            Tuple (min_price, max_price) hoặc None nếu không khớp.
        """
        approx_patterns = [
            r"(?:khoảng|tầm|xấp xỉ|gần|tầm khoảng)\s*(\d+(?:[.,]\d+)?)\s*(triệu|tr|nghìn|k)",
        ]
        for pattern in approx_patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1).replace(",", "."))
                unit = match.group(2)
                base = value * self.CURRENCY_MULTIPLIERS.get(unit, 1)
                delta = base * 0.15
                return (round(base - delta), round(base + delta))
        return None

    def _extract_price(self, text: str) -> Optional[float]:
        """Helper trích xuất một giá trị tiền tệ bất kỳ từ text."""
        # Pattern: số (có thể có dấu chấm/phẩy) + đơn vị
        pattern = r"(\d+(?:[.,]\d+)?)\s*(triệu|tr|nghìn|k)"
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1).replace(",", "."))
            unit = match.group(2)
            multiplier = self.CURRENCY_MULTIPLIERS.get(unit, 1)
            return value * multiplier

        # Pattern: số lớn trực tiếp (ví dụ: 25000000)
        pattern_direct = r"\b(\d{7,})\b"
        match = re.search(pattern_direct, text)
        if match:
            return float(match.group(1))

        return None

    def _extract_max_price(self, text: str) -> Optional[float]:
        """
        Trích xuất giá tối đa từ câu hỏi.

        Lưu ý: Chỉ xử lý các biểu thức chỉ giới hạn rõ ràng ('dưới', 'không quá').
        Biểu thức 'khoảng/tầm' được xử lý riêng trong _extract_approximate_price_range().
        """
        # Chỉ match các từ chỉ giới hạn trên (không bao gồm 'khoảng', 'tầm')
        upper_patterns = [
            r"(?:dưới|không quá|tối đa|max|budget|ngân sách)\s*(\d+(?:[.,]\d+)?)\s*(triệu|tr|nghìn|k)",
            r"(\d+(?:[.,]\d+)?)\s*(triệu|tr|nghìn|k)\s*(?:trở xuống|trở lại|thôi)",
        ]

        for pattern in upper_patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1).replace(",", "."))
                unit = match.group(2)
                return value * self.CURRENCY_MULTIPLIERS.get(unit, 1)

        return None

    def _extract_min_price(self, text: str) -> Optional[float]:
        """Trích xuất giá tối thiểu từ câu hỏi."""
        lower_patterns = [
            r"(?:trên|từ|hơn|ít nhất)\s*(\d+(?:[.,]\d+)?)\s*(triệu|tr|nghìn|k)",
            r"(\d+(?:[.,]\d+)?)\s*(triệu|tr|nghìn|k)\s*(?:trở lên|trở ra)",
        ]

        for pattern in lower_patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1).replace(",", "."))
                unit = match.group(2)
                return value * self.CURRENCY_MULTIPLIERS.get(unit, 1)

        return None

    def _extract_brand(self, text: str) -> Optional[str]:
        """
        Trích xuất thương hiệu từ câu hỏi.

        Trong recommendation mode: trả về brand đầu tiên tìm được.
        Trong comparison mode: các brand được xử lý qua _extract_comparison_products().
        """
        for keyword, brand in self.BRAND_KEYWORDS.items():
            if keyword in text:
                return brand
        return None

    def _detect_mode(self, text: str) -> str:
        """
        Detect chế độ xử lý dựa trên cấu trúc câu hỏi.

        Trả về 'comparison' nếu phát hiện các dạng:
        - 'so sánh X và/hay Y'
        - 'X vs Y'
        - 'X hay Y cái nào tốt hơn'
        - 'X khác gì Y'
        - 'nên chọn X hay Y'

        Trả về 'recommendation' cho tất cả các trưống hợp khác.
        """
        comparison_patterns = [
            # so sánh ... và/hay ...
            r"so\s+sánh",
            # X vs Y
            r"\bvs\.?\b",
            # ... cái nào tốt hơn / cái nào hay hơn
            r"cái\s+nào\s+(?:tốt|hay|tốt hơn|nên\s+mua|nên\s+chọn)",
            # ... khác gì ...
            r"khác\s+gì",
            # nên chọn ... hay ...
            r"nên\s+chọn",
            # so với
            r"so\s+với",
        ]
        for pattern in comparison_patterns:
            if re.search(pattern, text):
                return "comparison"

        # 'hay' chỉ là comparison nếu có ít nhất 2 brand/model xuất hiện
        if "hay" in text:
            brands_found = [
                brand
                for keyword, brand in self.BRAND_KEYWORDS.items()
                if keyword in text
            ]
            # Un-duplicate brands
            unique_brands = list(dict.fromkeys(brands_found))
            if len(unique_brands) >= 2 or self._count_model_mentions(text) >= 2:
                return "comparison"

        return "recommendation"

    def _count_model_mentions(self, text: str) -> int:
        """
        Đếm số lượng model/sử liệu xuất hiện trong text.
        Dùng để phát hiện comparison qua 'hay' khi có nhiều model.
        """
        # Model pattern: từ điều bắt đầu bằng viết hoa + có số
        model_pattern = r"\b[A-Z][a-z]+\s+[A-Z0-9][a-zA-Z0-9]*(?:\s+[A-Z0-9][a-zA-Z0-9]*)*\b"
        matches = re.findall(model_pattern, text)
        return len(matches)

    def _extract_comparison_products(self, original: str, text_lower: str) -> list[str]:
        """
        Trích xuất danh sách tên/model sản phẩm cần so sánh.

        Chiến lược:
        1. Loại bỏ các từ nối/signal words (‘so sánh’, ‘vs’, ‘hay’, ...)
        2. Split theo các separator (‘vs’, ‘và’, ‘hay’)
        3. Dùng rule-based để nhận dạng các cụm tên Brand + Model

        Args:
            original: Câu hỏi gốc (giữ hoa/thường để giữ tên model)
            text_lower: Câu hỏi viết thường

        Returns:
            Danh sách tên sản phẩm/model đã clean
        """
        # Bước 1: Loại bỏ các cụm dẫn đầu không cần thiết
        noise_prefixes = [
            r"^(so sánh|hãy so sánh|cho tôi so sánh|bạn hãy so sánh)\s*",
            r"^(tôi nên chọn|nên chọn|tôi muốn biết|cho hỏi)\s*",
        ]
        cleaned = original.strip()
        cleaned_lower = text_lower.strip()
        for prefix in noise_prefixes:
            cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE).strip()
            cleaned_lower = re.sub(prefix, "", cleaned_lower).strip()

        # Loại bỏ suffix không cần thiết (câu hỏi phía sau)
        noise_suffixes = [
            r"\s*(cái nào tốt hơn|cái nào hay hơn|cái nào nên mua|khác gì nhau|thì sao|nhỉ)\s*\??$",
        ]
        for suffix in noise_suffixes:
            cleaned = re.sub(suffix, "", cleaned, flags=re.IGNORECASE).strip()

        # Bước 2: Split theo các separator chính
        # Thứ tự: 'vs' trước 'và'/'hay' để tránh split nhầm
        separator_pattern = r"\s+(?:vs\.?|và|hay|hoặc|so với|khác gì)\s+"
        parts = re.split(separator_pattern, cleaned, flags=re.IGNORECASE)

        # Bước 3: Clean từng phần
        products = []
        for part in parts:
            part = part.strip().strip("?")
            # Loại bỏ phần đưa ra điều kiện (ví dụ: 'cái nào tốt hơn')
            part = re.sub(
                r"\s*(cái nào|tốt hơn|hay hơn|nên mua|nên chọn).*$",
                "",
                part,
                flags=re.IGNORECASE,
            ).strip()

            if part and len(part) >= 3:
                # Capitalize đầu mỗi từ (title-case) nhưng giữ các từ hoa sẵn
                # Ví dụ: 'asus rog g14' -> 'Asus ROG G14' (giữ cụm viết hoa gốc)
                products.append(self._title_case_product_name(part))

        # Loại duplicate và trả về
        seen = set()
        unique_products = []
        for p in products:
            key = p.lower()
            if key not in seen:
                seen.add(key)
                unique_products.append(p)

        return unique_products

    def _title_case_product_name(self, name: str) -> str:
        """
        Tạo title-case cho tên sản phẩm, giữ nguyên các cụm viết hoa (‘ROG’, ‘RTX’, ...).
        """
        words = name.split()
        result = []
        for word in words:
            # Giữ nguyên nếu đã có hoa (như ROG, RTX, TUF, XPS, M2, G14)
            if word.isupper() or re.match(r"^[A-Z][0-9]", word):
                result.append(word)
            else:
                result.append(word.capitalize())
        return " ".join(result)

    def _extract_min_ram(self, text: str) -> Optional[int]:
        """Trích xuất yêu cầu RAM tối thiểu."""
        # Pattern: số GB RAM
        pattern = r"(\d+)\s*gb\s*ram|ram\s*(\d+)\s*gb|(\d+)\s*gb"
        matches = re.findall(pattern, text)
        for match in matches:
            # Lấy giá trị đầu tiên không None trong tuple
            value = next((int(v) for v in match if v), None)
            if value and value in [4, 8, 16, 32, 64]:  # RAM hợp lệ
                return value
        return None

    def _extract_cpu_keyword(self, text: str) -> Optional[str]:
        """Trích xuất từ khóa CPU."""
        cpu_patterns = [
            r"(i[3579][-\s]\d{4,5}[a-z]*)",  # Intel i5-12500H
            r"(core\s+ultra\s+\d+)",  # Core Ultra 7
            r"(ryzen\s+[3579]\s*\d{4}[a-z]*)",  # Ryzen 9 7945HX
            r"(m[123]\s+(?:pro|max|ultra)?)",  # Apple M2 Pro
            r"(snapdragon\s+x)",  # Snapdragon X Elite
        ]

        for pattern in cpu_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        # Tìm keyword CPU đơn giản
        simple_keywords = ["i3", "i5", "i7", "i9", "ryzen 5", "ryzen 7", "ryzen 9"]
        for kw in simple_keywords:
            if kw in text:
                return kw

        return None

    def _extract_gpu_keyword(self, text: str) -> Optional[str]:
        """Trích xuất từ khóa GPU."""
        gpu_patterns = [
            r"(rtx\s*\d{4}[a-z\s]*(?:ti|super)?)",  # RTX 4060 Ti
            r"(gtx\s*\d{4}[a-z\s]*)",  # GTX 1650
            r"(rx\s*\d{4}[a-z\s]*(?:m|xt)?)",  # RX 6700M
            r"(arc\s+[a-z]\d+[a-z]*)",  # Intel Arc A770M
        ]

        for pattern in gpu_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def _extract_min_storage(self, text: str) -> Optional[int]:
        """Trích xuất yêu cầu dung lượng ổ cứng tối thiểu."""
        pattern = r"(\d+)\s*(?:gb|tb)\s*(?:ssd|hdd|ổ|storage)"
        match = re.search(pattern, text)
        if match:
            value = int(match.group(1))
            unit = "tb" if "tb" in text[match.start():match.end()] else "gb"
            return value * 1024 if unit == "tb" else value
        return None

    def _detect_use_case(self, text: str) -> Optional[str]:
        """Xác định mục đích sử dụng chính từ câu hỏi."""
        use_case_scores = {}

        for use_case, keywords in self.USE_CASE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                use_case_scores[use_case] = score

        if not use_case_scores:
            return None

        # Trả về use case có nhiều keyword nhất
        return max(use_case_scores, key=use_case_scores.get)

    def _build_semantic_query(self, original_query: str, query_lower: str) -> str:
        """
        Xây dựng câu truy vấn ngữ nghĩa tối ưu cho vector search.

        Mục tiêu: tạo câu query phong phú hơn để embedding model
        tìm được sản phẩm phù hợp nhất.
        """
        use_case = self._detect_use_case(query_lower)

        # Bổ sung context ngữ nghĩa vào query
        enrichments = []

        if use_case == "gaming":
            enrichments.append(
                "laptop gaming hiệu năng cao GPU RTX card rời frame rate cao"
            )
        elif use_case == "design":
            enrichments.append(
                "laptop đồ họa thiết kế màn hình chính xác màu sắc RAM lớn"
            )
        elif use_case == "office":
            enrichments.append(
                "laptop văn phòng pin trâu nhẹ mỏng ổn định bàn phím tốt"
            )
        elif use_case == "student":
            enrichments.append(
                "laptop sinh viên giá rẻ nhẹ pin lâu đa năng cơ bản"
            )
        elif use_case == "programming":
            enrichments.append(
                "laptop lập trình RAM nhiều CPU mạnh màn hình nét terminal"
            )
        elif use_case == "lightweight":
            enrichments.append(
                "laptop mỏng nhẹ ultrabook portable di chuyển nhiều"
            )

        if enrichments:
            return f"{original_query} {' '.join(enrichments)}"

        return original_query


# =============================================================================
# MODULE 5: SCORING ENGINE - Chấm điểm và xếp hạng
# =============================================================================


class ScoringEngine:
    """
    Tính điểm tương thích cho các laptop ứng viên.

    Tiêu chí chấm điểm:
    - Cùng thương hiệu với yêu cầu: +3 điểm
    - Tầm giá tương đương (±20%): +2 điểm
    - Cùng dòng CPU yêu cầu: +2 điểm
    - Sản phẩm HOT: +1 điểm
    - Điểm vector similarity (nhân hệ số 5): 0-5 điểm
    """

    def score_candidates(
        self,
        candidates: list[dict],
        parsed_query: ParsedQuery,
    ) -> list[dict]:
        """
        Tính điểm và xếp hạng lại các sản phẩm ứng viên.

        Args:
            candidates: Danh sách sản phẩm từ vector search
            parsed_query: Tiêu chí đã parse từ câu hỏi

        Returns:
            Danh sách đã được sắp xếp theo điểm tổng (giảm dần)
        """
        scored = []

        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            similarity_score = candidate.get("similarity_score", 0.0)

            # Tính điểm bonus
            bonus_score = 0.0
            score_details = []

            # 1. CÁC TIÊU CHÍ HIỆN TẠI (GIỮ NGUYÊN)
            
            # +3: Cùng thương hiệu
            if parsed_query.brand and metadata.get("brand", "") == parsed_query.brand.lower():
                bonus_score += 3.0
                score_details.append("brand_match(+3)")

            # +2: Tầm giá tương đương (±20% của giá tham chiếu)
            ref_price = parsed_query.max_price or parsed_query.min_price
            if ref_price:
                product_price = metadata.get("price", 0)
                price_diff_ratio = abs(product_price - ref_price) / ref_price
                if price_diff_ratio <= 0.20:
                    bonus_score += 2.0
                    score_details.append("price_match(+2)")

            # +2: Cùng dòng CPU
            if parsed_query.cpu_keyword and parsed_query.cpu_keyword in metadata.get("cpu", "").lower():
                bonus_score += 2.0
                score_details.append("cpu_match(+2)")

            # +1: Sản phẩm HOT
            if metadata.get("is_hot", False):
                bonus_score += 1.0
                score_details.append("hot_product(+1)")

            # 2. BỔ SUNG: RAM MATCH
            product_ram = 0
            if metadata.get("ram") is not None:
                try:
                    product_ram = int(metadata.get("ram", 0))
                except (ValueError, TypeError):
                    pass

            if parsed_query.min_ram is not None:
                if product_ram >= parsed_query.min_ram:
                    bonus_score += 2.0
                    score_details.append("ram_match(+2)")
                else:
                    bonus_score -= 1.0
                    score_details.append("ram_insufficient(-1)")

            # 3. BỔ SUNG: GPU MATCH
            gpu_str = metadata.get("gpu", "")
            gpu_lower = gpu_str.lower() if gpu_str else ""
            
            # GPU Keyword match từ query parser
            if parsed_query.gpu_keyword:
                if parsed_query.gpu_keyword.lower() in gpu_lower:
                    bonus_score += 3.0
                    score_details.append("gpu_match(+3)")

            # Phân loại GPU rời và GPU tích hợp
            is_dedicated_gpu = any(kw in gpu_lower for kw in ["rtx", "gtx", "radeon", "quadro", "geforce"])
            
            # Gợi ý GPU theo nhu cầu gaming/design
            if parsed_query.use_case in ("gaming", "design"):
                if is_dedicated_gpu:
                    if parsed_query.use_case == "gaming":
                        bonus_score += 2.0
                        score_details.append("dedicated_gpu_for_gaming(+2)")
                    else:
                        bonus_score += 2.0
                        score_details.append("dedicated_gpu_for_design(+2)")
                else:
                    bonus_score -= 1.0
                    score_details.append("integrated_gpu_penalty(-1)")

            # 4. BỔ SUNG: USE CASE / INTENT MATCH
            cpu_str = metadata.get("cpu", "")
            cpu_lower = cpu_str.lower() if cpu_str else ""
            is_powerful_cpu = any(kw in cpu_lower for kw in ["i5", "i7", "i9", "ryzen 5", "ryzen 7", "ryzen 9", "ultra", "m1", "m2", "m3", "m4", "snapdragon"])
            
            if parsed_query.use_case == "gaming":
                # RAM >= 16GB
                if product_ram >= 16:
                    bonus_score += 1.0
                    score_details.append("gaming_ram_match(+1)")
                # CPU mạnh
                if is_powerful_cpu:
                    bonus_score += 1.0
                    score_details.append("powerful_cpu_for_gaming(+1)")
                # Tags có gaming
                if "gaming" in metadata.get("use_case_tags", "").lower():
                    bonus_score += 1.0
                    score_details.append("gaming_tag_match(+1)")

            elif parsed_query.use_case == "office":
                # Giá hợp lý (<= 25 triệu)
                if metadata.get("price", 0) <= 25000000:
                    bonus_score += 1.0
                    score_details.append("reasonable_price_for_office(+1)")
                # RAM >= 8GB
                if product_ram >= 8:
                    bonus_score += 1.0
                    score_details.append("office_ram_match(+1)")
                # CPU tiết kiệm điện / văn phòng
                has_u_suffix = False
                if re.search(r"\b\d{4,5}u\b|\bu\b", cpu_lower) or cpu_lower.endswith("u") or "u " in cpu_lower:
                    has_u_suffix = True
                is_office_cpu = has_u_suffix or any(kw in cpu_lower for kw in ["ultra", "m1", "m2", "m3", "m4", "snapdragon"])
                if is_office_cpu:
                    bonus_score += 1.0
                    score_details.append("office_cpu_match(+1)")
                # Không cần GPU rời (tức là có GPU tích hợp)
                if not is_dedicated_gpu:
                    bonus_score += 1.0
                    score_details.append("integrated_gpu_for_office(+1)")

            elif parsed_query.use_case == "design":
                # RAM >= 16GB
                if product_ram >= 16:
                    bonus_score += 1.0
                    score_details.append("design_ram_match(+1)")
                # CPU mạnh
                if is_powerful_cpu:
                    bonus_score += 1.0
                    score_details.append("powerful_cpu_for_design(+1)")
                # Màn hình tốt (check display/screen trong metadata/document)
                screen_info = ""
                for k, v in metadata.items():
                    if any(term in k.lower() for term in ["display", "screen", "resolution"]):
                        screen_info += f" {v}"
                if "document" in candidate:
                    screen_info += f" {candidate.get('document', '')}"
                screen_info_lower = screen_info.lower()
                good_display_keywords = ["oled", "retina", "qhd", "2k", "3k", "4k", "120hz", "144hz", "165hz", "240hz", "dci-p3", "srgb", "ips"]
                if any(kw in screen_info_lower for kw in good_display_keywords):
                    bonus_score += 1.0
                    score_details.append("good_display(+1)")

            elif parsed_query.use_case == "programming":
                # RAM >= 16GB
                if product_ram >= 16:
                    bonus_score += 1.0
                    score_details.append("programming_ram_match(+1)")
                # SSD
                storage_str = metadata.get("storage", "").lower()
                doc_str = candidate.get("document", "").lower()
                if "ssd" in storage_str or "ssd" in doc_str:
                    bonus_score += 1.0
                    score_details.append("ssd_storage(+1)")
                # CPU i5/Ryzen 5 trở lên
                if is_powerful_cpu:
                    bonus_score += 1.0
                    score_details.append("programming_cpu_match(+1)")

            # 5. BỔ SUNG: STOCK CHECK
            stock_val = None
            if "stock" in metadata:
                stock_val = metadata.get("stock")
            elif "in_stock" in metadata:
                stock_val = metadata.get("in_stock")

            if stock_val is not None:
                if isinstance(stock_val, bool):
                    if stock_val:
                        bonus_score += 0.5
                        score_details.append("stock_available(+0.5)")
                    else:
                        bonus_score -= 5.0
                        score_details.append("out_of_stock(-5)")
                else:
                    try:
                        stock_num = float(stock_val)
                        if stock_num > 0:
                            bonus_score += 0.5
                            score_details.append("stock_available(+0.5)")
                        else:
                            bonus_score -= 5.0
                            score_details.append("out_of_stock(-5)")
                    except (ValueError, TypeError):
                        pass

            # Điểm vector similarity (0.0-1.0) nhân hệ số 5
            vector_score = similarity_score * 5.0

            # Tổng điểm
            total_score = vector_score + bonus_score

            candidate_with_score = {
                **candidate,
                "bonus_score": bonus_score,
                "vector_score": vector_score,
                "total_score": total_score,
                "score_details": score_details,
            }
            scored.append(candidate_with_score)

            logger.debug(
                f"Sản phẩm {metadata.get('name', 'N/A')}: "
                f"vector={vector_score:.2f}, bonus={bonus_score:.1f}, "
                f"total={total_score:.2f}, details={score_details}"
            )

        # Sắp xếp theo tổng điểm giảm dần
        scored.sort(key=lambda x: x["total_score"], reverse=True)
        return scored


# =============================================================================
# MODULE 6: RECOMMENDATION GENERATOR - Gọi LLM tạo câu trả lời
# =============================================================================


class RecommendationGenerator:
    """
    Tổng hợp thông tin và gọi LLM để tạo câu trả lời có cấu trúc.

    Sử dụng LangChain's .with_structured_output() để đảm bảo
    LLM trả về đúng schema Pydantic LLMStructuredOutput.
    """

    def __init__(self):
        self.llm = self._create_llm()
        # Bind structured output schema vào LLM
        self.structured_llm = self.llm.with_structured_output(LLMStructuredOutput)
        self.prompt_template = self._build_prompt_template()
        logger.info("RecommendationGenerator đã khởi tạo thành công.")

    def _create_llm(self):
        """Tạo LLM instance dựa trên cấu hình provider."""
        if settings.mock_embeddings:
            logger.info("Khởi tạo MOCK LLM...")
            from langchain_core.runnables import Runnable
            class MockStructuredLLM(Runnable):
                def invoke(self, input, config=None, **kwargs):
                    from schemas import LLMStructuredOutput, RecommendedProduct
                    import re
                    ctx = ""
                    if hasattr(input, "to_string"):
                        ctx = input.to_string()
                    elif isinstance(input, dict):
                        ctx = input.get("product_context", "")
                    elif hasattr(input, "messages"):
                        ctx = str(input.messages)
                    else:
                        ctx = str(input)
                    
                    # 1. Trích xuất user_query
                    query_match = re.search(r"NHU CẦU KHÁCH HÀNG:\s*(.*?)\s*\n\nTIÊU CHÍ ĐÃ PHÂN TÍCH:", ctx, re.DOTALL)
                    user_query = query_match.group(1).strip() if query_match else ""
                    user_query_lower = user_query.lower()
                    
                    # 2. Trích xuất các candidates
                    candidates_raw = ctx.split("--- SẢN PHẨM #")
                    candidates = []
                    for block in candidates_raw[1:]:
                        pid_match = re.search(r"ID:\s*(\d+)", block)
                        name_match = re.search(r"Tên:\s*(.*?)\n", block)
                        price_match = re.search(r"Giá:\s*(.*?)\n", block)
                        url_match = re.search(r"URL:\s*(.*?)\n", block)
                        img_match = re.search(r"imageUrl:\s*(.*?)\n", block)
                        
                        if pid_match and name_match:
                            pid = int(pid_match.group(1))
                            name = name_match.group(1).strip()
                            
                            price_val = 0.0
                            if price_match:
                                price_str = price_match.group(1).replace("VND", "").replace(",", "").replace(".", "").replace(" ₫", "").strip()
                                price_digits = re.sub(r"[^\d]", "", price_str)
                                if price_digits:
                                    try:
                                        price_val = float(price_digits)
                                    except:
                                        pass
                            
                            url = url_match.group(1).strip() if url_match else ""
                            image_url = img_match.group(1).strip() if img_match else ""
                            
                            candidates.append({
                                "id": pid,
                                "name": name,
                                "price": price_val,
                                "url": url,
                                "image_url": image_url
                            })

                    # 3. Phân loại câu hỏi theo luật
                    matched_products = []
                    answer_text = ""
                    reason_text = ""
                    
                    is_gaming = any(k in user_query_lower for k in ["gaming", "game", "rtx", "144hz"])
                    is_office = any(k in user_query_lower for k in ["văn phòng", "office", "mỏng nhẹ", "pin"])
                    is_design = any(k in user_query_lower for k in ["đồ họa", "design", "render"])
                    is_dev = any(k in user_query_lower for k in ["lập trình", "programming", "dev", "code"])
                    
                    if is_gaming:
                        answer_text = "Dựa trên nhu cầu tìm kiếm laptop gaming của bạn, tôi xin gợi ý các sản phẩm tối ưu hiệu năng đồ họa và tốc độ quét màn hình. Các dòng máy Asus TUF hoặc Acer Nitro được trang bị GPU rời RTX cực kỳ mạnh mẽ để chơi mượt mà các tựa game hiện đại."
                        reason_text = "Dòng laptop gaming cấu hình mạnh mẽ, hệ thống tản nhiệt tối ưu và màn hình tần số quét cao phù hợp nhu cầu chơi game."
                        matched_products = [c for c in candidates if any(k in c['name'].lower() for k in ["tuf", "nitro", "gaming", "zephyrus"])]
                    elif is_office:
                        answer_text = "Đối với các nhu cầu làm việc văn phòng, học tập và ưu tiên thiết kế mỏng nhẹ cùng thời lượng pin tốt, dưới đây là các lựa chọn tối ưu như HP Pavilion, Dell Inspiron, Dell Vostro hoặc IdeaPad. Chúng đáp ứng mượt mà các ứng dụng văn phòng và có thời lượng pin lâu dài."
                        reason_text = "Thiết kế mỏng nhẹ, pin trâu và cấu hình mượt mà cho các tác vụ văn phòng, học tập hàng ngày."
                        matched_products = [c for c in candidates if any(k in c['name'].lower() for k in ["vostro", "pavilion", "slim", "inspiron", "ideapad"])]
                    elif is_design:
                        answer_text = "Để xử lý tốt các tác vụ thiết kế đồ họa, edit video, dựng hình 2D/3D và render, bạn cần cấu hình mạnh mẽ với CPU nhiều nhân, màn hình màu sắc chuẩn xác và GPU rời hiệu năng cao như dòng Asus ROG Zephyrus hay MacBook Pro."
                        reason_text = "Được trang bị CPU hiệu năng cao và card đồ họa mạnh mẽ giúp xử lý mượt mà tác vụ đồ họa và render video."
                        matched_products = [c for c in candidates if any(k in c['name'].lower() for k in ["zephyrus", "macbook", "pro", "design"])]
                    elif is_dev:
                        answer_text = "Đối với các lập trình viên và nhà phát triển phần mềm, độ bền bỉ của máy, bàn phím gõ êm ái cùng dung lượng RAM lớn là yếu tố quyết định. Dòng Lenovo ThinkPad, Dell Vostro hoặc MacBook Pro là những sự lựa chọn hàng đầu."
                        reason_text = "Cấu hình CPU mạnh mẽ kết hợp dung lượng RAM tốt và bàn phím chất lượng cao, rất phù hợp cho công việc lập trình và chạy code."
                        matched_products = [c for c in candidates if any(k in c['name'].lower() for k in ["thinkpad", "macbook", "pro", "vostro", "dev"])]
                    else:
                        answer_text = "Dựa trên yêu cầu và kết quả phân tích tiêu chí tìm kiếm của bạn, tôi xin gợi ý các dòng laptop phù hợp nhất hiện có tại hệ thống:"
                        reason_text = "Sản phẩm nổi bật phù hợp tốt nhất trong danh sách ứng viên hiện tại."
                        matched_products = candidates

                    # 4. Tạo recommendedProducts (dùng real products từ candidates nếu có)
                    recommended = []
                    if matched_products:
                        for p in matched_products[:3]:
                            recommended.append(
                                RecommendedProduct(
                                    id=p['id'],
                                    name=p['name'],
                                    price=p['price'],
                                    url=p['url'],
                                    image_url=p['image_url'],
                                    reason=reason_text
                                )
                            )
                    
                    if not recommended and candidates:
                        p = candidates[0]
                        recommended.append(
                            RecommendedProduct(
                                id=p['id'],
                                name=p['name'],
                                price=p['price'],
                                url=p['url'],
                                image_url=p['image_url'],
                                reason="Sản phẩm nổi bật từ danh sách ứng viên."
                            )
                        )

                    citations = [f"TechStore ID #{p.id}" for p in recommended]
                    
                    return LLMStructuredOutput(
                        answer=answer_text if answer_text else "Hiện tại không có câu trả lời phù hợp.",
                        confidence_score=0.95,
                        citations=citations,
                        missing_information=[],
                        recommended_products=recommended
                    )
            class MockLLM(Runnable):
                def with_structured_output(self, schema):
                    return MockStructuredLLM()
                def invoke(self, input, config=None, **kwargs):
                    return "Mock answer"
            return MockLLM()

        provider = settings.llm_provider.lower()

        if provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI

            logger.info(f"Khởi tạo Gemini LLM: {settings.llm_model_name}")
            return ChatGoogleGenerativeAI(
                model=settings.llm_model_name,
                google_api_key=settings.google_api_key,
                temperature=0.3,  # Thấp để output ổn định, có cấu trúc
            )

        elif provider == "openai":
            from langchain_openai import ChatOpenAI

            logger.info(f"Khởi tạo OpenAI LLM: {settings.llm_model_name}")
            return ChatOpenAI(
                model=settings.llm_model_name,
                api_key=settings.openai_api_key,
                temperature=0.3,
            )

        else:
            raise ValueError(f"Provider '{provider}' không được hỗ trợ.")

    def _build_prompt_template(self) -> ChatPromptTemplate:
        """Xây dựng prompt template cho LLM."""
        system_prompt = """Bạn là chuyên gia tư vấn laptop tại cửa hàng công nghệ TechStore.
Nhiệm vụ của bạn là phân tích thông tin sản phẩm và đưa ra tư vấn chuyên nghiệp, khách quan bằng tiếng Việt.

NGUYÊN TẮC TƯ VẤN:
1. Luôn khách quan, trung thực dựa trên thông số kỹ thuật thực tế
2. So sánh các sản phẩm một cách công bằng, chỉ ra ưu/nhược điểm cụ thể
3. Phù hợp với nhu cầu thực tế của khách hàng
4. Dùng ngôn ngữ thân thiện, dễ hiểu nhưng vẫn chuyên nghiệp
5. Nếu thiếu thông tin để tư vấn tốt hơn, hãy nêu rõ những gì cần hỏi thêm

⚠️ QUY TẮC BẮT BUỘC - CHỐNG BỊA ĐẶT SẢN PHẨM (PHẢI TUÂN THỦ TUYỆT ĐỐI):
1. CHỈ được đề xuất sản phẩm nằm trong danh sách "DANH SÁCH SẢN PHẨM ỨNG VIÊN" mà hệ thống cung cấp.
2. KHÔNG được tự tạo ra sản phẩm mới không có trong danh sách.
3. KHÔNG được tự bịa hoặc thay đổi ID, tên sản phẩm, giá, url, imageUrl của bất kỳ sản phẩm nào.
4. Trường recommendedProducts CHỈ được chứa các sản phẩm có ID xuất hiện trong danh sách ứng viên phía dưới.
5. Nếu không có sản phẩm nào trong danh sách phù hợp với nhu cầu khách hàng, BẮT BUỘC trả recommendedProducts = [].
6. Nếu thiếu thông tin để tư vấn chắc chắn, ghi rõ vào trường missingInformation.
7. Trường citations BẮT BUỘC phải dựa trên ID sản phẩm thật có trong danh sách ứng viên, theo dạng "TechStore ID #<id>".

QUAN TRỌNG: Bạn PHẢI trả về JSON có cấu trúc chính xác theo schema được cung cấp."""

        human_prompt = """NHU CẦU KHÁCH HÀNG:
{user_query}

TIÊU CHÍ ĐÃ PHÂN TÍCH:
- Ngân sách tối đa: {max_price}
- Thương hiệu yêu cầu: {brand}
- RAM tối thiểu: {min_ram}
- Mục đích sử dụng: {use_case}

DANH SÁCH SẢN PHẨM ỨNG VIÊN (chỉ được dùng các sản phẩm có trong danh sách này):
{product_context}

LƯU Ý: Bạn CHỈ được đề xuất sản phẩm có ID nằm trong danh sách ứng viên trên.
Nếu không có sản phẩm nào phù hợp, trả recommendedProducts = [].
Hãy phân tích và tư vấn dựa trên thông tin trên. Đưa ra câu trả lời chi tiết và các sản phẩm phù hợp nhất."""

        return ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", human_prompt)]
        )

    def _format_product_context(self, ranked_products: list[dict], max_products: int) -> str:
        """
        Định dạng thông tin sản phẩm thành text để đưa vào prompt.

        Mỗi candidate phải có đủ id, name, brand, price, ram, cpu, gpu, storage,
        url, imageUrl, score và citation để LLM có thể tham chiếu chính xác.

        Args:
            ranked_products: Danh sách sản phẩm đã xếp hạng
            max_products: Số sản phẩm tối đa đưa vào context

        Returns:
            Chuỗi văn bản mô tả các sản phẩm
        """
        context_parts = []

        for i, product in enumerate(ranked_products[:max_products], 1):
            metadata = product.get("metadata", {})
            total_score = product.get("total_score", 0)
            vector_score = product.get("vector_score", 0)
            bonus_score = product.get("bonus_score", 0)
            score_details = product.get("score_details", [])
            product_id = metadata.get("product_id", "N/A")

            product_info = [
                f"--- SẢN PHẨM #{i} ---",
                f"ID: {product_id}",
                f"Tên: {metadata.get('name', 'N/A')}",
                f"Thương hiệu: {metadata.get('brand', 'N/A').upper()}",
                f"Giá: {metadata.get('price', 0):,.0f} VND",
                f"CPU: {metadata.get('cpu', 'N/A')}",
                f"RAM: {metadata.get('ram', 'N/A')}GB",
                f"GPU: {metadata.get('gpu', 'Tích hợp')}",
                f"Ổ cứng: {metadata.get('storage', 'N/A')}",
                f"URL: {metadata.get('url', '')}",
                f"imageUrl: {metadata.get('image_url', '')}",
                f"Điểm phù hợp: {total_score:.2f} (vector={vector_score:.2f}, bonus={bonus_score:.1f})",
                f"Chi tiết điểm: {', '.join(score_details) if score_details else 'N/A'}",
                f"Nguồn trích dẫn: TechStore ID #{product_id}",
            ]

            if metadata.get("screen_size"):
                product_info.append(f"Màn hình: {metadata.get('screen_size')} inch")

            if metadata.get("weight"):
                product_info.append(f"Trọng lượng: {metadata.get('weight')}kg")

            if metadata.get("is_hot"):
                product_info.append("⭐ Sản phẩm BÁN CHẠY")

            if metadata.get("use_case_tags"):
                product_info.append(f"Phù hợp cho: {metadata.get('use_case_tags')}")

            context_parts.append("\n".join(product_info))

        if not context_parts:
            return "Không tìm thấy sản phẩm phù hợp trong hệ thống."

        # Thêm nhắc nhở cuối để chắc chắn LLM không bịa sản phẩm
        header = (
            f"Tổng số sản phẩm ứng viên hợp lệ: {len(ranked_products[:max_products])}.\n"
            "BẮT BUỘC: Chỉ đề xuất sản phẩm có ID nằm trong danh sách trên.\n\n"
        )
        return header + "\n\n".join(context_parts)

    def _calculate_confidence_score(
        self, ranked_products: list[dict], parsed_query: ParsedQuery
    ) -> float:
        """
        Tính confidence score tổng thể của câu trả lời.

        Dựa trên:
        - Điểm similarity của sản phẩm top 1
        - Số lượng sản phẩm tìm được
        - Mức độ khớp với tiêu chí
        """
        if not ranked_products:
            return 0.1

        # Lấy similarity score của sản phẩm tốt nhất
        top_similarity = ranked_products[0].get("similarity_score", 0.0)

        # Hệ số dựa trên số lượng sản phẩm tìm được
        product_count_factor = min(len(ranked_products) / 5.0, 1.0)

        # Hệ số dựa trên có tìm được sản phẩm khớp tiêu chí không
        criteria_match_factor = 0.7  # Mặc định
        if ranked_products[0].get("bonus_score", 0) >= 3:
            criteria_match_factor = 0.95  # Khớp tốt
        elif ranked_products[0].get("bonus_score", 0) >= 1:
            criteria_match_factor = 0.80

        # Tính điểm tổng hợp
        confidence = (
            top_similarity * 0.5
            + product_count_factor * 0.2
            + criteria_match_factor * 0.3
        )

        return round(min(max(confidence, 0.0), 1.0), 2)

    def _validate_and_repair_products(
        self,
        result: LLMStructuredOutput,
        ranked_products: list[dict],
        max_products: int,
        confidence: float,
    ) -> LLMStructuredOutput:
        """
        Validate và sửa chữa danh sách recommendedProducts do LLM trả về.

        Quy trình:
        1. Xây dựng bảng tra cứu candidate_ids và metadata từ ranked_products.
        2. Lọc bỏ mọi sản phẩm có id không nằm trong candidates (hallucination).
        3. Bổ sung url/imageUrl/price/name từ metadata thật nếu LLM bỏ trống/bịa.
        4. Tạo reason fallback nếu LLM để trống.
        5. Nếu toàn bộ sản phẩm bị lọc: override answer + giảm confidence.

        Args:
            result: Structured output thô từ LLM.
            ranked_products: Danh sách candidates đã xếp hạng (ground truth).
            max_products: Số sản phẩm tối đa được phép trả về.
            confidence: Confidence score đã tính trước đó.

        Returns:
            LLMStructuredOutput đã được validate và sửa chữa.
        """
        from schemas import RecommendedProduct

        # --- Bước 1: Xây dựng bảng tra cứu từ candidates (ground truth) ---
        candidate_map: dict[int, dict] = {}
        for product in ranked_products[:max_products]:
            metadata = product.get("metadata", {})
            pid = metadata.get("product_id")
            if pid is not None:
                candidate_map[int(pid)] = {
                    "metadata": metadata,
                    "total_score": product.get("total_score", 0),
                    "score_details": product.get("score_details", []),
                }

        candidate_ids = set(candidate_map.keys())
        logger.info(
            f"[Validate] candidate_ids hợp lệ: {sorted(candidate_ids)}"
        )

        # --- Bước 2: Lọc + sửa chữa từng sản phẩm LLM trả về ---
        original_count = len(result.recommended_products)
        validated: list[RecommendedProduct] = []

        for item in result.recommended_products:
            try:
                item_id = int(item.id)
            except (TypeError, ValueError):
                logger.warning(
                    f"[Validate] Sản phẩm có id không hợp lệ: {item.id!r} — loại bỏ."
                )
                continue

            if item_id not in candidate_ids:
                logger.warning(
                    f"[Validate] Sản phẩm ID={item_id} KHÔNG nằm trong candidates "
                    f"— đây là hallucination, loại bỏ."
                )
                continue

            # Lấy metadata ground truth từ candidate
            ground_truth = candidate_map[item_id]["metadata"]
            score_details = candidate_map[item_id]["score_details"]
            total_score = candidate_map[item_id]["total_score"]

            # --- Bước 3: Bổ sung/sửa các trường bị thiếu hoặc sai ---
            repaired_name = item.name or ground_truth.get("name", "")
            repaired_price = item.price if item.price and item.price > 0 else ground_truth.get("price", 0)
            repaired_url = item.url or ground_truth.get("url", "")
            # imageUrl có thể được LLM gán qua alias hoặc field name
            llm_image_url = getattr(item, "image_url", None) or getattr(item, "imageUrl", None) or ""
            repaired_image_url = llm_image_url or ground_truth.get("image_url", "")

            # --- Bước 4: Tạo reason fallback nếu LLM để trống ---
            if item.reason and item.reason.strip():
                repaired_reason = item.reason.strip()
            else:
                details_str = ", ".join(score_details) if score_details else "phù hợp với tiêu chí tìm kiếm"
                repaired_reason = (
                    f"{ground_truth.get('name', 'Sản phẩm')} (ID #{item_id}) "
                    f"được đề xuất với điểm phù hợp {total_score:.1f}. "
                    f"Lý do: {details_str}."
                )

            validated.append(
                RecommendedProduct(
                    id=item_id,
                    name=repaired_name,
                    price=repaired_price,
                    url=repaired_url,
                    imageUrl=repaired_image_url,
                    reason=repaired_reason,
                )
            )

        removed_count = original_count - len(validated)
        if removed_count > 0:
            logger.warning(
                f"[Validate] Đã loại bỏ {removed_count}/{original_count} sản phẩm "
                f"do hallucination hoặc ID không hợp lệ."
            )

        result.recommended_products = validated

        # --- Bước 5: Nếu toàn bộ sản phẩm bị loại bỏ ---
        if not validated:
            logger.warning(
                "[Validate] Tất cả sản phẩm LLM đề xuất đều không hợp lệ. "
                "Override answer và giảm confidence."
            )
            result.answer = (
                "Hệ thống chưa tìm thấy sản phẩm phù hợp với nhu cầu của bạn "
                "trong dữ liệu hiện có. Bạn có thể thử điều chỉnh ngân sách, "
                "thương hiệu hoặc yêu cầu cấu hình để tìm kiếm chính xác hơn."
            )
            result.confidence_score = min(confidence, 0.30)
        else:
            result.confidence_score = confidence

        return result

    def generate(
        self,
        user_query: str,
        parsed_query: ParsedQuery,
        ranked_products: list[dict],
        max_products: int,
    ) -> LLMStructuredOutput:
        """
        Gọi LLM với structured output để tạo câu trả lời JSON.

        Args:
            user_query: Câu hỏi gốc của người dùng
            parsed_query: Kết quả phân tích câu hỏi
            ranked_products: Danh sách sản phẩm đã xếp hạng
            max_products: Số lượng sản phẩm tối đa đưa vào response

        Returns:
            LLMStructuredOutput đã được validate chống hallucination
        """
        # Chuẩn bị context cho prompt
        product_context = self._format_product_context(ranked_products, max_products)

        # Tính confidence score
        confidence = self._calculate_confidence_score(ranked_products, parsed_query)

        # Chuẩn bị các biến cho prompt
        prompt_variables = {
            "user_query": user_query,
            "product_context": product_context,
            "max_price": (
                f"{parsed_query.max_price:,.0f} VND"
                if parsed_query.max_price
                else "Không xác định"
            ),
            "brand": parsed_query.brand or "Không yêu cầu",
            "min_ram": (
                f"{parsed_query.min_ram}GB"
                if parsed_query.min_ram
                else "Không yêu cầu"
            ),
            "use_case": parsed_query.use_case or "Đa năng",
        }

        try:
            logger.info(
                f"Đang gọi LLM để tạo câu trả lời. "
                f"Số sản phẩm context: {min(len(ranked_products), max_products)}"
            )

            # Tạo chain: prompt | structured_llm
            chain = self.prompt_template | self.structured_llm

            # Gọi LLM với structured output
            result: LLMStructuredOutput = chain.invoke(prompt_variables)

            logger.info("Gọi LLM thành công, đã nhận được structured output thô.")

            # ---- POST-LLM VALIDATION: chống hallucination ----
            logger.info(
                f"[Validate] Bắt đầu kiểm tra {len(result.recommended_products)} sản phẩm "
                f"LLM trả về so với {min(len(ranked_products), max_products)} candidates hợp lệ."
            )
            result = self._validate_and_repair_products(
                result=result,
                ranked_products=ranked_products,
                max_products=max_products,
                confidence=confidence,
            )
            logger.info(
                f"[Validate] Sau validate: {len(result.recommended_products)} sản phẩm hợp lệ, "
                f"confidence={result.confidence_score}"
            )

            return result

        except Exception as e:
            logger.error(f"Lỗi khi gọi LLM: {e}", exc_info=True)

            # Fallback: tạo response cơ bản khi LLM lỗi
            return self._create_fallback_response(
                ranked_products, max_products, confidence
            )

    def _create_fallback_response(
        self,
        ranked_products: list[dict],
        max_products: int,
        confidence: float,
    ) -> LLMStructuredOutput:
        """
        Tạo response dự phòng khi LLM gặp lỗi.
        Sử dụng thông tin sản phẩm trực tiếp từ metadata.
        """
        from schemas import RecommendedProduct

        recommended = []
        for product in ranked_products[:max_products]:
            metadata = product.get("metadata", {})
            recommended.append(
                RecommendedProduct(
                    id=metadata.get("product_id", 0),
                    name=metadata.get("name", ""),
                    price=metadata.get("price", 0),
                    url=metadata.get("url", ""),
                    imageUrl=metadata.get("image_url", ""),
                    reason="Sản phẩm phù hợp dựa trên tiêu chí tìm kiếm.",
                )
            )

        return LLMStructuredOutput(
            answer=(
                f"Dựa trên nhu cầu của bạn, hệ thống đề xuất các laptop sau: "
                f"{', '.join([m.get('metadata', {}).get('name', '') for m in ranked_products[:max_products]])}. "
                "Vui lòng xem chi tiết từng sản phẩm để lựa chọn phù hợp."
            ),
            confidenceScore=confidence,
            citations=[
                f"Thông số kỹ thuật từ TechStore ID #{m.get('metadata', {}).get('product_id', 'N/A')}"
                for m in ranked_products[:max_products]
            ],
            missingInformation=[
                "Không thể tạo tư vấn chi tiết do lỗi hệ thống. Vui lòng thử lại sau."
            ],
            recommendedProducts=recommended,
        )


# =============================================================================
# RAG SERVICE - Điều phối toàn bộ pipeline
# =============================================================================


class RAGService:
    """
    Dịch vụ RAG chính, điều phối toàn bộ luồng xử lý:
    Query Parser → Metadata Filter → Vector Search → Scoring → LLM
    """

    def __init__(self, db_manager: ChromaDBManager):
        self.db_manager = db_manager
        self.query_parser = QueryParser()
        self.scoring_engine = ScoringEngine()
        self.recommendation_generator = RecommendationGenerator()
        logger.info("RAGService đã khởi tạo thành công.")

    def process_chat(
        self,
        request: ChatRequest,
    ) -> LLMStructuredOutput:
        """
        Xử lý request chat và trả về kết quả RAG có cấu trúc.

        Luồng xử lý:
        1. Parse câu hỏi → trích xuất tiêu chí
        2. Xây dựng metadata filter
        3. Query ChromaDB (filter + vector search)
        4. Scoring & re-ranking
        5. Gọi LLM tạo kết quả JSON

        Args:
            request: ChatRequest từ API endpoint

        Returns:
            LLMStructuredOutput với đầy đủ thông tin
        """
        user_query = request.message
        max_products = request.top_k or settings.max_recommended_products

        logger.info(f"Bắt đầu xử lý chat request: '{user_query[:80]}'")

        # ---- BƯỚC 1: Parse câu hỏi ----
        logger.info("Bước 1: Phân tích câu hỏi...")
        parsed_query = self.query_parser.parse(user_query)

        logger.info(
            f"Kết quả parse: brand={parsed_query.brand}, "
            f"max_price={parsed_query.max_price}, "
            f"min_ram={parsed_query.min_ram}, "
            f"use_case={parsed_query.use_case}"
        )

        # ---- BƯỚC 2: Xây dựng metadata filter ----
        logger.info("Bước 2: Xây dựng metadata filter...")
        metadata_filter = self.db_manager.build_metadata_filter(
            {
                "brand": parsed_query.brand,
                "max_price": parsed_query.max_price,
                "min_price": parsed_query.min_price,
                "min_ram": parsed_query.min_ram,
            }
        )
        logger.info(f"Metadata filter: {metadata_filter}")

        # ---- BƯỚC 3: Query ChromaDB ----
        logger.info("Bước 3: Thực hiện Vector Search + Metadata Filter...")
        n_results = min(
            settings.top_k_results * 2,  # Lấy nhiều hơn để scoring có đủ data
            50,  # Giới hạn tối đa
        )

        candidates = self.db_manager.query_with_filter(
            query_text=parsed_query.semantic_query,
            metadata_filter=metadata_filter,
            n_results=n_results,
        )

        logger.info(f"Tìm được {len(candidates)} ứng viên từ vector search.")

        # Nếu filter quá chặt và không tìm được kết quả, thử lại không filter
        if not candidates and metadata_filter:
            logger.warning(
                "Không tìm thấy kết quả với filter. "
                "Thử lại không có metadata filter..."
            )
            candidates = self.db_manager.query_with_filter(
                query_text=parsed_query.semantic_query,
                metadata_filter=None,
                n_results=settings.top_k_results,
            )

        # ---- BƯỚC 4: Scoring & Re-ranking ----
        logger.info("Bước 4: Chấm điểm và xếp hạng sản phẩm...")
        ranked_products = self.scoring_engine.score_candidates(
            candidates=candidates,
            parsed_query=parsed_query,
        )

        logger.info(
            f"Top 3 sản phẩm sau ranking: "
            + str(
                [
                    f"{p.get('metadata', {}).get('name', 'N/A')} ({p.get('total_score', 0):.1f}đ)"
                    for p in ranked_products[:3]
                ]
            )
        )

        # ---- BƯỚC 5: Gọi LLM tạo kết quả ----
        logger.info("Bước 5: Gọi LLM để tạo câu trả lời có cấu trúc...")
        result = self.recommendation_generator.generate(
            user_query=user_query,
            parsed_query=parsed_query,
            ranked_products=ranked_products,
            max_products=max_products,
        )

        logger.info(
            f"Hoàn thành xử lý. "
            f"Confidence: {result.confidence_score}, "
            f"Số sản phẩm đề xuất: {len(result.recommended_products)}"
        )

        return result
