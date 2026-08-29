import os
import sys

# Script tự động cài đặt reportlab nếu chưa có và tạo tài liệu PDF
try:
    import reportlab
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, ListFlowable, ListItem
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# 1. Đăng ký Font hỗ trợ tiếng Việt (Arial có sẵn trên Windows)
font_path = "C:\\Windows\\Fonts\\arial.ttf"
font_bold_path = "C:\\Windows\\Fonts\\arialbd.ttf"
font_italic_path = "C:\\Windows\\Fonts\\ariali.ttf"
font_bold_italic_path = "C:\\Windows\\Fonts\\arialbi.ttf"

if not os.path.exists(font_path):
    # Fallback nếu chạy ở môi trường Linux/macOS không có font Arial của Windows
    # Tìm kiếm font hệ thống phổ biến
    alternative_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "arial.ttf"
    ]
    for p in alternative_paths:
        if os.path.exists(p):
            font_path = p
            font_bold_path = p
            font_italic_path = p
            font_bold_italic_path = p
            break

try:
    pdfmetrics.registerFont(TTFont("Arial", font_path))
    pdfmetrics.registerFont(TTFont("Arial-Bold", font_bold_path))
    pdfmetrics.registerFont(TTFont("Arial-Italic", font_italic_path))
    pdfmetrics.registerFont(TTFont("Arial-BoldItalic", font_bold_italic_path))
    print("Arial font registered successfully.")
