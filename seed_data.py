"""
seed_data.py - Script thêm dữ liệu mẫu laptop vào ChromaDB

Chạy script này một lần sau khi cài đặt để có dữ liệu demo.
Sử dụng: python seed_data.py
"""

import json
import logging
import sys
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# URL của RAG microservice (chạy local)
BASE_URL = "http://localhost:8000"

# =============================================================================
# DỮ LIỆU MẪU - 15 laptop đại diện cho nhiều phân khúc
# =============================================================================

SAMPLE_LAPTOPS = [
    # ---- GAMING ----
    {
        "id": 1,
        "name": "Asus ROG Zephyrus G14 (2024) GA403UV",
        "brand": "Asus",
        "price": 34990000,
        "ram": 16,
        "cpu": "AMD Ryzen 9 8945HS",
        "gpu": "NVIDIA GeForce RTX 4060 8GB",
        "storage": "1TB NVMe SSD",
        "screen_size": 14.0,
        "screen_resolution": "2560x1600 OLED 120Hz",
        "battery_life": "10 giờ",
        "weight": 1.65,
        "operating_system": "Windows 11 Home",
        "url": "/product/1",
        "image_url": "/images/asus-rog-g14.jpg",
        "description": "Laptop gaming cao cấp mỏng nhẹ với màn hình OLED tuyệt đẹp, hiệu năng gaming đỉnh cao.",
        "is_hot": True,
        "use_case_tags": "gaming, design, portable",
    },
    {
        "id": 2,
        "name": "MSI Katana 15 B13VFK",
        "brand": "MSI",
        "price": 24990000,
        "ram": 16,
        "cpu": "Intel Core i7-13620H",
        "gpu": "NVIDIA GeForce RTX 4060 8GB",
        "storage": "512GB NVMe SSD",
        "screen_size": 15.6,
        "screen_resolution": "1920x1080 IPS 144Hz",
        "battery_life": "6 giờ",
        "weight": 2.2,
        "operating_system": "Windows 11 Home",
        "url": "/product/2",
        "image_url": "/images/msi-katana-15.jpg",
        "description": "Laptop gaming tầm trung hiệu năng RTX 4060, phù hợp chơi game AAA.",
        "is_hot": True,
        "use_case_tags": "gaming",
    },
    {
        "id": 3,
        "name": "Lenovo LOQ 15APH9",
        "brand": "Lenovo",
        "price": 21990000,
        "ram": 16,
        "cpu": "AMD Ryzen 7 7745HX",
        "gpu": "NVIDIA GeForce RTX 4060 8GB",
        "storage": "512GB NVMe SSD",
        "screen_size": 15.6,
        "screen_resolution": "1920x1080 IPS 144Hz",
        "battery_life": "5 giờ",
        "weight": 2.4,
        "operating_system": "Windows 11 Home",
        "url": "/product/3",
        "image_url": "/images/lenovo-loq-15.jpg",
        "description": "Laptop gaming giá tốt nhất phân khúc tầm trung với RTX 4060.",
        "is_hot": False,
        "use_case_tags": "gaming",
    },
    {
        "id": 4,
        "name": "Dell G15 5530 Gaming",
        "brand": "Dell",
        "price": 19990000,
        "ram": 16,
        "cpu": "Intel Core i5-13450HX",
        "gpu": "NVIDIA GeForce RTX 3050 6GB",
        "storage": "512GB NVMe SSD",
        "screen_size": 15.6,
        "screen_resolution": "1920x1080 IPS 120Hz",
        "battery_life": "6 giờ",
        "weight": 2.52,
        "operating_system": "Windows 11 Home",
        "url": "/product/4",
        "image_url": "/images/dell-g15.jpg",
        "description": "Laptop gaming entry-level phù hợp cho game thủ mới bắt đầu.",
        "is_hot": False,
        "use_case_tags": "gaming",
    },
    # ---- THIẾT KẾ / ĐỒ HỌA ----
    {
        "id": 5,
        "name": "Apple MacBook Pro 14 M3 Pro",
        "brand": "Apple",
        "price": 52990000,
        "ram": 18,
        "cpu": "Apple M3 Pro 11-core",
        "gpu": "Apple M3 Pro 14-core GPU",
        "storage": "512GB SSD",
        "screen_size": 14.2,
        "screen_resolution": "3024x1964 Liquid Retina XDR 120Hz",
        "battery_life": "18 giờ",
        "weight": 1.61,
        "operating_system": "macOS Sonoma",
        "url": "/product/5",
        "image_url": "/images/macbook-pro-14-m3.jpg",
        "description": "Laptop đồ họa chuyên nghiệp cao cấp nhất với chip M3 Pro, màu sắc chuẩn xác.",
        "is_hot": True,
        "use_case_tags": "design, video editing, professional",
    },
    {
        "id": 6,
        "name": "Asus ProArt Studiobook 16 OLED H7604",
        "brand": "Asus",
        "price": 44990000,
        "ram": 32,
        "cpu": "Intel Core i9-13980HX",
        "gpu": "NVIDIA GeForce RTX 4070 8GB",
        "storage": "1TB NVMe SSD",
        "screen_size": 16.0,
        "screen_resolution": "3200x2000 OLED 120Hz DCI-P3 100%",
        "battery_life": "6 giờ",
        "weight": 2.4,
        "operating_system": "Windows 11 Pro",
        "url": "/product/6",
        "image_url": "/images/asus-proart-16.jpg",
        "description": "Workstation di động cho designer và creator chuyên nghiệp, màn hình OLED chuẩn màu.",
        "is_hot": False,
        "use_case_tags": "design, video editing, 3D rendering, professional",
    },
    {
        "id": 7,
        "name": "HP ZBook Fury 16 G10",
        "brand": "HP",
        "price": 38990000,
        "ram": 32,
        "cpu": "Intel Core i7-13850HX",
        "gpu": "NVIDIA RTX 4000 Ada 8GB",
        "storage": "1TB NVMe SSD",
        "screen_size": 16.0,
        "screen_resolution": "1920x1200 IPS 400nits",
        "battery_life": "8 giờ",
        "weight": 2.76,
        "operating_system": "Windows 11 Pro",
        "url": "/product/7",
        "image_url": "/images/hp-zbook-fury-16.jpg",
        "description": "Mobile workstation dành cho kỹ sư CAD/CAM, render 3D chuyên nghiệp.",
        "is_hot": False,
        "use_case_tags": "design, CAD, engineering, professional",
    },
    # ---- VĂN PHÒNG / DOANH NHÂN ----
    {
        "id": 8,
        "name": "Dell XPS 13 9340",
        "brand": "Dell",
        "price": 29990000,
        "ram": 16,
        "cpu": "Intel Core Ultra 7 165H",
        "gpu": "Intel Arc Graphics",
        "storage": "512GB NVMe SSD",
        "screen_size": 13.4,
        "screen_resolution": "1920x1200 IPS",
        "battery_life": "12 giờ",
        "weight": 1.17,
        "operating_system": "Windows 11 Home",
        "url": "/product/8",
        "image_url": "/images/dell-xps-13.jpg",
        "description": "Ultrabook cao cấp siêu mỏng nhẹ dành cho doanh nhân, pin siêu trâu.",
        "is_hot": True,
        "use_case_tags": "office, business, portable",
    },
    {
        "id": 9,
        "name": "Lenovo ThinkPad X1 Carbon Gen 11",
        "brand": "Lenovo",
        "price": 35990000,
        "ram": 16,
        "cpu": "Intel Core i7-1365U",
        "gpu": "Intel Iris Xe Graphics",
        "storage": "512GB NVMe SSD",
        "screen_size": 14.0,
        "screen_resolution": "1920x1200 IPS 400nits",
        "battery_life": "15 giờ",
        "weight": 1.12,
        "operating_system": "Windows 11 Pro",
        "url": "/product/9",
        "image_url": "/images/thinkpad-x1-carbon.jpg",
        "description": "Laptop doanh nhân huyền thoại - bàn phím tốt nhất, pin cực trâu, bảo mật cao.",
        "is_hot": False,
        "use_case_tags": "office, business, security",
    },
    {
        "id": 10,
        "name": "HP EliteBook 840 G10",
        "brand": "HP",
        "price": 27990000,
        "ram": 16,
        "cpu": "Intel Core i5-1335U",
        "gpu": "Intel Iris Xe Graphics",
        "storage": "512GB NVMe SSD",
        "screen_size": 14.0,
        "screen_resolution": "1920x1080 IPS Sure View",
        "battery_life": "10 giờ",
        "weight": 1.34,
        "operating_system": "Windows 11 Pro",
        "url": "/product/10",
        "image_url": "/images/hp-elitebook-840.jpg",
        "description": "Laptop doanh nghiệp bảo mật với màn hình chống nhìn trộm Sure View.",
        "is_hot": False,
        "use_case_tags": "office, business, security",
    },
    # ---- SINH VIÊN / PHỔ THÔNG ----
    {
        "id": 11,
        "name": "Acer Aspire 5 A515-58M",
        "brand": "Acer",
        "price": 12990000,
        "ram": 8,
        "cpu": "Intel Core i5-1335U",
        "gpu": "Intel Iris Xe Graphics",
        "storage": "512GB NVMe SSD",
        "screen_size": 15.6,
        "screen_resolution": "1920x1080 IPS",
        "battery_life": "8 giờ",
        "weight": 1.8,
        "operating_system": "Windows 11 Home",
        "url": "/product/11",
        "image_url": "/images/acer-aspire-5.jpg",
        "description": "Laptop sinh viên giá rẻ hiệu năng tốt, phù hợp học tập và làm việc cơ bản.",
        "is_hot": True,
        "use_case_tags": "student, office, basic",
    },
    {
        "id": 12,
        "name": "Lenovo IdeaPad Slim 5 16IAH8",
        "brand": "Lenovo",
        "price": 15990000,
        "ram": 16,
        "cpu": "Intel Core i5-12450H",
        "gpu": "Intel Arc A370M 4GB",
        "storage": "512GB NVMe SSD",
        "screen_size": 16.0,
        "screen_resolution": "1920x1200 IPS",
        "battery_life": "7 giờ",
        "weight": 1.83,
        "operating_system": "Windows 11 Home",
        "url": "/product/12",
        "image_url": "/images/lenovo-ideapad-slim5.jpg",
        "description": "Laptop học sinh/sinh viên màn hình lớn 16 inch, RAM 16GB giá hợp lý.",
        "is_hot": False,
        "use_case_tags": "student, office, multimedia",
    },
    {
        "id": 13,
        "name": "HP Pavilion 15 eg3099TU",
        "brand": "HP",
        "price": 13490000,
        "ram": 8,
        "cpu": "Intel Core i5-1335U",
        "gpu": "Intel Iris Xe Graphics",
        "storage": "256GB NVMe SSD",
        "screen_size": 15.6,
        "screen_resolution": "1920x1080 IPS",
        "battery_life": "8 giờ",
        "weight": 1.75,
        "operating_system": "Windows 11 Home",
        "url": "/product/13",
        "image_url": "/images/hp-pavilion-15.jpg",
        "description": "Laptop phổ thông dành cho sinh viên và gia đình, giá phải chăng.",
        "is_hot": False,
        "use_case_tags": "student, office, basic",
    },
    # ---- LẬP TRÌNH ----
    {
        "id": 14,
        "name": "Framework Laptop 13 AMD",
        "brand": "Framework",
        "price": 22990000,
        "ram": 32,
        "cpu": "AMD Ryzen 7 7840U",
        "gpu": "AMD Radeon 780M",
        "storage": "1TB NVMe SSD",
        "screen_size": 13.5,
        "screen_resolution": "2256x1504 IPS",
        "battery_life": "10 giờ",
        "weight": 1.37,
        "operating_system": "Windows 11 Home / Linux",
        "url": "/product/14",
        "image_url": "/images/framework-13-amd.jpg",
        "description": "Laptop modular dành cho developer, Linux-friendly, RAM 32GB, có thể sửa chữa dễ dàng.",
        "is_hot": False,
        "use_case_tags": "programming, linux, portable",
    },
    {
        "id": 15,
        "name": "Asus Zenbook Pro 14 OLED UX6404",
        "brand": "Asus",
        "price": 39990000,
        "ram": 32,
        "cpu": "Intel Core i9-13900H",
        "gpu": "NVIDIA GeForce RTX 4070 8GB",
        "storage": "1TB NVMe SSD",
        "screen_size": 14.5,
        "screen_resolution": "2880x1800 OLED 120Hz",
        "battery_life": "7 giờ",
        "weight": 1.65,
        "operating_system": "Windows 11 Pro",
        "url": "/product/15",
        "image_url": "/images/asus-zenbook-pro-14.jpg",
        "description": "Laptop cao cấp đa năng cho creator và developer chuyên nghiệp.",
        "is_hot": True,
        "use_case_tags": "design, programming, gaming, professional",
    },
]