except Exception as e:
    print(f"Cannot register Arial font: {e}. Using default Helvetica.")
    pdfmetrics.registerFont(TTFont("Arial", "Helvetica"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", "Helvetica-Bold"))
    pdfmetrics.registerFont(TTFont("Arial-Italic", "Helvetica-Oblique"))
    pdfmetrics.registerFont(TTFont("Arial-BoldItalic", "Helvetica-BoldOblique"))

# 2. Định nghĩa Custom Canvas để vẽ Header, Footer và đánh số trang động (Numbered Canvas)
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_elements(num_pages)
            super().showPage()
        super().save()

    def draw_page_elements(self, page_count):
        # Không vẽ header/footer trên trang bìa (trang 1)
        if self._pageNumber == 1:
            return

        self.saveState()
        
        # Thiết lập màu sắc và nét vẽ
        primary_color = colors.HexColor("#0f172a") # Navy sẫm
        gray_color = colors.HexColor("#64748b") # Slate gray
        border_color = colors.HexColor("#e2e8f0") # Light gray
        
        # --- HEADER ---
        self.setStrokeColor(border_color)
        self.setLineWidth(0.75)
        self.line(54, 790, 541, 790) # Đường kẻ trên
        
        self.setFont("Arial-Bold", 8)
        self.setFillColor(primary_color)
        self.drawString(54, 797, "TÀI LIỆU SẢN PHẨM & ĐẶC TẢ KỸ THUẬT")
        
        self.setFont("Arial", 8)
        self.setFillColor(gray_color)
        self.drawRightString(541, 797, "Hệ thống Product-Comparison-RAG")
        
        # --- FOOTER ---
        self.line(54, 55, 541, 55) # Đường kẻ dưới
        
        self.setFont("Arial", 8)
        self.setFillColor(gray_color)
        self.drawString(54, 40, "Tài liệu đào tạo AI Intern & Hướng dẫn tích hợp Spring Boot")
        
        page_str = f"Trang {self._pageNumber} / {page_count}"
        self.drawRightString(541, 40, page_str)
        
        self.restoreState()


def create_product_pdf(filename="AI_Laptop_Copilot_Product_Document.pdf"):
    # Margins: 54pt (~0.75 inch)
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # 3. Tạo styles tùy chỉnh hỗ trợ tiếng Việt & màu sắc hiện đại
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#1e3a8a"), # Navy
        alignment=1, # Center
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Arial',
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#475569"), # Slate
        alignment=1, # Center
        spaceAfter=30
    )
    
    meta_style = ParagraphStyle(
        'CoverMeta',
        parent=styles['Normal'],
        fontName='Arial-Italic',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        alignment=1,
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'H1_Custom',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=15,
        spaceAfter=10,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2_Custom',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f766e"), # Teal
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'H3_Custom',
        parent=styles['Normal'],
        fontName='Arial-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#b45309"), # Amber
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Arial',
        fontSize=9.5,
        leading=14.5,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=8
    )

    body_bold = ParagraphStyle(
        'Body_Bold',
        parent=body_style,
        fontName='Arial-Bold'
    )

    body_italic = ParagraphStyle(
        'Body_Italic',
        parent=body_style,
        fontName='Arial-Italic',
        textColor=colors.HexColor("#475569")
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Arial', # Sử dụng Arial thay Courier để hiển thị đúng unicode tiếng Việt
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderColor=colors.HexColor("#cbd5e1"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=6
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=body_style,
        backColor=colors.HexColor("#f8fafc"),
        borderColor=colors.HexColor("#3b82f6"),
        borderWidth=1.5,
        borderPadding=8,
        spaceBefore=8,
        spaceAfter=8
    )

    story = []

    # =========================================================================
    # TRANG BÌA (COVER PAGE)
    # =========================================================================
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("TÀI LIỆU YÊU CẦU SẢN PHẨM & ĐẶC TẢ KỸ THUẬT", ParagraphStyle('CoverPre', parent=body_style, fontName='Arial-Bold', fontSize=10, textColor=colors.HexColor("#2563eb"), alignment=1, spaceAfter=10)))
    story.append(Paragraph("HỆ THỐNG AI LAPTOP COPILOT<br/>(PRODUCT-COMPARISON-RAG)", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Giải pháp Trợ lý ảo Tư vấn và So sánh Laptop cấu hình thời gian thực<br/>kết hợp FastAPI, ChromaDB và Gemini/OpenAI", subtitle_style))
    
    # Vẽ một đường kẻ trang trí ở trang bìa
    d_table = Table([[""]], colWidths=[300], rowHeights=[2])
    d_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#2563eb")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER')
    ]))
    story.append(d_table)
    story.append(Spacer(1, 2 * inch))

    story.append(Paragraph("<b>Tác giả:</b> Đội ngũ Phát triển AI & Antigravity Assistant", meta_style))
    story.append(Paragraph("<b>Đối tượng độc giả:</b> AI Intern, Kỹ sư tích hợp hệ thống, Hội đồng Mentors", meta_style))
    story.append(Paragraph("<b>Phiên bản tài liệu:</b> 1.0.0 (Mức độ chi tiết nâng cao)", meta_style))
    story.append(Paragraph("<b>Ngày phát hành:</b> 14 tháng 07 năm 2026", meta_style))
    story.append(PageBreak())

    # =========================================================================
    # CHƯƠNG 1: TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)
    # =========================================================================
    story.append(Paragraph("CHƯƠNG 1: TỔNG QUAN DỰ ÁN (PROJECT OVERVIEW)", h1_style))
    story.append(Paragraph("<b>1.1 Bối cảnh và Vấn đề thực tế (Problem Statement)</b>", h2_style))
    story.append(Paragraph(
        "Trong lĩnh vực thương mại điện tử bán lẻ thiết bị công nghệ, đặc biệt là Laptop, khách hàng thường gặp khó khăn lớn khi lựa chọn sản phẩm phù hợp do tính chất đa dạng của thương hiệu, mẫu mã và các thông số kỹ thuật phức tạp (CPU thế hệ mới, GPU rời, dung lượng RAM, tốc độ ổ cứng, loại màn hình...). Các chatbot AI thông dụng hiện nay (chỉ sử dụng mô hình ngôn ngữ lớn LLM độc lập) thường gặp phải các hạn chế nghiêm trọng sau:",
        body_style
    ))
    
    bullet_style = ParagraphStyle('BulletText', parent=body_style, leftIndent=20, firstLineIndent=-10, spaceAfter=4)
    story.append(Paragraph("• <b>Hiện tượng ảo giác (Hallucination):</b> LLM tự bịa ra thông số kỹ thuật hoặc gán ghép sai cấu hình (ví dụ: gán card đồ họa RTX 4060 cho Macbook Air) do không được cung cấp cơ sở tri thức chính xác.", bullet_style))
    story.append(Paragraph("• <b>Thiếu dữ liệu thời gian thực:</b> LLM không biết được chính xác giá bán hiện tại tại cửa hàng, các chương trình khuyến mãi đang chạy, hoặc tình trạng tồn kho thực tế (còn hàng hay hết hàng).", bullet_style))
    story.append(Paragraph("• <b>Thiếu tính định hướng nghiệp vụ:</b> AI gợi ý các sản phẩm đã dừng kinh doanh hoặc các sản phẩm có biên lợi nhuận thấp thay vì ưu tiên các sản phẩm chiến lược, sản phẩm HOT đang sẵn hàng.", bullet_style))

    story.append(Paragraph("<b>1.2 Giải pháp và Mục tiêu của hệ thống (Solution & Goals)</b>", h2_style))
    story.append(Paragraph(
        "Dự án <b>Product-Comparison-RAG</b> ra đời nhằm xây dựng một Microservice AI chuyên biệt đóng vai trò là một <b>AI Laptop Copilot</b>. Hệ thống sử dụng kỹ thuật <b>RAG (Retrieval-Augmented Generation)</b> cải tiến để khắc phục triệt để các vấn đề trên. Mục tiêu cốt lõi bao gồm:",
        body_style
    ))
    story.append(Paragraph("1. <b>Chính xác tuyệt đối:</b> Đảm bảo toàn bộ thông tin về thông số kỹ thuật, giá bán và đường dẫn sản phẩm được phản hồi đúng 100% so với cơ sở dữ liệu thực tế của cửa hàng.", bullet_style))
    story.append(Paragraph("2. <b>Bộ lọc thuộc tính cứng kết hợp tìm kiếm ngữ nghĩa (Hybrid Search):</b> Giải quyết triệt để bài toán lọc cứng theo khoảng giá (ví dụ: dưới 25 triệu), RAM (ví dụ: tối thiểu 16GB) và thương hiệu trước khi tìm kiếm ngữ nghĩa.", bullet_style))
    story.append(Paragraph("3. <b>Đồng bộ hóa dữ liệu thời gian thực:</b> Cung cấp các API RESTful giúp website chính (Java Spring Boot) đồng bộ ngay lập tức thông tin khi admin Thêm/Sửa/Xóa sản phẩm hoặc cập nhật tồn kho.", bullet_style))
    story.append(Paragraph("4. <b>Xếp hạng thông minh (Scoring Engine):</b> Tối ưu hóa gợi ý bằng cách chấm điểm bổ sung dựa trên nhu cầu thực tế (gaming, đồ họa, văn phòng) và các yếu tố nghiệp vụ (sản phẩm HOT, sản phẩm còn hàng).", bullet_style))

    story.append(Paragraph("<b>1.3 Kiến trúc tổng thể và Sự phân tách trách nhiệm (Architecture & Separation of Concerns)</b>", h2_style))
    story.append(Paragraph(
        "Hệ thống được thiết kế theo mô hình Microservice hiện đại, chia tách rõ ràng trách nhiệm giữa hai phần:",
        body_style
    ))
    
    # Bảng mô tả vai trò
    arch_data = [
        [Paragraph("<b>Hệ thống chính (Java Spring Boot)</b>", body_bold), Paragraph("<b>Microservice AI (Python FastAPI)</b>", body_bold)],
        [
            Paragraph("• Quản lý giao diện khách hàng (UI/UX), giỏ hàng, đơn đặt hàng, thanh toán.<br/>• Quản lý Database quan hệ chính (MySQL/PostgreSQL) lưu thông tin sản phẩm đầy đủ.<br/>• Đóng vai trò Master: Đồng bộ dữ liệu sang AI Service khi có sự kiện Thêm/Sửa/Xóa laptop.", body_style),
            Paragraph("• Quản lý Vector Database cục bộ (ChromaDB) chuyên dụng.<br/>• Thực hiện trích xuất ý định câu hỏi (Query Parser), Metadata Filter và Vector Search.<br/>• Tương tác với LLM (Gemini/OpenAI) qua LangChain để tạo câu trả lời JSON có cấu trúc.<br/>• Kiểm tra chéo chống ảo giác (Anti-hallucination layer).", body_style)
        ]
    ]
    arch_table = Table(arch_data, colWidths=[240, 240])
    arch_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(arch_table)
    story.append(Spacer(1, 10))

    # Sơ đồ khối ASCII
    story.append(Paragraph("<b>Sơ đồ tương tác luồng dữ liệu RESTful:</b>", body_bold))
    story.append(Paragraph(
        "[Khách Hàng] ==(Gửi câu hỏi)==> [Spring Boot Web] ==(API Chat /api/chat)==> [FastAPI AI Service]<br/>"
        "                                                                                    │<br/>"
        "                                                                           (RAG Pipeline xử lý)<br/>"
        "                                                                                    │<br/>"
        "[Khách Hàng] <==(Hiển thị Cards)== [Spring Boot Web] <==(Trả về JSON camelCase) <====┘",
        code_style
    ))
    
    story.append(PageBreak())

    # =========================================================================
    # CHƯƠNG 2: RAG PIPELINE CẢI TIẾN (ADVANCED RAG PIPELINE)
    # =========================================================================
    story.append(Paragraph("CHƯƠNG 2: RAG PIPELINE CẢI TIẾN (ADVANCED RAG PIPELINE)", h1_style))
    story.append(Paragraph(
        "RAG Pipeline thông thường chỉ lấy câu hỏi của người dùng đi tìm kiếm vector và đưa vào LLM. Điều này dẫn đến tỷ lệ gợi ý sai lệch thông số cứng rất cao (ví dụ: khách yêu cầu máy dưới 20 triệu nhưng vector tương đồng lại gợi ý máy 40 triệu). Hệ thống <b>Product-Comparison-RAG</b> giải quyết triệt để bằng pipeline 6 bước nghiêm ngặt sau:",
        body_style
    ))

    # Sơ đồ Pipeline
    pipeline_steps = [
        ("1. Query Parser", "Nhận dạng ý định (Chat/So sánh) & các thông số cứng (khoảng giá, RAM, CPU/GPU, use case) bằng Regex & Heuristic Rule-based nhằm tối ưu hóa chi phí và tốc độ xử lý."),
        ("2. Metadata Filter", "Biên dịch tiêu chí cứng thành bộ lọc ChromaDB (Metadata Pre-filtering). Khoanh vùng không gian tìm kiếm chính xác trước khi tính độ tương đồng vector."),
        ("3. Vector Search", "Nhúng câu truy vấn ngữ nghĩa thành vector (Embedding) và thực hiện tìm kiếm Top-K laptop tương đồng ngữ nghĩa nhất trong tập sản phẩm đã được lọc cứng."),
        ("4. Scoring & Re-ranking", "Bộ chấm điểm nghiệp vụ (Scoring Engine) tính toán lại thứ tự xếp hạng của laptop dựa trên mức độ phù hợp phần cứng, tình trạng hàng trong kho và độ HOT."),
        ("5. LLM Structured Output", "Sử dụng Langchain parser ép LLM trả về cấu trúc JSON chính xác theo Schema định nghĩa bằng Pydantic (chứa câu trả lời tư vấn, trích dẫn nguồn, sản phẩm gợi ý)."),
        ("6. Anti-Hallucination Layer", "Tầng hậu xử lý (Post-processing) kiểm tra chéo ID sản phẩm do LLM đề xuất với DB thực tế, loại bỏ sản phẩm ảo giác, và đè thông tin gốc chống LLM bịa đặt.")
    ]
    
    for step_title, step_desc in pipeline_steps:
        story.append(Paragraph(f"<b>{step_title}</b>", h2_style))
        story.append(Paragraph(step_desc, body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>2.1 Chi tiết Thuật toán chấm điểm của Scoring Engine</b>", h2_style))
    story.append(Paragraph(
        "Scoring Engine giải quyết bài toán nghiệp vụ kinh doanh laptop thực tế bằng cách điều chỉnh thứ tự gợi ý dựa trên sự kết hợp giữa toán học vector cosine và các luật heuristics của con người. Công thức tính điểm tổng quát như sau:",
        body_style
    ))
    
    # Công thức toán học (latex style) hiển thị đẹp
    story.append(Paragraph(
        "$$Score_{Total} = (Similarity_{Vector} \\times 5.0) + Bonus_{Business} - Penalties$$",
        ParagraphStyle('MathStyle', parent=body_style, fontName='Arial-Bold', fontSize=11, alignment=1, spaceBefore=8, spaceAfter=8, textColor=colors.HexColor("#0f766e"))
    ))
    
    story.append(Paragraph("<b>Bảng chi tiết các luật chấm điểm bổ sung (Bonus & Penalty):</b>", body_bold))
    
    rules_data = [
        [Paragraph("<b>Tiêu chí chấm điểm</b>", body_bold), Paragraph("<b>Mức điểm ảnh hưởng</b>", body_bold), Paragraph("<b>Ý nghĩa nghiệp vụ</b>", body_bold)],
        [
            Paragraph("Khớp thương hiệu yêu cầu", body_style),
            Paragraph("<b>+3.0 điểm</b>", body_style),
            Paragraph("Ưu tiên tối đa các sản phẩm thuộc thương hiệu khách hàng chỉ định trong câu hỏi.", body_style)
        ],
        [
            Paragraph("Khớp khoảng giá yêu cầu (biên độ dao động ±20%)", body_style),
            Paragraph("<b>+2.0 điểm</b>", body_style),
            Paragraph("Khuyến khích các máy nằm sát tầm giá ngân sách mong muốn của khách hàng.", body_style)
        ],
        [
            Paragraph("Khớp dòng CPU yêu cầu (i5, i7, ryzen 7...)", body_style),
            Paragraph("<b>+2.0 điểm</b>", body_style),
            Paragraph("Ưu tiên đúng thế hệ vi xử lý khách hàng mong muốn.", body_style)
        ],
        [
            Paragraph("Khớp chính xác card đồ họa (GPU)", body_style),
            Paragraph("<b>+3.0 điểm</b>", body_style),
            Paragraph("Rất quan trọng với nhóm khách hàng chuyên nghiệp, game thủ hoặc designer.", body_style)
        ],
        [
            Paragraph("Sản phẩm HOT (isHot = True)", body_style),
            Paragraph("<b>+1.0 điểm</b>", body_style),
            Paragraph("Thúc đẩy doanh số bằng cách ưu tiên giới thiệu sản phẩm bán chạy của hệ thống.", body_style)
        ],
        [
            Paragraph("RAM đáp ứng tối thiểu", body_style),
            Paragraph("Đủ RAM: <b>+2.0 điểm</b><br/>Thiếu RAM: <b>-1.0 điểm (Phạt)</b>", body_style),
            Paragraph("Đảm bảo máy gợi ý chạy tốt tác vụ. Phạt nếu RAM máy nhỏ hơn yêu cầu của khách.", body_style)
        ],
        [
            Paragraph("GPU rời cho tác vụ nặng (Gaming/Design)", body_style),
            Paragraph("Có card rời: <b>+2.0 điểm</b><br/>Card tích hợp: <b>-1.0 điểm (Phạt)</b>", body_style),
            Paragraph("Tránh gợi ý card đồ họa tích hợp yếu cho khách cần chơi game nặng hoặc render video.", body_style)
        ],
        [
            Paragraph("Kiểm tra tồn kho (Stock check)", body_style),
            Paragraph("Còn hàng: <b>+0.5 điểm</b><br/>Hết hàng: <b>-5.0 điểm (Phạt nặng)</b>", body_style),
            Paragraph("<b>Quy tắc sống còn:</b> Đẩy sản phẩm hết hàng xuống cuối cùng để tránh việc AI tư vấn sản phẩm khách không thể mua.", body_style)
        ]
    ]
    
    rules_table = Table(rules_data, colWidths=[150, 110, 220])
    rules_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(rules_table)
    
    story.append(PageBreak())

    # =========================================================================
    # CHƯƠNG 3: THIẾT KẾ API VÀ HƯỚNG DẪN TÍCH HỢP SPRING BOOT
    # =========================================================================
    story.append(Paragraph("CHƯƠNG 3: THIẾT KẾ API VÀ HƯỚNG DẪN TÍCH HỢP (SPRING BOOT)", h1_style))
    story.append(Paragraph(
        "Hệ thống RAG Service cung cấp các REST API chuẩn hóa sử dụng định dạng JSON. Để thuận tiện nhất cho việc chuyển giao cấu trúc dữ liệu sang Java (Spring Boot DTO), toàn bộ dữ liệu phản hồi nghiệp vụ đều được ánh xạ tự động sang định dạng <b>camelCase</b>.",
        body_style
    ))
    
    story.append(Paragraph("<b>3.1 Đặc tả các API chính</b>", h2_style))
    
    # Bảng đặc tả endpoint
    api_list_data = [
        [Paragraph("<b>HTTP Method & Path</b>", body_bold), Paragraph("<b>Mô tả vai trò trong hệ thống</b>", body_bold), Paragraph("<b>Payload chính</b>", body_bold)],
        [
            Paragraph("<font color='#097969'><b>GET</b></font> /health", body_style),
            Paragraph("Kiểm tra trạng thái hoạt động của server và cấu hình LLM hiện tại.", body_style),
            Paragraph("Không", body_style)
        ],
        [
            Paragraph("<font color='#097969'><b>GET</b></font> /api/stats", body_style),
            Paragraph("Trả về thống kê số lượng sản phẩm hiện có trong vector database.", body_style),
            Paragraph("Không", body_style)
        ],
        [
            Paragraph("<font color='#b8860b'><b>POST</b></font> /api/sync-product", body_style),
            Paragraph("Đồng bộ (thêm/cập nhật) thông tin một laptop từ Spring Boot sang ChromaDB.", body_style),
            Paragraph("Thông tin chi tiết laptop (JSON)", body_style)
        ],
        [
            Paragraph("<font color='#b8860b'><b>POST</b></font> /api/sync-product/bulk", body_style),
            Paragraph("Đồng bộ hàng loạt laptop cùng lúc. Dùng khi import dữ liệu ban đầu.", body_style),
            Paragraph("Danh sách các sản phẩm (JSON)", body_style)
        ],
        [
            Paragraph("<font color='#8b0000'><b>DELETE</b></font> /api/sync-product/{id}", body_style),
            Paragraph("Xóa sản phẩm khỏi ChromaDB khi admin xóa trên web chính.", body_style),
            Paragraph("ID sản phẩm trên đường dẫn", body_style)
        ],
        [
            Paragraph("<font color='#b8860b'><b>POST</b></font> /api/chat", body_style),
            Paragraph("API cốt lõi nhận câu hỏi tự nhiên của khách hàng và trả về tư vấn kèm sản phẩm đề xuất.", body_style),
            Paragraph("<code>message</code>, <code>sessionId</code>, <code>topK</code>", body_style)
        ]
    ]
    api_table = Table(api_list_data, colWidths=[150, 190, 140])
    api_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(api_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>3.2 Ví dụ mã nguồn tích hợp phía Java Spring Boot</b>", h2_style))
    story.append(Paragraph(
        "Nhà phát triển Spring Boot nên sử dụng thư viện <b>WebClient</b> (Reactive Web) thay thế cho RestTemplate cũ để gọi API sang FastAPI không đồng bộ hoặc đồng bộ qua cơ chế <code>.block()</code>.",
        body_style
    ))
    
    java_code = (
        "// Định nghĩa ChatRequestDto gửi đi\n"
        "public class ChatRequestDto {\n"
        "    private String message;\n"
        "    @JsonProperty(\"session_id\")\n"
        "    private String sessionId;\n"
        "    @JsonProperty(\"top_k\")\n"
        "    private Integer topK;\n"
        "    // Getters and Setters...\n"
        "}\n\n"
        "// Lớp tích hợp kết nối chính\n"
        "@Service\n"
        "public class RagIntegrationService {\n"
        "    private final WebClient webClient;\n\n"
        "    public RagIntegrationService(WebClient.Builder builder, \n"
        "                                 @Value(\"${rag.url:http://localhost:8000}\") String ragUrl) {\n"
        "        this.webClient = builder.baseUrl(ragUrl).build();\n"
        "    }\n\n"
        "    public ChatResponseDto chat(String message, String sessionId) {\n"
        "        ChatRequestDto req = new ChatRequestDto(message, sessionId, 5);\n"
        "        return this.webClient.post()\n"
        "                .uri(\"/api/chat\")\n"
        "                .contentType(MediaType.APPLICATION_JSON)\n"
        "                .bodyValue(req)\n"
        "                .retrieve()\n"
        "                .bodyToMono(ChatResponseDto.class)\n"
        "                .block(); // Chặn đồng bộ để nhận kết quả ngay\n"
        "    }\n"
        "}"
    )
    story.append(Paragraph(java_code.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style))

    story.append(Paragraph("<b>3.3 Các điểm chạm nghiệp vụ cần chèn code gọi RAG trong Spring Boot:</b>", h3_style))
    story.append(Paragraph("1. <b>Khi Admin Thêm/Sửa sản phẩm:</b> Sau khi lưu thành công vào MySQL, gọi <code>syncProduct(dto)</code> để cập nhật vector trong ChromaDB tức thì.", bullet_style))
    story.append(Paragraph("2. <b>Khi Admin Xóa sản phẩm:</b> Gọi <code>deleteProduct(productId)</code> để gỡ ngay vector khỏi ChromaDB, tránh việc AI tiếp tục giới thiệu sản phẩm đã xóa.", bullet_style))
    story.append(Paragraph("3. <b>Khi người dùng chat:</b> Nhận câu hỏi, chuyển tiếp sang RAG service, nhận response và render câu trả lời dạng Markdown cùng danh sách <code>recommendedProducts</code> thành dạng <b>Thẻ sản phẩm (Cards)</b> kèm link mua hàng.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # CHƯƠNG 4: KỊCH BẢN TRÌNH BÀY VÀ HƯỚNG DẪN DEMO (DEMO SCRIPT)
    # =========================================================================
    story.append(Paragraph("CHƯƠNG 4: KỊCH BẢN TRÌNH BÀY VÀ HƯỚNG DẪN DEMO", h1_style))
    story.append(Paragraph(
        "Để chuẩn bị báo cáo dự án trước Mentor hoặc Hội đồng phản biện đạt kết quả xuất sắc, AI Intern cần tuân thủ kịch bản trình bày logic 5 bước cụ thể dưới đây:",
        body_style
    ))
    
    story.append(Paragraph("<b>4.1 Checklist chuẩn bị kỹ thuật trước giờ Demo</b>", h2_style))
    story.append(Paragraph("• Đảm bảo Uvicorn server đang chạy ổn định tại cổng 8000.", bullet_style))
    story.append(Paragraph("• Đã chạy file <code>seed_data.py</code> để nạp sẵn 15 sản phẩm mẫu vào ChromaDB.", bullet_style))
    story.append(Paragraph("• Kiểm tra kết nối <code>GET /health</code> hiển thị trạng thái <i>healthy</i>.", bullet_style))
    story.append(Paragraph("• Đảm bảo file cấu hình <code>.env</code> đã thiết lập chính xác (đã điền API Key hoặc bật <code>MOCK_EMBEDDINGS=true</code> nếu chạy offline).", bullet_style))
    
    story.append(Paragraph("<b>4.2 Kịch bản trình bày từng bước (Demo Flow)</b>", h2_style))
    
    demo_steps = [
        ("Bước 1: Chứng minh khả năng phân tích câu hỏi (Query Parser)", "Gọi API debug <code>POST /api/parse-query-debug</code> với câu hỏi: <i>'So sánh Macbook Pro M3 và Asus ROG G14'</i>. Giải thích cho Mentor cách hệ thống nhận diện ý định so sánh (mode=comparison) và tự động trích xuất chính xác mảng tên máy cần so sánh."),
        ("Bước 2: Trình diễn cơ chế lọc cứng và tính điểm (Scoring Engine)", "Gọi API debug <code>POST /api/search-debug</code> với nội dung: <i>'Tôi cần laptop gaming dưới 25 triệu RAM 16GB'</i>. Chỉ ra bộ lọc <code>metadataFilter</code> được tự động áp dụng (RAM >= 16, Price <= 25tr). Chỉ ra mảng <code>scoreDetails</code> giải thích cách tính điểm cộng cấu hình giúp laptop phù hợp nhất nổi lên trên đầu."),
        ("Bước 3: Trình diễn kịch bản tư vấn thực tế", "Gửi câu hỏi tư vấn thực tế tới <code>POST /api/chat</code>. Cho Mentor thấy câu trả lời tư vấn Markdown chi tiết, chuyên nghiệp cùng mảng <code>recommendedProducts</code> chứa các thông tin hình ảnh, giá và url khớp 100% với database gốc."),
        ("Bước 4: Trình diễn tính năng so sánh (Comparison Mode)", "Gửi câu hỏi: <i>'so sánh Asus ROG G14 và Lenovo Legion 5'</i>. Trực quan hóa câu trả lời của AI tự động chia thành các phần so sánh song song: Thiết kế, hiệu năng, màn hình và trọng lượng."),
        ("Bước 5: Chứng minh tính năng đồng bộ thời gian thực", "Thực hiện gửi request đồng bộ sản phẩm mới (ID=16) qua <code>POST /api/sync-product</code>. Sau đó thực hiện chat lại câu hỏi liên quan để thấy AI đã cập nhật và tư vấn được ngay sản phẩm mới này.")
    ]
    
    for num, (step_t, step_d) in enumerate(demo_steps, 1):
        story.append(Paragraph(f"<b>{num}. {step_t}</b>", h3_style))
        story.append(Paragraph(step_d, body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>4.3 Các điểm kỹ thuật nổi bật cần nhấn mạnh khi thuyết trình:</b>", h2_style))
    story.append(Paragraph("• <b>Hybrid RAG Architecture:</b> Giải thích sự khác biệt giữa RAG thông dụng (chỉ tìm kiếm vector dễ sai sót) và Hybrid RAG (kết hợp lọc siêu dữ liệu có cấu trúc ChromaDB trước khi tìm kiếm vector).", bullet_style))
    story.append(Paragraph("• <b>Custom Scoring Engine:</b> Chứng minh hệ thống tích hợp các luật nghiệp vụ laptop (GPU rời cho gaming, phạt out of stock, ưu tiên máy HOT) giúp chất lượng tư vấn vượt xa chatbot thông thường.", bullet_style))
    story.append(Paragraph("• <b>Anti-Hallucination Guardrail:</b> Nhấn mạnh cơ chế hậu xử lý kiểm tra chéo ID và điền đè thông tin gốc đảm bảo AI không bao giờ bịa đặt thông số hay đường dẫn sản phẩm.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # CHƯƠNG 5: BỘ CÂU HỎI PHỎNG VẤN THỬ NGHIỆM VÀ CÂU TRẢ LỜI MẪU (Q&A)
    # =========================================================================
    story.append(Paragraph("CHƯƠNG 5: BỘ CÂU HỎI PHỎNG VẤN THỬ NGHIỆM & ĐÁP ÁN MẪU", h1_style))
    story.append(Paragraph(
        "Để giúp AI Intern tự tin vượt qua các câu hỏi phỏng vấn chuyên môn từ nhà tuyển dụng hoặc Mentors về RAG, Vector Database và kiến trúc hệ thống, dưới đây là bộ 12 câu hỏi chọn lọc kèm đáp án chi tiết:",
        body_style
    ))
    
    qas = [
        ("Câu 1: Kỹ thuật RAG (Retrieval-Augmented Generation) giải quyết vấn đề gì của LLM?",
         "RAG giải quyết 3 hạn chế lớn của LLM: (1) <b>Giảm ảo giác (Hallucination)</b> bằng cách cung cấp thông tin thực tế làm cơ sở dữ liệu đầu vào cho LLM; (2) <b>Cập nhật thông tin mới nhất</b> mà không cần re-train hay fine-tune mô hình; (3) <b>Bảo mật dữ liệu</b> bằng cách giới hạn LLM chỉ trả lời trong phạm vi tài liệu được cung cấp."),
         
        ("Câu 2: Tại sao hệ thống này cần dùng Metadata Pre-filtering thay vì thực hiện Vector Search trước rồi mới lọc?",
         "Nếu thực hiện Vector Search trước, không gian vector trả về Top-K kết quả có thể chứa toàn bộ các laptop đắt tiền (vì chúng có nhiều bài viết mô tả chi tiết, độ tương đồng ngữ nghĩa cao). Khi đó, nếu ta lọc sau (Post-filtering) theo khoảng giá rẻ, có thể toàn bộ Top-K đều bị loại bỏ dẫn đến kết quả trống. <b>Metadata Pre-filtering</b> lọc trước để giới hạn không gian tìm kiếm của ChromaDB chỉ chứa các máy thỏa mãn điều kiện cứng (giá, RAM, hãng), đảm bảo kết quả vector search luôn chính xác và có sản phẩm trả về."),
         
        ("Câu 3: Hãy giải thích cách hoạt động của ChromaDB trong dự án này? Khoảng cách Cosine mang ý nghĩa gì?",
         "ChromaDB lưu trữ các tài liệu mô tả sản phẩm dưới dạng các vector nhúng (Embeddings) được tạo ra từ mô hình Gemini/OpenAI. Khoảng cách (distance) được tính theo công thức Cosine Similarity. Khoảng cách Cosine dao động từ 0 (hoàn toàn giống nhau) đến 2 (hoàn toàn ngược nhau). Hệ thống tự quy đổi similarity_score = 1.0 - (distance / 2.0) để có điểm tương đồng từ 0.0 đến 1.0 làm cơ sở chấm điểm."),
         
        ("Câu 4: Điều gì xảy ra khi có sự không khớp (mismatch) về số chiều (dimension) giữa Embedding Model và ChromaDB?",
         "Nếu thay đổi mô hình Embedding (ví dụ từ Gemini 768 chiều sang OpenAI 1536 chiều) mà vẫn dùng database cũ, ChromaDB sẽ báo lỗi không khớp số chiều khi thực hiện truy vấn hoặc thêm mới sản phẩm. Hệ thống đã triển khai cơ chế kiểm tra chủ động trong file <code>database.py</code>: đo thử số chiều của mô hình hiện tại và so sánh với phần tử có sẵn trong DB. Nếu lệch, hệ thống sẽ log cảnh báo CRITICAL hướng dẫn admin xóa thư mục <code>chroma_db</code> cũ và khởi chạy lại <code>seed_data.py</code> để rebuild dữ liệu."),
         
        ("Câu 5: Công thức Re-ranking của Scoring Engine được thiết kế như thế nào? Tại sao cần nhân điểm vector với 5.0?",
         "Công thức: Score = (Vector Similarity * 5.0) + Bonus - Penalty. Điểm tương đồng vector gốc chỉ dao động từ 0.0 đến 1.0, do đó biên độ dao động rất nhỏ. Bằng cách nhân hệ số 5.0, điểm vector đóng góp tối đa 5.0 điểm vào tổng số điểm. Điều này giúp cân bằng tỷ trọng giữa độ tương đồng ngữ nghĩa và các điểm bonus nghiệp vụ (Brand match +3.0, GPU match +3.0, RAM match +2.0, out of stock phạt nặng -5.0) để đưa ra xếp hạng tối ưu nhất."),
         
        ("Câu 6: Làm thế nào để đảm bảo mô hình LLM luôn trả về JSON hợp lệ mà không bị lỗi text tự do?",
         "Hệ thống sử dụng cơ chế <b>Structured Output</b> của Langchain (hàm <code>with_structured_output</code>) kết hợp với Pydantic model <code>LLMStructuredOutput</code> để định nghĩa cấu trúc JSON mong muốn. LangChain sẽ tự động chèn chỉ dẫn schema vào prompt và ép LLM trả về chính xác định dạng JSON. Nếu LLM trả về text tự do, Langchain parser sẽ catch lỗi và kích hoạt cơ chế <code>_create_fallback_response</code> tự tạo JSON an toàn từ metadata DB."),
         
        ("Câu 7: Tầng chống ảo giác (Anti-hallucination layer) hoạt động như thế nào sau khi LLM phản hồi?",
         "Sau khi LLM trả về kết quả cấu trúc, hàm <code>_validate_and_repair_products</code> sẽ: (1) Kiểm tra xem ID các sản phẩm đề xuất có thực sự nằm trong danh sách candidates đã được lấy từ ChromaDB không. Nếu LLM tự bịa ID lạ, sản phẩm đó bị loại bỏ; (2) Thực hiện đè (override) các thông số cứng như Tên, Giá, URL, Image URL từ metadata gốc của database lên kết quả của LLM. Tránh trường hợp LLM sửa tên hoặc viết sai giá bán."),
         
        ("Câu 8: Tại sao chúng ta sử dụng rule-based Regex cho Query Parser thay vì gọi LLM?",
         "Gọi LLM để phân tích câu hỏi ở bước 1 sẽ mất thêm 1 lượt gọi API (tốn tiền) và làm tăng độ trễ (latency) của hệ thống lên thêm 1-2 giây. Trong khi đó, các câu hỏi lọc laptop thường có cấu trúc khá rõ ràng về giá (triệu, tr, k), RAM (GB), hãng sản xuất. Sử dụng Regex kết hợp rule-based Heuristic giúp trích xuất các tiêu chí cứng cực kỳ nhanh (độ trễ gần như bằng 0) và miễn phí hoàn toàn."),
         
        ("Câu 9: Chế độ Mock Mode (MOCK_EMBEDDINGS=true) hoạt động như thế nào? Dùng khi nào?",
         "Mock Mode được dùng khi test offline không có internet hoặc thiếu API Key. Khi kích hoạt, hệ thống sẽ sử dụng một lớp Mock Embedding trả về vector giả lập có chiều dài cố định (768) và Mock LLM trả về nội dung tư vấn mẫu cấu trúc định sẵn. Giúp kiểm thử tích hợp E2E giữa Spring Boot và FastAPI thông suốt mà không phụ thuộc dịch vụ ngoài."),
         
        ("Câu 10: Hãy nêu 3 hạn chế hiện tại của hệ thống này và hướng giải quyết trong tương lai?",
         "Hạn chế: (1) Chưa lưu lịch sử trò chuyện (Conversation History) để chat nhiều lượt; (2) AI chưa tự tìm kiếm internet nếu máy cần so sánh không có trong DB của cửa hàng; (3) Bộ Query Parser còn đơn giản chưa xử lý được câu hỏi quá phức tạp. Hướng giải quyết: (1) Thêm Session memory; (2) Tích hợp công cụ tìm kiếm web (Tavily/Google Search API) làm fallback; (3) Sử dụng mô hình LLM nhỏ (như Llama-3-8B) chạy local làm Query Parser chuyên dụng."),
         
        ("Câu 11: Tại sao nên tách biệt FastAPI AI Service và Spring Boot thay vì viết chung trong một dự án?",
         "Tách biệt microservice giúp: (1) <b>Tối ưu tài nguyên:</b> Python chuyên trị AI/Data Science với các thư viện mạnh mẽ (LangChain, ChromaDB) còn Java chuyên xử lý nghiệp vụ doanh nghiệp, bảo mật và transaction; (2) <b>Khả năng scale độc lập:</b> AI service tốn nhiều RAM/GPU có thể deploy trên server có GPU riêng, còn Spring Boot chạy trên server CPU thông thường; (3) <b>Giảm thiểu ảnh hưởng lỗi:</b> Nếu AI service gặp sự cố, hệ thống Web chính vẫn hoạt động bình thường, chỉ tạm ẩn chatbot."),
         
        ("Câu 12: Làm sao hệ thống đảm bảo an toàn cho các API Key của Gemini/OpenAI?",
         "Hệ thống sử dụng thư viện <code>pydantic-settings</code> đọc các cấu hình trực tiếp từ biến môi trường hoặc file cấu hình cục bộ <code>.env</code>. File này được thêm vào <code>.gitignore</code> để ngăn chặn việc vô tình push API Key lên các kho chứa mã nguồn công cộng như GitHub.")
    ]

    for qa_num, (q, a) in enumerate(qas, 1):
        qa_block = []
        qa_block.append(Paragraph(f"<b>{qa_num}. {q}</b>", h3_style))
        qa_block.append(Paragraph(f"<i>Trả lời:</i> {a}", body_style))
        # Keep each QA block together so it doesn't break across pages awkwardly
        story.append(KeepTogether(qa_block))
        story.append(Spacer(1, 5))

    # 4. Xây dựng tài liệu PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully created: {filename}")

if __name__ == "__main__":
    create_product_pdf()