def seed_data(base_url: str = BASE_URL):
    """
    Thêm tất cả dữ liệu mẫu vào ChromaDB thông qua API.

    Args:
        base_url: URL của RAG microservice
    """
    logger.info(f"Bắt đầu seed {len(SAMPLE_LAPTOPS)} sản phẩm vào {base_url}...")

    success_count = 0
    error_count = 0

    with httpx.Client(timeout=30.0) as client:
        # Kiểm tra server đang chạy
        try:
            response = client.get(f"{base_url}/health")
            response.raise_for_status()
            logger.info(f"✅ Server đang hoạt động: {response.json()}")
        except Exception as e:
            logger.error(
                f"❌ Không thể kết nối đến server tại {base_url}. "
                f"Hãy chắc chắn server đang chạy!\nLỗi: {e}"
            )
            sys.exit(1)

        # Thêm từng sản phẩm
        for laptop in SAMPLE_LAPTOPS:
            try:
                response = client.post(
                    f"{base_url}/api/sync-product",
                    json=laptop,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    logger.info(
                        f"✅ [{success_count + 1}/{len(SAMPLE_LAPTOPS)}] "
                        f"Đã thêm: {laptop['name']}"
                    )
                    success_count += 1
                else:
                    logger.error(f"❌ Lỗi khi thêm: {laptop['name']}: {result}")
                    error_count += 1

                # Delay nhỏ để tránh rate limit API embedding
                time.sleep(0.5)

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"❌ HTTP Error khi thêm {laptop['name']}: "
                    f"{e.response.status_code} - {e.response.text}"
                )
                error_count += 1
            except Exception as e:
                logger.error(f"❌ Lỗi không mong đợi khi thêm {laptop['name']}: {e}")
                error_count += 1

    # Kiểm tra kết quả
    logger.info("\n" + "=" * 50)
    logger.info(f"📊 KẾT QUẢ SEED DATA:")
    logger.info(f"   ✅ Thành công: {success_count}/{len(SAMPLE_LAPTOPS)}")
    logger.info(f"   ❌ Thất bại:   {error_count}/{len(SAMPLE_LAPTOPS)}")

    if success_count > 0:
        # Kiểm tra stats
        with httpx.Client() as client:
            stats = client.get(f"{base_url}/api/stats").json()
            logger.info(
                f"   📦 Tổng sản phẩm trong DB: "
                f"{stats.get('total_products_in_vector_db', 'N/A')}"
            )

    logger.info("=" * 50)


if __name__ == "__main__":
    seed_data()
