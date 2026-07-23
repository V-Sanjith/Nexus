from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event, text
from app.config import settings
import structlog

logger = structlog.get_logger()

# Configure engine arguments dynamically to prevent SQLite crash on pool settings
if settings.DATABASE_PROVIDER == "sqlite":
    engine = create_async_engine(
        str(settings.DATABASE_URL),
        echo=settings.DEBUG,
        # SQLite: disable connection pool reuse issues (use NullPool or StaticPool for async)
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # wait up to 30s for a lock to clear before raising
        }
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_wal_mode(dbapi_connection, connection_record):
        """Enable WAL mode so readers don't block writers and vice-versa."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30s timeout in ms
        cursor.close()
else:
    engine = create_async_engine(
        str(settings.DATABASE_URL),
        echo=settings.DEBUG,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True
    )

# Async session maker factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    """Dependency injection helper to yield active async sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

get_db = get_db_session

async def init_db():
    """Initializes the database schema automatically on startup."""
    from app.models import Base
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")

# Helper to compute dynamic performance metrics for laptops based on CPU & GPU
def get_laptop_performance_metrics(cpu: str, gpu: str, ram: int):
    # CPU Multi-core & Single-core scoring
    if "i9" in cpu.lower() or "ryzen 9" in cpu.lower() or "m3 max" in cpu.lower():
        cpu_multi = 22000
        cpu_single = 1900
        ai_tops = 45
    elif "i7" in cpu.lower() or "ryzen 7" in cpu.lower() or "m3 pro" in cpu.lower() or "ultra 7" in cpu.lower():
        cpu_multi = 15500
        cpu_single = 1750
        ai_tops = 34
    elif "i5" in cpu.lower() or "ryzen 5" in cpu.lower() or "m3" in cpu.lower():
        cpu_multi = 11000
        cpu_single = 1600
        ai_tops = 18
    else:
        cpu_multi = 7500
        cpu_single = 1300
        ai_tops = 10

    # Scale CPU multi-core for high-performance HX series
    if "hx" in cpu.lower():
        cpu_multi = int(cpu_multi * 1.2)

    # Scale CPU multi-core with RAM size
    if ram <= 8:
        cpu_multi = int(cpu_multi * 0.85)
    elif ram >= 32:
        cpu_multi = int(cpu_multi * 1.1)

    # GPU 3DMark & Gaming FPS scoring
    if "4090" in gpu:
        gpu_name = "NVIDIA GeForce RTX 4090"
        gpu_3dmark = 21000
        fps_1080p = 180
        fps_1440p = 145
        rt_score = 95
    elif "4080" in gpu:
        gpu_name = "NVIDIA GeForce RTX 4080"
        gpu_3dmark = 16500
        fps_1080p = 145
        fps_1440p = 115
        rt_score = 82
    elif "4070" in gpu:
        gpu_name = "NVIDIA GeForce RTX 4070"
        gpu_3dmark = 12200
        fps_1080p = 115
        fps_1440p = 85
        rt_score = 72
    elif "4060" in gpu:
        gpu_name = "NVIDIA GeForce RTX 4060"
        gpu_3dmark = 10200
        fps_1080p = 95
        fps_1440p = 70
        rt_score = 62
    elif "4050" in gpu:
        gpu_name = "NVIDIA GeForce RTX 4050"
        gpu_3dmark = 8400
        fps_1080p = 80
        fps_1440p = 55
        rt_score = 50
    elif "m3 max" in gpu.lower():
        gpu_name = "Apple M3 Max 30-Core GPU"
        gpu_3dmark = 11500
        fps_1080p = 90
        fps_1440p = 65
        rt_score = 45
    elif "m3 pro" in gpu.lower():
        gpu_name = "Apple M3 Pro 18-Core GPU"
        gpu_3dmark = 7800
        fps_1080p = 65
        fps_1440p = 45
        rt_score = 32
    elif "m3" in gpu.lower():
        gpu_name = "Apple M3 10-Core GPU"
        gpu_3dmark = 3400
        fps_1080p = 32
        fps_1440p = 18
        rt_score = 12
    elif "arc" in gpu.lower():
        gpu_name = "Intel Arc Graphics"
        gpu_3dmark = 3800
        fps_1080p = 35
        fps_1440p = 20
        rt_score = 15
    elif "radeon" in gpu.lower():
        gpu_name = "AMD Radeon 780M"
        gpu_3dmark = 3200
        fps_1080p = 30
        fps_1440p = 15
        rt_score = 10
    else:
        gpu_name = "Intel Iris Xe Graphics" if "intel" in gpu.lower() else gpu
        gpu_3dmark = 1800
        fps_1080p = 20
        fps_1440p = 8
        rt_score = 5

    return cpu_multi, cpu_single, ai_tops, gpu_name, gpu_3dmark, fps_1080p, fps_1440p, rt_score

async def seed_database():
    """Seeds the database with a high-fidelity catalog of realistic laptops, smartphones, and monitors.
    Idempotent: skips seeding if products already exist in the database.
    """
    from sqlalchemy import select, delete, func
    from app.models.product import Product
    
    async with async_session_maker() as session:
        # Check if catalog is already seeded — skip if so to avoid downtime on restarts
        result = await session.execute(select(func.count()).select_from(Product))
        existing_count = result.scalar()
        if existing_count and existing_count > 0:
            logger.info("Catalog already seeded, skipping re-seed.", existing_products=existing_count)
            return
        
        logger.info("No products found. Initializing catalog seed...")

        products = []

        # =====================================================================
        # 1. LAPTOPS DEFINITIONS (13 Realistic base models with specific configs)
        # =====================================================================
        base_laptops = [
    {
        "name": "Lenovo V15 Ryzen 5",
        "brand": "Lenovo",
        "laptop_type": "student",
        "manufacturer": "Lenovo",
        "model_number": "82YU00W3IN",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 7.5,
        "panel_type": "TN",
        "brightness_nits": 250,
        "srgb_coverage": 60.0,
        "adobe_rgb_coverage": 40.0,
        "dci_p3_coverage": 40.0,
        "color_accuracy_delta_e": 3.3,
        "battery_capacity_wh": 38.0,
        "weight_kg": 1.65,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "Ryzen 5 7520U quad-core speed under \u20b940k",
            "Full numeric keypad"
        ],
        "known_cons": [
            "TN panel"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 377.3,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7520U",
                "gpu": "amd radeon 610m",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Acer Aspire 5 Gaming RTX 2050",
        "brand": "Acer",
        "laptop_type": "gaming",
        "manufacturer": "Acer",
        "model_number": "A515-57G",
        "operating_system": "Windows 11 Home",
        "gpu_type": "dedicated",
        "cooling_score": 8.0,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 65.0,
        "adobe_rgb_coverage": 45.0,
        "dci_p3_coverage": 45.0,
        "color_accuracy_delta_e": 2.8,
        "battery_capacity_wh": 50.0,
        "weight_kg": 1.8,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.2,
        "known_pros": [
            "NVIDIA RTX 2050 dedicated graphics under \u20b945,000",
            "12th Gen Core i5 12-core"
        ],
        "known_cons": [
            "50Wh battery"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 458.9,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "Intel Core i5-12450H",
                "gpu": "nvidia rtx 2050",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "HP Victus 15 Ryzen 5",
        "brand": "HP",
        "laptop_type": "gaming",
        "manufacturer": "HP",
        "model_number": "15-fb0150AX",
        "operating_system": "Windows 11 Home",
        "gpu_type": "dedicated",
        "cooling_score": 8.2,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 65.0,
        "adobe_rgb_coverage": 45.0,
        "dci_p3_coverage": 45.0,
        "color_accuracy_delta_e": 2.7,
        "battery_capacity_wh": 52.5,
        "weight_kg": 2.29,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "AMD Ryzen 5 5600H 6-core",
            "144Hz high refresh display",
            "Dual-fan cooling system"
        ],
        "known_cons": [
            "Slight screen wobble"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 509.9,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "AMD Ryzen 5 5600H",
                "gpu": "nvidia rtx 2050",
                "refresh": 144,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Apple MacBook Air M3 13",
        "brand": "Apple",
        "laptop_type": "creator",
        "manufacturer": "Apple",
        "model_number": "MRXV3HN/A",
        "operating_system": "macOS",
        "gpu_type": "integrated",
        "cooling_score": 9.2,
        "panel_type": "Liquid Retina",
        "brightness_nits": 500,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 98.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.6,
        "battery_capacity_wh": 52.6,
        "weight_kg": 1.24,
        "upgradeability": {
            "ram": False,
            "ssd": False
        },
        "repairability_score": 6.0,
        "known_pros": [
            "Apple M3 8-core CPU 10-core GPU speed",
            "18-hour real world battery life",
            "Silent fanless cooling"
        ],
        "known_cons": [
            "Base 8GB RAM"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
        "base_price": 1172.8,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "cpu": "Apple M3",
                "gpu": "apple m3 10-core gpu",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS Vivobook Pro 15 OLED",
        "brand": "ASUS",
        "laptop_type": "creator",
        "manufacturer": "ASUS",
        "model_number": "K6502VU",
        "operating_system": "Windows 11 Home",
        "gpu_type": "dedicated",
        "cooling_score": 8.8,
        "panel_type": "OLED",
        "brightness_nits": 600,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 99.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.7,
        "battery_capacity_wh": 70.0,
        "weight_kg": 1.8,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.2,
        "known_pros": [
            "NVIDIA RTX 4050 6GB graphics",
            "2.8K 120Hz OLED screen",
            "Dual-fan IceCool Plus cooling"
        ],
        "known_cons": [
            "Battery life under heavy GPU load"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 968.8,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-13500H",
                "gpu": "nvidia rtx 4050",
                "refresh": 120,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Lenovo ThinkPad E14 Gen 5",
        "brand": "Lenovo",
        "laptop_type": "business",
        "manufacturer": "Lenovo",
        "model_number": "21JK000DIN",
        "operating_system": "Windows 11 Pro",
        "gpu_type": "integrated",
        "cooling_score": 8.5,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 75.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 1.8,
        "battery_capacity_wh": 57.0,
        "weight_kg": 1.41,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.8,
        "known_pros": [
            "Iconic TrackPoint red pointer & legendary keyboard",
            "Dual RAM SODIMM slots",
            "MIL-STD-810H pass"
        ],
        "known_cons": [
            "Power brick is bulky"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 662.8,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7530U",
                "gpu": "amd radeon 780m",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "HP ProBook 450 G10",
        "brand": "HP",
        "laptop_type": "business",
        "manufacturer": "HP",
        "model_number": "450-G10",
        "operating_system": "Windows 11 Pro",
        "gpu_type": "integrated",
        "cooling_score": 8.3,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 65.0,
        "adobe_rgb_coverage": 45.0,
        "dci_p3_coverage": 45.0,
        "color_accuracy_delta_e": 2.8,
        "battery_capacity_wh": 51.0,
        "weight_kg": 1.79,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.5,
        "known_pros": [
            "15.6-inch full numeric keypad",
            "HP Wolf Security endpoint protection",
            "Dual SODIMM RAM slots"
        ],
        "known_cons": [
            "Screen is 250 nits"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 713.8,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-1335U",
                "gpu": "intel iris xe",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Acer Swift Go 14 OLED",
        "brand": "Acer",
        "laptop_type": "creator",
        "manufacturer": "Acer",
        "model_number": "SFG14-71",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 8.2,
        "panel_type": "OLED",
        "brightness_nits": 500,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 98.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.8,
        "battery_capacity_wh": 65.0,
        "weight_kg": 1.25,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "2.8K 90Hz OLED display",
            "Intel Core i5-13500H performance",
            "Ultra-portable 1.25kg chassis"
        ],
        "known_cons": [
            "Soldered LPDDR5 RAM"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 611.8,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-13500H",
                "gpu": "intel iris xe",
                "refresh": 90,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS Zenbook 14 OLED",
        "brand": "ASUS",
        "laptop_type": "portability",
        "manufacturer": "ASUS",
        "model_number": "UM3402YA",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 8.4,
        "panel_type": "OLED",
        "brightness_nits": 600,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 99.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.7,
        "battery_capacity_wh": 75.0,
        "weight_kg": 1.39,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.8,
        "known_pros": [
            "75Wh battery runs 14 hours",
            "2.8K 90Hz OLED screen",
            "ErgoSense touchpad NumberPad"
        ],
        "known_cons": [
            "Glossy screen reflection"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 764.8,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 7 7730U",
                "gpu": "amd radeon 780m",
                "refresh": 90,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Lenovo Yoga Slim 6",
        "brand": "Lenovo",
        "laptop_type": "creator",
        "manufacturer": "Lenovo",
        "model_number": "83E0000DIN",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 8.3,
        "panel_type": "OLED",
        "brightness_nits": 400,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 95.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.9,
        "battery_capacity_wh": 65.0,
        "weight_kg": 1.35,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "Intel Core i5-12450H 12-thread CPU",
            "Full aluminum build quality",
            "MIL-STD-810H pass"
        ],
        "known_cons": [
            "Single M.2 SSD slot"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 662.8,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-12450H",
                "gpu": "intel iris xe",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "HP Envy x360 14",
        "brand": "HP",
        "laptop_type": "portability",
        "manufacturer": "HP",
        "model_number": "14-es0013TU",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 8.1,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 75.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 1.8,
        "battery_capacity_wh": 43.0,
        "weight_kg": 1.52,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "360-degree 2-in-1 convertible hinge",
            "Active Stylus pen support",
            "5MP IR webcam"
        ],
        "known_cons": [
            "43Wh battery"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 795.4,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-1335U",
                "gpu": "intel iris xe",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Lenovo V14 i3-1215U",
        "brand": "Lenovo",
        "laptop_type": "student",
        "manufacturer": "Lenovo",
        "model_number": "82T0007DIN",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 7.2,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 60.0,
        "adobe_rgb_coverage": 42.0,
        "dci_p3_coverage": 42.0,
        "color_accuracy_delta_e": 3.2,
        "battery_capacity_wh": 38.0,
        "weight_kg": 1.43,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "Compact 14-inch chassis",
            "12th Gen Intel i3 6-core",
            "TPM 2.0 security"
        ],
        "known_cons": [
            "Basic 38Wh battery"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 336.6,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "Intel Core i3-1215U",
                "gpu": "intel uhd",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS Vivobook 15 i3",
        "brand": "ASUS",
        "laptop_type": "student",
        "manufacturer": "ASUS",
        "model_number": "X1500EA",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 7.0,
        "panel_type": "TN",
        "brightness_nits": 220,
        "srgb_coverage": 55.0,
        "adobe_rgb_coverage": 38.0,
        "dci_p3_coverage": 38.0,
        "color_accuracy_delta_e": 3.6,
        "battery_capacity_wh": 37.0,
        "weight_kg": 1.8,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "NanoEdge display bezels",
            "Fingerprint sensor login",
            "Dual storage design"
        ],
        "known_cons": [
            "TN screen panel"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 326.4,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "Intel Core i3-1115G4",
                "gpu": "intel uhd",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Acer Aspire 3 Ryzen 3",
        "brand": "Acer",
        "laptop_type": "student",
        "manufacturer": "Acer",
        "model_number": "A315-24P",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 7.1,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 60.0,
        "adobe_rgb_coverage": 40.0,
        "dci_p3_coverage": 40.0,
        "color_accuracy_delta_e": 3.4,
        "battery_capacity_wh": 40.0,
        "weight_kg": 1.78,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "Ryzen 3 7320U power efficiency",
            "FHD IPS screen",
            "Comfortable hinge lift"
        ],
        "known_cons": [
            "LPDDR5 memory soldered"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 285.6,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "AMD Ryzen 3 7320U",
                "gpu": "amd radeon 610m",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Lenovo IdeaPad Slim 3 i5",
        "brand": "Lenovo",
        "laptop_type": "business",
        "manufacturer": "Lenovo",
        "model_number": "83ER000DIN",
        "operating_system": "Windows 11 Home",
        "gpu_type": "integrated",
        "cooling_score": 8.0,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 72.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 2.0,
        "battery_capacity_wh": 47.0,
        "weight_kg": 1.62,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "Intel Core i5-13420H 8-core speed",
            "User facing Dolby Audio speakers",
            "Smart Power thermal management"
        ],
        "known_cons": [
            "16GB RAM is soldered"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 530.5,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-13420H",
                "gpu": "intel uhd",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Dell Latitude 3540 i5",
        "brand": "Dell",
        "laptop_type": "business",
        "manufacturer": "Dell",
        "model_number": "L3540-i5",
        "operating_system": "Windows 11 Pro",
        "gpu_type": "integrated",
        "cooling_score": 8.5,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 65.0,
        "adobe_rgb_coverage": 45.0,
        "dci_p3_coverage": 45.0,
        "color_accuracy_delta_e": 2.8,
        "battery_capacity_wh": 54.0,
        "weight_kg": 1.81,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.8,
        "known_pros": [
            "Dell Optimizer AI performance tuning",
            "Commercial Grade durability build",
            "Dual SODIMM RAM upgradeable to 64GB"
        ],
        "known_cons": [
            "Base screen is 250 nits"
        ],
        "known_issues": [],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 642.6,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-1335U",
                "gpu": "intel iris xe",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Lenovo V15 G4 Ryzen 3",
        "brand": "Lenovo",
        "laptop_type": "student",
        "manufacturer": "Lenovo",
        "model_number": "82YU00W2IN",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 7.0,
        "panel_type": "TN",
        "brightness_nits": 250,
        "srgb_coverage": 55.0,
        "adobe_rgb_coverage": 38.0,
        "dci_p3_coverage": 38.0,
        "color_accuracy_delta_e": 3.8,
        "battery_capacity_wh": 38.0,
        "weight_kg": 1.65,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 8.2,
        "known_pros": [
            "Entry-level price point under \u20b930,000",
            "Ryzen 3 7320U quad-core power efficiency",
            "Physical webcam privacy shutter"
        ],
        "known_cons": [
            "TN panel viewing angles are narrow",
            "38Wh battery capacity"
        ],
        "known_issues": [
            "Function keys default to hotkey mode (changeable in BIOS)"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 295.8,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "AMD Ryzen 3 7320U",
                "gpu": "amd radeon 610m",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS Vivobook Go 15",
        "brand": "ASUS",
        "laptop_type": "student",
        "manufacturer": "ASUS",
        "model_number": "E1504FA",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 7.4,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 65.0,
        "adobe_rgb_coverage": 45.0,
        "dci_p3_coverage": 45.0,
        "color_accuracy_delta_e": 3.1,
        "battery_capacity_wh": 42.0,
        "weight_kg": 1.63,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "180-degree lay-flat hinge",
            "Fast 60% charging in 49 minutes",
            "Full-size ErgoSense keyboard"
        ],
        "known_cons": [
            "Single-channel LPDDR5 memory",
            "Plastic lid material"
        ],
        "known_issues": [
            "MyASUS app popup notifications upon boot"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 357.0,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7520U",
                "gpu": "amd radeon 610m",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "HP 15s Core i3",
        "brand": "HP",
        "laptop_type": "student",
        "manufacturer": "HP",
        "model_number": "15s-fy5007TU",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 7.2,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 62.0,
        "adobe_rgb_coverage": 44.0,
        "dci_p3_coverage": 44.0,
        "color_accuracy_delta_e": 3.0,
        "battery_capacity_wh": 41.0,
        "weight_kg": 1.69,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "Intel 12th Gen Core i3 6-core processor",
            "Dual RAM slots upgradeable to 32GB",
            "HP Fast Charge technology"
        ],
        "known_cons": [
            "No keyboard backlighting",
            "Basic webcam quality"
        ],
        "known_issues": [
            "Trackpad click clicker feels hollow"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 387.6,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "Intel Core i3-1215U",
                "gpu": "intel uhd",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "HP Pavilion 14 Ryzen 5",
        "brand": "HP",
        "laptop_type": "business",
        "manufacturer": "HP",
        "model_number": "14-ec1019AU",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 8.0,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 72.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 2.0,
        "battery_capacity_wh": 43.0,
        "weight_kg": 1.41,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "Aluminum keyboard deck build",
            "100% sRGB color accurate 14-inch screen",
            "Bang & Olufsen tuned speakers"
        ],
        "known_cons": [
            "43Wh battery limits heavy runtime",
            "No Thunderbolt support"
        ],
        "known_issues": [
            "Silver keyboard keys lack contrast with backlight on"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 540.7,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7530U",
                "gpu": "amd radeon 780m",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Lenovo ThinkBook 14 Gen 6",
        "brand": "Lenovo",
        "laptop_type": "business",
        "manufacturer": "Lenovo",
        "model_number": "21KG005AIN",
        "operating_system": "Windows 11 Pro",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 8.4,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 75.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 1.8,
        "battery_capacity_wh": 60.0,
        "weight_kg": 1.38,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.5,
        "known_pros": [
            "Dual RAM SODIMM slots & dual M.2 SSD slots",
            "MIL-STD-810H military durability test pass",
            "FHD infrared camera with Windows Hello"
        ],
        "known_cons": [
            "Power button fingerprint reader can miss dirty fingers"
        ],
        "known_issues": [
            "Lenovo Vantage battery threshold reset after BIOS update"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 703.9,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-1335U",
                "gpu": "intel iris xe",
                "refresh": 60,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Apple MacBook Air 13 M3",
        "brand": "Apple",
        "laptop_type": "ultrabook",
        "manufacturer": "Apple",
        "model_number": "MRXV3",
        "operating_system": "macOS Sonoma",
        "linux_supported": False,
        "gpu_type": "integrated",
        "cooling_score": 8.0,
        "panel_type": "IPS",
        "brightness_nits": 500,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 85.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 1.1,
        "battery_capacity_wh": 52.6,
        "weight_kg": 1.24,
        "upgradeability": {
            "ram": False,
            "ssd": False
        },
        "repairability_score": 4.0,
        "known_pros": [
            "Silent fanless build",
            "Incredible battery endurance up to 18 hours",
            "Vibrant Retina screen display"
        ],
        "known_cons": [
            "Base model has only 8GB RAM",
            "Supports only one external display natively"
        ],
        "known_issues": [
            "Thermal throttling under sustained multi-core rendering"
        ],
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
        "base_price": 1099.0,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "cpu": "Apple M3 8-Core",
                "gpu": "m3",
                "refresh": 60,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Apple M3 8-Core",
                "gpu": "m3",
                "refresh": 60,
                "price_adjust": 400.0
            },
            {
                "ram": 24,
                "storage": 512,
                "cpu": "Apple M3 8-Core",
                "gpu": "m3",
                "refresh": 60,
                "price_adjust": 600.0
            }
        ]
    },
    {
        "name": "Apple MacBook Pro 14 M3 Pro",
        "brand": "Apple",
        "laptop_type": "creator",
        "manufacturer": "Apple",
        "model_number": "MRX33",
        "operating_system": "macOS Sonoma",
        "linux_supported": False,
        "gpu_type": "integrated",
        "cooling_score": 9.2,
        "panel_type": "Mini-LED",
        "brightness_nits": 1000,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 90.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.8,
        "battery_capacity_wh": 72.4,
        "weight_kg": 1.61,
        "upgradeability": {
            "ram": False,
            "ssd": False
        },
        "repairability_score": 4.5,
        "known_pros": [
            "Best-in-class Liquid Retina XDR 120Hz display",
            "Superb 18-core GPU performance",
            "Full HDMI & SD card slot"
        ],
        "known_cons": [
            "Heavy for 14-inch form factor",
            "Expensive upgrades"
        ],
        "known_issues": [
            "Slight blooming on high-contrast HDR content"
        ],
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
        "base_price": 1999.0,
        "configs": [
            {
                "ram": 18,
                "storage": 512,
                "cpu": "Apple M3 Pro 11-Core",
                "gpu": "m3 pro",
                "refresh": 120,
                "price_adjust": 0.0
            },
            {
                "ram": 36,
                "storage": 1024,
                "cpu": "Apple M3 Pro 12-Core",
                "gpu": "m3 pro",
                "refresh": 120,
                "price_adjust": 600.0
            }
        ]
    },
    {
        "name": "Dell Inspiron 15 3530",
        "brand": "Dell",
        "laptop_type": "student",
        "manufacturer": "Dell",
        "model_number": "3530-i5",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 6.8,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 60.0,
        "adobe_rgb_coverage": 42.0,
        "dci_p3_coverage": 42.0,
        "color_accuracy_delta_e": 3.5,
        "battery_capacity_wh": 41.0,
        "weight_kg": 1.65,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "Affordable student pricing",
            "Comfortable keyboard deck",
            "Full numeric keypad"
        ],
        "known_cons": [
            "Small battery capacity",
            "Muted display colors"
        ],
        "known_issues": [
            "Touchpad can feel stiff at corners"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 499.0,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "Intel Core i5-1335U",
                "gpu": "intel iris xe",
                "refresh": 120,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-1335U",
                "gpu": "intel iris xe",
                "refresh": 120,
                "price_adjust": 60.0
            }
        ]
    },
    {
        "name": "Dell Alienware m16 R2",
        "brand": "Dell",
        "laptop_type": "gaming",
        "manufacturer": "Dell",
        "model_number": "m16-R2",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 9.1,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 80.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 1.8,
        "battery_capacity_wh": 90.0,
        "weight_kg": 2.61,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "Redesigned stealth mode chassis",
            "Massive 240Hz QHD+ gaming panel",
            "Cryo-tech cooling vapor chamber"
        ],
        "known_cons": [
            "Heavy power adapter brick",
            "High price tier"
        ],
        "known_issues": [
            "AlienFX lighting sync bug after sleep"
        ],
        "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
        "base_price": 2199.0,
        "configs": [
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "Intel Core Ultra 7 155H",
                "gpu": "rtx 4070",
                "refresh": 240,
                "price_adjust": 0.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "Intel Core Ultra 9 185H",
                "gpu": "rtx 4080",
                "refresh": 240,
                "price_adjust": 500.0
            }
        ]
    },
    {
        "name": "Acer Predator Helios Neo 16",
        "brand": "Acer",
        "laptop_type": "gaming",
        "manufacturer": "Acer",
        "model_number": "PHN16-72",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 8.7,
        "panel_type": "IPS",
        "brightness_nits": 500,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 78.0,
        "dci_p3_coverage": 80.0,
        "color_accuracy_delta_e": 1.9,
        "battery_capacity_wh": 90.0,
        "weight_kg": 2.6,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "Unbeatable price-to-performance RTX 4060",
            "500 nits high brightness display",
            "5th Gen AeroBlade 3D fans"
        ],
        "known_cons": [
            "Loud turbo fan profiles",
            "Bulky chassis design"
        ],
        "known_issues": [
            "PredatorSense app uses noticeable idle CPU"
        ],
        "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
        "base_price": 1199.0,
        "configs": [
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "Intel Core i7-14700HX",
                "gpu": "rtx 4060",
                "refresh": 165,
                "price_adjust": 0.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "Intel Core i7-14700HX",
                "gpu": "rtx 4070",
                "refresh": 240,
                "price_adjust": 350.0
            }
        ]
    },
    {
        "name": "HP Victus 15",
        "brand": "HP",
        "laptop_type": "gaming",
        "manufacturer": "HP",
        "model_number": "15-fa1000",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 7.0,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 65.0,
        "adobe_rgb_coverage": 45.0,
        "dci_p3_coverage": 45.0,
        "color_accuracy_delta_e": 3.2,
        "battery_capacity_wh": 52.5,
        "weight_kg": 2.29,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 7.8,
        "known_pros": [
            "Excellent value for budget gaming",
            "Upgradeability for both RAM and SSD",
            "Sturdy hinge design"
        ],
        "known_cons": [
            "Screen color accuracy and brightness are low",
            "Plastic chassis feels cheap"
        ],
        "known_issues": [
            "Screen wobble when gaming under fan noise"
        ],
        "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
        "base_price": 600.0,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7640HS",
                "gpu": "RTX 4050",
                "refresh": 144,
                "price_adjust": -100.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7640HS",
                "gpu": "RTX 4050",
                "refresh": 144,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "Intel Core i5-13420H",
                "gpu": "RTX 4050",
                "refresh": 144,
                "price_adjust": 100.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "AMD Ryzen 7 7840HS",
                "gpu": "RTX 4060",
                "refresh": 144,
                "price_adjust": 250.0
            }
        ]
    },
    {
        "name": "Acer Nitro V 15",
        "brand": "Acer",
        "laptop_type": "gaming",
        "manufacturer": "Acer",
        "model_number": "ANV15-51",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 7.2,
        "panel_type": "IPS",
        "brightness_nits": 250,
        "srgb_coverage": 65.0,
        "adobe_rgb_coverage": 48.0,
        "dci_p3_coverage": 48.0,
        "color_accuracy_delta_e": 3.0,
        "battery_capacity_wh": 57.0,
        "weight_kg": 2.1,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.0,
        "known_pros": [
            "Very lightweight for a gaming laptop",
            "Dual M.2 SSD slots for expansion",
            "Highly competitive price"
        ],
        "known_cons": [
            "Battery life is short under general use",
            "Quiet speakers"
        ],
        "known_issues": [
            "Keyboard deck flexes slightly under heavy typing"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 650.0,
        "configs": [
            {
                "ram": 8,
                "storage": 512,
                "cpu": "Intel Core i5-13420H",
                "gpu": "RTX 4050",
                "refresh": 144,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-13420H",
                "gpu": "RTX 4050",
                "refresh": 144,
                "price_adjust": 50.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "Intel Core i7-13620H",
                "gpu": "RTX 4060",
                "refresh": 144,
                "price_adjust": 200.0
            }
        ]
    },
    {
        "name": "Lenovo LOQ 15",
        "brand": "Lenovo",
        "laptop_type": "gaming",
        "manufacturer": "Lenovo",
        "model_number": "LOQ-15IRH8",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 7.6,
        "panel_type": "IPS",
        "brightness_nits": 350,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 72.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 2.0,
        "battery_capacity_wh": 60.0,
        "weight_kg": 2.4,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.2,
        "known_pros": [
            "Superb 100% sRGB display at an affordable price",
            "Excellent keyboard layout with numpad",
            "Very stable gaming thermals"
        ],
        "known_cons": [
            "Power brick is extremely heavy and bulky",
            "Chassis is thick plastic"
        ],
        "known_issues": [
            "Battery drains slightly even when plugged in under extreme turbo load"
        ],
        "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
        "base_price": 800.0,
        "configs": [
            {
                "ram": 12,
                "storage": 512,
                "cpu": "Intel Core i5-13450HX",
                "gpu": "RTX 4050",
                "refresh": 144,
                "price_adjust": -80.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-13450HX",
                "gpu": "RTX 4060",
                "refresh": 144,
                "price_adjust": 50.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "Intel Core i7-13700HX",
                "gpu": "RTX 4060",
                "refresh": 144,
                "price_adjust": 180.0
            },
            {
                "ram": 24,
                "storage": 1024,
                "cpu": "AMD Ryzen 7 7840HX",
                "gpu": "RTX 4060",
                "refresh": 144,
                "price_adjust": 250.0
            }
        ]
    },
    {
        "name": "ASUS TUF Gaming A15",
        "brand": "ASUS",
        "laptop_type": "gaming",
        "manufacturer": "ASUS",
        "model_number": "FA507UV",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 7.8,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 75.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 2.2,
        "battery_capacity_wh": 90.0,
        "weight_kg": 2.2,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.5,
        "known_pros": [
            "Massive 90Wh battery offers top-class runtime",
            "Military-grade durable chassis",
            "Good keyboard with RGB backlighting"
        ],
        "known_cons": [
            "Fans are loud under performance mode",
            "Screen has average viewing angles"
        ],
        "known_issues": [
            "Wi-Fi card can sometimes disconnect under heavy network load"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 950.0,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7535HS",
                "gpu": "RTX 4050",
                "refresh": 144,
                "price_adjust": -100.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "AMD Ryzen 7 7735HS",
                "gpu": "RTX 4060",
                "refresh": 144,
                "price_adjust": 50.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "AMD Ryzen 7 7735HS",
                "gpu": "RTX 4060",
                "refresh": 144,
                "price_adjust": 200.0
            }
        ]
    },
    {
        "name": "Asus ROG Zephyrus G14",
        "brand": "Asus",
        "laptop_type": "gaming",
        "manufacturer": "ASUS",
        "model_number": "GA403",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 8.5,
        "panel_type": "OLED",
        "brightness_nits": 500,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 95.0,
        "dci_p3_coverage": 99.0,
        "color_accuracy_delta_e": 1.2,
        "battery_capacity_wh": 76.0,
        "weight_kg": 1.5,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 7.2,
        "known_pros": [
            "Stunning Nebula HDR OLED display",
            "Thin and lightweight aluminum chassis",
            "Excellent speakers and trackpad"
        ],
        "known_cons": [
            "RAM is completely soldered and cannot be upgraded",
            "Chassis gets warm under heavy gaming"
        ],
        "known_issues": [
            "Slight screen glare in bright outdoor environments"
        ],
        "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
        "base_price": 1400.0,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 7 8840HS",
                "gpu": "RTX 4060",
                "refresh": 120,
                "price_adjust": -100.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "AMD Ryzen 9 8945HS",
                "gpu": "RTX 4070",
                "refresh": 120,
                "price_adjust": 100.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "AMD Ryzen 9 8945HS",
                "gpu": "RTX 4070",
                "refresh": 120,
                "price_adjust": 300.0
            },
            {
                "ram": 32,
                "storage": 2048,
                "cpu": "AMD Ryzen 9 8945HS",
                "gpu": "RTX 4070",
                "refresh": 120,
                "price_adjust": 400.0
            }
        ]
    },
    {
        "name": "ASUS ROG Strix SCAR 16",
        "brand": "ASUS",
        "laptop_type": "gaming",
        "manufacturer": "ASUS",
        "model_number": "G634JY",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 9.2,
        "panel_type": "Mini-LED",
        "brightness_nits": 1100,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 98.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.9,
        "battery_capacity_wh": 90.0,
        "weight_kg": 2.65,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 7.5,
        "known_pros": [
            "Mini-LED display with extreme HDR brightness",
            "Unrivaled gaming frame rates (RTX 4080/4090)",
            "Tri-Fan cooling system prevents throttling"
        ],
        "known_cons": [
            "Extremely heavy and thick chassis",
            "Very poor battery life under gaming"
        ],
        "known_issues": [
            "Coil whine sometimes audible in silent environment under GPU transition"
        ],
        "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
        "base_price": 2400.0,
        "configs": [
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "Intel Core i9-14900HX",
                "gpu": "RTX 4080",
                "refresh": 240,
                "price_adjust": -150.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "Intel Core i9-14900HX",
                "gpu": "RTX 4080",
                "refresh": 240,
                "price_adjust": 0.0
            },
            {
                "ram": 32,
                "storage": 2048,
                "cpu": "Intel Core i9-14900HX",
                "gpu": "RTX 4090",
                "refresh": 240,
                "price_adjust": 500.0
            },
            {
                "ram": 64,
                "storage": 2048,
                "cpu": "Intel Core i9-14900HX",
                "gpu": "RTX 4090",
                "refresh": 240,
                "price_adjust": 800.0
            }
        ]
    },
    {
        "name": "Lenovo ThinkPad E14",
        "brand": "Lenovo",
        "laptop_type": "business",
        "manufacturer": "Lenovo",
        "model_number": "E14-Gen5",
        "operating_system": "Windows 11 Pro",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 7.5,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 70.0,
        "dci_p3_coverage": 70.0,
        "color_accuracy_delta_e": 2.0,
        "battery_capacity_wh": 57.0,
        "weight_kg": 1.53,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.8,
        "known_pros": [
            "Excellent keyboard feedback and TrackPoint",
            "Strong entry-level durability and ports",
            "Upgradable memory slot"
        ],
        "known_cons": [
            "Chassis has slightly thick screen bezels",
            "Speakers are average"
        ],
        "known_issues": [
            "Trackpad clicks can feel stiff initially"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 650.0,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "cpu": "AMD Ryzen 5 7530U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": -100.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7530U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 7 7730U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": 80.0
            }
        ]
    },
    {
        "name": "HP ProBook 440 G10",
        "brand": "HP",
        "laptop_type": "business",
        "manufacturer": "HP",
        "model_number": "440-G10",
        "operating_system": "Windows 11 Pro",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 7.6,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 70.0,
        "dci_p3_coverage": 70.0,
        "color_accuracy_delta_e": 2.1,
        "battery_capacity_wh": 54.0,
        "weight_kg": 1.38,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 8.5,
        "known_pros": [
            "Highly repairable with dual SODIMM slots",
            "Lightweight aluminum deck",
            "Robust enterprise security"
        ],
        "known_cons": [
            "Battery life is standard",
            "Display colors are a bit muted"
        ],
        "known_issues": [
            "CPU fan cycles frequently under fast multitasking"
        ],
        "image_url": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=500&q=80",
        "base_price": 700.0,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "cpu": "Intel Core i5-1335U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": -100.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-1335U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i7-1355U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": 100.0
            }
        ]
    },
    {
        "name": "Lenovo ThinkPad X1 Carbon",
        "brand": "Lenovo",
        "laptop_type": "business",
        "manufacturer": "Lenovo",
        "model_number": "21KC",
        "operating_system": "Windows 11 Pro",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 8.0,
        "panel_type": "IPS",
        "brightness_nits": 400,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 75.0,
        "dci_p3_coverage": 75.0,
        "color_accuracy_delta_e": 1.8,
        "battery_capacity_wh": 57.0,
        "weight_kg": 1.09,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 8.2,
        "known_pros": [
            "Extremely lightweight carbon fiber chassis",
            "Legendary comfortable business keyboard",
            "Superb security and TrackPoint"
        ],
        "known_cons": [
            "Soldered memory cannot be upgraded",
            "High premium pricing"
        ],
        "known_issues": [
            "Chassis collects fingerprint smudges easily"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 1500.0,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core Ultra 7 155U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": 0.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "Intel Core Ultra 7 155U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": 200.0
            },
            {
                "ram": 64,
                "storage": 2048,
                "cpu": "Intel Core Ultra 7 155U",
                "gpu": "Integrated",
                "refresh": 60,
                "price_adjust": 500.0
            }
        ]
    },
    {
        "name": "Dell XPS 16",
        "brand": "Dell",
        "laptop_type": "creator",
        "manufacturer": "Dell",
        "model_number": "XPS9640",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "dedicated",
        "cooling_score": 8.2,
        "panel_type": "OLED",
        "brightness_nits": 500,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 98.0,
        "dci_p3_coverage": 100.0,
        "color_accuracy_delta_e": 0.9,
        "battery_capacity_wh": 99.5,
        "weight_kg": 2.2,
        "upgradeability": {
            "ram": False,
            "ssd": True
        },
        "repairability_score": 6.0,
        "known_pros": [
            "Gorgeous borderless InfinityEdge display",
            "Excellent rendering speed",
            "Large high-fidelity haptic trackpad"
        ],
        "known_cons": [
            "Very heavy at 2.2kg",
            "Soldered RAM limits modifications"
        ],
        "known_issues": [
            "Requires USB-C dongles for legacy ports"
        ],
        "image_url": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=500&q=80",
        "base_price": 1800.0,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core Ultra 7 155H",
                "gpu": "RTX 4050",
                "refresh": 120,
                "price_adjust": 0.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "Intel Core Ultra 9 185H",
                "gpu": "RTX 4060",
                "refresh": 120,
                "price_adjust": 300.0
            },
            {
                "ram": 64,
                "storage": 2048,
                "cpu": "Intel Core Ultra 9 185H",
                "gpu": "RTX 4070",
                "refresh": 120,
                "price_adjust": 700.0
            }
        ]
    },
    {
        "name": "Apple MacBook Pro 16",
        "brand": "Apple",
        "laptop_type": "developer",
        "manufacturer": "Apple",
        "model_number": "A2992",
        "operating_system": "macOS Sonoma",
        "linux_supported": False,
        "gpu_type": "integrated",
        "cooling_score": 9.5,
        "panel_type": "Mini-LED",
        "brightness_nits": 1000,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 99.0,
        "dci_p3_coverage": 99.0,
        "color_accuracy_delta_e": 0.8,
        "battery_capacity_wh": 100.0,
        "weight_kg": 2.14,
        "upgradeability": {
            "ram": False,
            "ssd": False
        },
        "repairability_score": 5.0,
        "known_pros": [
            "Exceptional liquid retina XDR screen contrast",
            "Incredible battery runtime up to 22 hours",
            "Completely silent fans under compiler load"
        ],
        "known_cons": [
            "Soldered storage and memory cannot be altered",
            "High premium cost entry barrier"
        ],
        "known_issues": [
            "Slight screen ghosting during high-speed gaming tests"
        ],
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
        "base_price": 2499.0,
        "configs": [
            {
                "ram": 18,
                "storage": 512,
                "cpu": "Apple M3 Pro",
                "gpu": "M3 Pro",
                "refresh": 120,
                "price_adjust": 0.0
            },
            {
                "ram": 36,
                "storage": 1024,
                "cpu": "Apple M3 Pro",
                "gpu": "M3 Pro",
                "refresh": 120,
                "price_adjust": 400.0
            },
            {
                "ram": 48,
                "storage": 2048,
                "cpu": "Apple M3 Max",
                "gpu": "M3 Max",
                "refresh": 120,
                "price_adjust": 1000.0
            }
        ]
    },
    {
        "name": "Apple MacBook Air 13-inch",
        "brand": "Apple",
        "laptop_type": "ultrabook",
        "manufacturer": "Apple",
        "model_number": "A3113",
        "operating_system": "macOS Sonoma",
        "linux_supported": False,
        "gpu_type": "integrated",
        "cooling_score": 10.0,
        "panel_type": "IPS",
        "brightness_nits": 500,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 85.0,
        "dci_p3_coverage": 98.0,
        "color_accuracy_delta_e": 1.1,
        "battery_capacity_wh": 52.6,
        "weight_kg": 1.24,
        "upgradeability": {
            "ram": False,
            "ssd": False
        },
        "repairability_score": 4.5,
        "known_pros": [
            "Completely silent fanless design",
            "Lightweight and portable aluminum body",
            "Outstanding battery runtime"
        ],
        "known_cons": [
            "Soldered memory cannot be upgraded",
            "Supports only one external display natively"
        ],
        "known_issues": [
            "Throttles slightly under continuous sustained multi-core compiler workloads"
        ],
        "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
        "base_price": 999.0,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "cpu": "Apple M3",
                "gpu": "M3",
                "refresh": 60,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Apple M3",
                "gpu": "M3",
                "refresh": 60,
                "price_adjust": 200.0
            },
            {
                "ram": 24,
                "storage": 1024,
                "cpu": "Apple M3",
                "gpu": "M3",
                "refresh": 60,
                "price_adjust": 500.0
            }
        ]
    },
    {
        "name": "HP Pavilion Plus 14",
        "brand": "HP",
        "laptop_type": "student",
        "manufacturer": "HP",
        "model_number": "14-ey0000",
        "operating_system": "Windows 11 Home",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 7.0,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 70.0,
        "dci_p3_coverage": 70.0,
        "color_accuracy_delta_e": 2.2,
        "battery_capacity_wh": 51.0,
        "weight_kg": 1.38,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 7.8,
        "known_pros": [
            "Very affordable student pricing",
            "Dual upgradeable memory slots",
            "Compact chassis weight"
        ],
        "known_cons": [
            "Average brightness limit nits",
            "Speakers lack bass depth"
        ],
        "known_issues": [
            "Chassis flexes slightly under heavy hand pressure"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 600.0,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "cpu": "Intel Core i5-1340P",
                "gpu": "Intel Graphics",
                "refresh": 90,
                "price_adjust": -50.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "Intel Core i5-1340P",
                "gpu": "Intel Graphics",
                "refresh": 90,
                "price_adjust": 50.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "cpu": "Intel Core i7-1360P",
                "gpu": "Intel Graphics",
                "refresh": 90,
                "price_adjust": 150.0
            }
        ]
    },
    {
        "name": "Lenovo ThinkPad L14 Developer Edition",
        "brand": "Lenovo",
        "laptop_type": "developer",
        "manufacturer": "Lenovo",
        "model_number": "L14-G5-DEV",
        "operating_system": "Ubuntu Linux 24.04 LTS",
        "linux_supported": True,
        "gpu_type": "integrated",
        "cooling_score": 7.8,
        "panel_type": "IPS",
        "brightness_nits": 300,
        "srgb_coverage": 100.0,
        "adobe_rgb_coverage": 70.0,
        "dci_p3_coverage": 70.0,
        "color_accuracy_delta_e": 2.0,
        "battery_capacity_wh": 57.0,
        "weight_kg": 1.4,
        "upgradeability": {
            "ram": True,
            "ssd": True
        },
        "repairability_score": 9.0,
        "known_pros": [
            "Pre-installed Ubuntu Linux with full hardware certification",
            "Excellent keyboard feedback",
            "Very modular design with high repairability"
        ],
        "known_cons": [
            "Plastic build feels less premium than T-series",
            "Charging brick is basic"
        ],
        "known_issues": [
            "Fingerprint reader requires proprietary driver on some distros"
        ],
        "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
        "base_price": 750.0,
        "configs": [
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 5 7535U",
                "gpu": "Radeon",
                "refresh": 60,
                "price_adjust": -50.0
            },
            {
                "ram": 16,
                "storage": 512,
                "cpu": "AMD Ryzen 7 7735U",
                "gpu": "Radeon",
                "refresh": 60,
                "price_adjust": 50.0
            },
            {
                "ram": 32,
                "storage": 1024,
                "cpu": "AMD Ryzen 7 7735U",
                "gpu": "Radeon",
                "refresh": 60,
                "price_adjust": 200.0
            }
        ]
    }
]

        # =====================================================================
        # 2. SMARTPHONES DEFINITIONS (8 Realistic models)
        # =====================================================================
        base_smartphones = [
    {
        "name": "Poco C65",
        "brand": "POCO",
        "phone_type": "budget",
        "manufacturer": "Xiaomi",
        "model_number": "2310FPCA4I",
        "base_price": 71.3,
        "configs": [
            {
                "ram": 4,
                "storage": 128,
                "processor": "MediaTek Helio G85",
                "processor_score": 3800,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.74,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Redmi A3",
        "brand": "Xiaomi",
        "phone_type": "budget",
        "manufacturer": "Xiaomi",
        "model_number": "23129RN51I",
        "base_price": 71.3,
        "configs": [
            {
                "ram": 3,
                "storage": 64,
                "processor": "MediaTek Helio G36",
                "processor_score": 3200,
                "camera_mp": 8.0,
                "battery_mah": 5000,
                "screen_size": 6.71,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Apple iPhone 15 Pro",
        "brand": "Apple",
        "phone_type": "flagship",
        "manufacturer": "Apple",
        "model_number": "A3102",
        "base_price": 1376.8,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Apple A17 Pro",
                "processor_score": 9850,
                "camera_mp": 48.0,
                "battery_mah": 3274,
                "screen_size": 6.1,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy S24 Ultra",
        "brand": "Samsung",
        "phone_type": "flagship",
        "manufacturer": "Samsung",
        "model_number": "SM-S928B",
        "base_price": 1325.8,
        "configs": [
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8 Gen 3 for Galaxy",
                "processor_score": 9900,
                "camera_mp": 200.0,
                "battery_mah": 5000,
                "screen_size": 6.8,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "OnePlus 12",
        "brand": "OnePlus",
        "phone_type": "flagship",
        "manufacturer": "OnePlus",
        "model_number": "CPH2573",
        "base_price": 662.8,
        "configs": [
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8 Gen 3",
                "processor_score": 9750,
                "camera_mp": 50.0,
                "battery_mah": 5400,
                "screen_size": 6.82,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Xiaomi 14",
        "brand": "Xiaomi",
        "phone_type": "compact",
        "manufacturer": "Xiaomi",
        "model_number": "23127PN0CG",
        "base_price": 713.8,
        "configs": [
            {
                "ram": 12,
                "storage": 512,
                "processor": "Snapdragon 8 Gen 3",
                "processor_score": 9700,
                "camera_mp": 50.0,
                "battery_mah": 4610,
                "screen_size": 6.36,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Google Pixel 8a",
        "brand": "Google",
        "phone_type": "compact",
        "manufacturer": "Google",
        "model_number": "G6GPR",
        "base_price": 499.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Google Tensor G3",
                "processor_score": 8400,
                "camera_mp": 64.0,
                "battery_mah": 4492,
                "screen_size": 6.1,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy S23 FE",
        "brand": "Samsung",
        "phone_type": "performance",
        "manufacturer": "Samsung",
        "model_number": "SM-S711B",
        "base_price": 387.6,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Exynos 2200",
                "processor_score": 8200,
                "camera_mp": 50.0,
                "battery_mah": 4500,
                "screen_size": 6.4,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Nothing Phone (2)",
        "brand": "Nothing",
        "phone_type": "performance",
        "manufacturer": "Nothing",
        "model_number": "A065",
        "base_price": 377.4,
        "configs": [
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8+ Gen 1",
                "processor_score": 8750,
                "camera_mp": 50.0,
                "battery_mah": 4700,
                "screen_size": 6.7,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Poco F6 5G",
        "brand": "POCO",
        "phone_type": "performance",
        "manufacturer": "Xiaomi",
        "model_number": "24069PC21I",
        "base_price": 285.6,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 8s Gen 3",
                "processor_score": 8900,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.67,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Redmi 12 5G",
        "brand": "Xiaomi",
        "phone_type": "budget",
        "manufacturer": "Xiaomi",
        "model_number": "23076RN8DY",
        "base_price": 122.4,
        "configs": [
            {
                "ram": 4,
                "storage": 128,
                "processor": "Snapdragon 4 Gen 2",
                "processor_score": 5800,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.79,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Poco M6 5G",
        "brand": "POCO",
        "phone_type": "budget",
        "manufacturer": "Xiaomi",
        "model_number": "23128PC3JI",
        "base_price": 96.9,
        "configs": [
            {
                "ram": 4,
                "storage": 128,
                "processor": "MediaTek Dimensity 6100+",
                "processor_score": 5300,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.74,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Realme Narzo N53",
        "brand": "Realme",
        "phone_type": "budget",
        "manufacturer": "Realme",
        "model_number": "RMX3761",
        "base_price": 91.8,
        "configs": [
            {
                "ram": 4,
                "storage": 64,
                "processor": "Unisoc T612",
                "processor_score": 4200,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.74,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy F14 5G",
        "brand": "Samsung",
        "phone_type": "battery",
        "manufacturer": "Samsung",
        "model_number": "SM-E146B",
        "base_price": 116.8,
        "configs": [
            {
                "ram": 4,
                "storage": 128,
                "processor": "Exynos 1330",
                "processor_score": 5900,
                "camera_mp": 50.0,
                "battery_mah": 6000,
                "screen_size": 6.6,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Poco X6 5G",
        "brand": "POCO",
        "phone_type": "midrange",
        "manufacturer": "Xiaomi",
        "model_number": "23122PCD1I",
        "base_price": 193.8,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 7s Gen 2",
                "processor_score": 7900,
                "camera_mp": 64.0,
                "battery_mah": 5100,
                "screen_size": 6.67,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Redmi Note 13 5G",
        "brand": "Xiaomi",
        "phone_type": "midrange",
        "manufacturer": "Xiaomi",
        "model_number": "2312DRA50I",
        "base_price": 173.4,
        "configs": [
            {
                "ram": 6,
                "storage": 128,
                "processor": "MediaTek Dimensity 6080",
                "processor_score": 6800,
                "camera_mp": 108.0,
                "battery_mah": 5000,
                "screen_size": 6.67,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Moto G54 5G",
        "brand": "Motorola",
        "phone_type": "battery",
        "manufacturer": "Motorola",
        "model_number": "XT2343-1",
        "base_price": 153.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "MediaTek Dimensity 7020",
                "processor_score": 7100,
                "camera_mp": 50.0,
                "battery_mah": 6000,
                "screen_size": 6.5,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Apple iPhone 13",
        "brand": "Apple",
        "phone_type": "compact",
        "manufacturer": "Apple",
        "model_number": "A2633",
        "base_price": 499.0,
        "configs": [
            {
                "ram": 4,
                "storage": 128,
                "processor": "Apple A15 Bionic",
                "processor_score": 8700,
                "camera_mp": 12.0,
                "battery_mah": 3227,
                "screen_size": 6.1,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Google Pixel 7a",
        "brand": "Google",
        "phone_type": "compact",
        "manufacturer": "Google",
        "model_number": "GWKK3",
        "base_price": 387.6,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Google Tensor G2",
                "processor_score": 7600,
                "camera_mp": 64.0,
                "battery_mah": 4385,
                "screen_size": 6.1,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Redmi 13C 5G",
        "brand": "Xiaomi",
        "phone_type": "budget",
        "manufacturer": "Xiaomi",
        "model_number": "23124RN87I",
        "build_score": 7.8,
        "known_pros": [
            "5G connectivity under \u20b910,000",
            "Large 6.74-inch 90Hz display",
            "5000mAh battery capacity"
        ],
        "known_cons": [
            "720p HD+ screen resolution",
            "18W slow charging"
        ],
        "known_issues": [
            "MIUI ads in system file manager (disableable)"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 102.0,
        "configs": [
            {
                "ram": 4,
                "storage": 128,
                "processor": "MediaTek Dimensity 6100+",
                "processor_score": 5400,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.74,
                "price_adjust": 0.0
            },
            {
                "ram": 6,
                "storage": 128,
                "processor": "MediaTek Dimensity 6100+",
                "processor_score": 5400,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.74,
                "price_adjust": 15.0
            }
        ]
    },
    {
        "name": "Moto G34 5G",
        "brand": "Motorola",
        "phone_type": "budget",
        "manufacturer": "Motorola",
        "model_number": "XT2363-4",
        "build_score": 8.2,
        "known_pros": [
            "Clean near-stock Android 14 interface",
            "Snapdragon 695 5G processor",
            "120Hz smooth refresh rate"
        ],
        "known_cons": [
            "HD+ screen resolution",
            "Single speaker output"
        ],
        "known_issues": [
            "Camera app takes 1.5 seconds to save HDR shots"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 122.4,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Snapdragon 695 5G",
                "processor_score": 6200,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.5,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy M15 5G",
        "brand": "Samsung",
        "phone_type": "battery",
        "manufacturer": "Samsung",
        "model_number": "SM-M156B",
        "build_score": 8.3,
        "known_pros": [
            "Massive 6000mAh monster battery",
            "FHD+ 90Hz Super AMOLED screen",
            "4 generations of OS upgrades"
        ],
        "known_cons": [
            "Waterdrop notch design",
            "25W charger sold separately"
        ],
        "known_issues": [
            "Heavy 217g weight due to 6000mAh battery"
        ],
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
        "base_price": 132.6,
        "configs": [
            {
                "ram": 6,
                "storage": 128,
                "processor": "MediaTek Dimensity 6100+",
                "processor_score": 5500,
                "camera_mp": 50.0,
                "battery_mah": 6000,
                "screen_size": 6.5,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "OnePlus Nord CE 4",
        "brand": "OnePlus",
        "phone_type": "midrange",
        "manufacturer": "OnePlus",
        "model_number": "CPH2613",
        "build_score": 8.8,
        "known_pros": [
            "100W SUPERVOOC ultra-fast charging",
            "Snapdragon 7 Gen 3 performance",
            "Aqua Touch screen usability with wet hands"
        ],
        "known_cons": [
            "Plastic frame construction",
            "No alert slider button"
        ],
        "known_issues": [
            "Auto brightness drops slightly when outdoor temperature exceeds 40C"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 255.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Snapdragon 7 Gen 3",
                "processor_score": 8100,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.7,
                "price_adjust": 0.0
            },
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 7 Gen 3",
                "processor_score": 8100,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.7,
                "price_adjust": 20.0
            }
        ]
    },
    {
        "name": "iQOO Z9 5G",
        "brand": "iQOO",
        "phone_type": "gaming",
        "manufacturer": "iQOO",
        "model_number": "I2302",
        "build_score": 8.6,
        "known_pros": [
            "MediaTek Dimensity 7200 highest processor score in class",
            "Sony OIS 50MP primary camera",
            "120Hz AMOLED 1800 nits display"
        ],
        "known_cons": [
            "Pre-installed Hot Apps folder",
            "No ultra-wide camera lens"
        ],
        "known_issues": [
            "Funtouch OS notifications delayed for un-pinned apps"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 204.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "MediaTek Dimensity 7200",
                "processor_score": 7400,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.67,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy S23 5G",
        "brand": "Samsung",
        "phone_type": "compact",
        "manufacturer": "Samsung",
        "model_number": "SM-S911B",
        "build_score": 9.2,
        "known_pros": [
            "Compact 6.1-inch easy one-handed flagship",
            "Snapdragon 8 Gen 2 for Galaxy",
            "IP68 water resistance & wireless charging"
        ],
        "known_cons": [
            "3900mAh battery requires evening top-up for heavy users",
            "25W charging speed"
        ],
        "known_issues": [
            "Mild palm rejection triggers on curved edge swipe"
        ],
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
        "base_price": 459.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Snapdragon 8 Gen 2 for Galaxy",
                "processor_score": 8950,
                "camera_mp": 50.0,
                "battery_mah": 3900,
                "screen_size": 6.1,
                "price_adjust": 0.0
            },
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 8 Gen 2 for Galaxy",
                "processor_score": 8950,
                "camera_mp": 50.0,
                "battery_mah": 3900,
                "screen_size": 6.1,
                "price_adjust": 50.0
            }
        ]
    },
    {
        "name": "Apple iPhone 15",
        "brand": "Apple",
        "phone_type": "flagship",
        "manufacturer": "Apple",
        "model_number": "A3090",
        "build_score": 9.0,
        "known_pros": [
            "Dynamic Island interactive header",
            "48MP main camera with 2x optical zoom crop",
            "USB-C port standard"
        ],
        "known_cons": [
            "Display is limited to 60Hz refresh rate",
            "Charging cap at 20W"
        ],
        "known_issues": [
            "Slight heat under initial iCloud setup restoration"
        ],
        "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
        "base_price": 799.0,
        "configs": [
            {
                "ram": 6,
                "storage": 128,
                "processor": "Apple A16 Bionic",
                "processor_score": 9100,
                "camera_mp": 48.0,
                "battery_mah": 3349,
                "screen_size": 6.1,
                "price_adjust": 0.0
            },
            {
                "ram": 6,
                "storage": 256,
                "processor": "Apple A16 Bionic",
                "processor_score": 9100,
                "camera_mp": 48.0,
                "battery_mah": 3349,
                "screen_size": 6.1,
                "price_adjust": 100.0
            }
        ]
    },
    {
        "name": "Apple iPhone 15 Pro Max",
        "brand": "Apple",
        "phone_type": "flagship",
        "manufacturer": "Apple",
        "model_number": "A3106",
        "build_score": 9.3,
        "known_pros": [
            "Grade 5 Titanium frame lighter design",
            "5x tetraprism optical zoom lens",
            "Action button customization"
        ],
        "known_cons": [
            "High baseline purchase price",
            "Slight lens reflection in dark video scenes"
        ],
        "known_issues": [
            "Early iOS versions experienced thermal spikes (fixed in 17.0.3)"
        ],
        "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
        "base_price": 1199.0,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "processor": "Apple A17 Pro",
                "processor_score": 9800,
                "camera_mp": 48.0,
                "battery_mah": 4422,
                "screen_size": 6.7,
                "price_adjust": 0.0
            },
            {
                "ram": 8,
                "storage": 512,
                "processor": "Apple A17 Pro",
                "processor_score": 9800,
                "camera_mp": 48.0,
                "battery_mah": 4422,
                "screen_size": 6.7,
                "price_adjust": 200.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy S25 Ultra",
        "brand": "Samsung",
        "phone_type": "flagship",
        "manufacturer": "Samsung",
        "model_number": "SM-S938B",
        "build_score": 9.0,
        "known_pros": [
            "Phenomenal 200MP camera resolution and zoom",
            "Integrated S-Pen stylus with low lag",
            "Corning Gorilla Armor screen reduces reflection"
        ],
        "known_cons": [
            "Extremely boxy corners feel uncomfortable",
            "Very expensive price entry barrier"
        ],
        "known_issues": [
            "Haptic motor vibrates slightly weaker than previous models"
        ],
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
        "base_price": 1299.0,
        "configs": [
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8 Gen 4",
                "processor_score": 9200,
                "camera_mp": 200.0,
                "battery_mah": 5000,
                "screen_size": 6.8,
                "price_adjust": 0.0
            },
            {
                "ram": 12,
                "storage": 512,
                "processor": "Snapdragon 8 Gen 4",
                "processor_score": 9200,
                "camera_mp": 200.0,
                "battery_mah": 5000,
                "screen_size": 6.8,
                "price_adjust": 100.0
            },
            {
                "ram": 16,
                "storage": 1024,
                "processor": "Snapdragon 8 Gen 4",
                "processor_score": 9200,
                "camera_mp": 200.0,
                "battery_mah": 5000,
                "screen_size": 6.8,
                "price_adjust": 300.0
            }
        ]
    },
    {
        "name": "Apple iPhone 16 Pro Max",
        "brand": "Apple",
        "phone_type": "flagship",
        "manufacturer": "Apple",
        "model_number": "A3296",
        "build_score": 9.2,
        "known_pros": [
            "Superb 4K video recording with Dolby Vision",
            "Unrivaled processor speed",
            "Exceptional titanium build aesthetics"
        ],
        "known_cons": [
            "Charging limits to 27W maximum speed",
            "Very expensive flagship pricing"
        ],
        "known_issues": [
            "Slight lens flares under direct streetlights at night"
        ],
        "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
        "base_price": 1199.0,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "processor": "Apple A18 Pro",
                "processor_score": 10000,
                "camera_mp": 48.0,
                "battery_mah": 4685,
                "screen_size": 6.9,
                "price_adjust": 0.0
            },
            {
                "ram": 8,
                "storage": 512,
                "processor": "Apple A18 Pro",
                "processor_score": 10000,
                "camera_mp": 48.0,
                "battery_mah": 4685,
                "screen_size": 6.9,
                "price_adjust": 200.0
            },
            {
                "ram": 8,
                "storage": 1024,
                "processor": "Apple A18 Pro",
                "processor_score": 10000,
                "camera_mp": 48.0,
                "battery_mah": 4685,
                "screen_size": 6.9,
                "price_adjust": 400.0
            }
        ]
    },
    {
        "name": "OnePlus 13",
        "brand": "OnePlus",
        "phone_type": "gaming",
        "manufacturer": "OnePlus",
        "model_number": "CPH2609",
        "build_score": 8.5,
        "known_pros": [
            "Superb gaming frame rates and thermal vapor chamber",
            "Incredible 100W wired / 50W wireless charging",
            "Vast 6000mAh battery capacity"
        ],
        "known_cons": [
            "Telephoto zoom lens is basic",
            "Alert slider gathers pocket lint easily"
        ],
        "known_issues": [
            "Display switches aggressively between refresh rates under battery saver"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 799.0,
        "configs": [
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8 Gen 4",
                "processor_score": 9600,
                "camera_mp": 50.0,
                "battery_mah": 6000,
                "screen_size": 6.82,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "processor": "Snapdragon 8 Gen 4",
                "processor_score": 9600,
                "camera_mp": 50.0,
                "battery_mah": 6000,
                "screen_size": 6.82,
                "price_adjust": 100.0
            },
            {
                "ram": 24,
                "storage": 1024,
                "processor": "Snapdragon 8 Gen 4",
                "processor_score": 9600,
                "camera_mp": 50.0,
                "battery_mah": 6000,
                "screen_size": 6.82,
                "price_adjust": 200.0
            }
        ]
    },
    {
        "name": "Nothing Phone 2a",
        "brand": "Nothing",
        "phone_type": "budget",
        "manufacturer": "Nothing",
        "model_number": "A104",
        "build_score": 8.0,
        "known_pros": [
            "Distinctive transparent glyph back layout",
            "Completely clean operating system interface",
            "Long battery endurance screen"
        ],
        "known_cons": [
            "Plastic back scratches very easily",
            "No wireless charging coil"
        ],
        "known_issues": [
            "Glyph lights occasionally blink out of sync with ringtone presets"
        ],
        "image_url": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80",
        "base_price": 349.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Dimensity 7200 Pro",
                "processor_score": 7000,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.7,
                "price_adjust": -99.0
            },
            {
                "ram": 8,
                "storage": 128,
                "processor": "Dimensity 7200 Pro",
                "processor_score": 7000,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.7,
                "price_adjust": 0.0
            },
            {
                "ram": 12,
                "storage": 256,
                "processor": "Dimensity 7200 Pro",
                "processor_score": 7000,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.7,
                "price_adjust": 50.0
            }
        ]
    },
    {
        "name": "OnePlus Nord 4",
        "brand": "OnePlus",
        "phone_type": "budget",
        "manufacturer": "OnePlus",
        "model_number": "CPH2621",
        "build_score": 8.1,
        "known_pros": [
            "Premium metal unibody chassis design",
            "Exceptional 80W rapid charging speeds",
            "Bright 120Hz AMOLED panel"
        ],
        "known_cons": [
            "Pre-installed bloatware apps",
            "Average low-light camera photos"
        ],
        "known_issues": [
            "Metal back conducts heat quickly under gaming"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 285.7,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Snapdragon 7+ Gen 3",
                "processor_score": 8200,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": -29.0
            },
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 7+ Gen 3",
                "processor_score": 8200,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": 20.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy A55",
        "brand": "Samsung",
        "phone_type": "budget",
        "manufacturer": "Samsung",
        "model_number": "SM-A556B",
        "build_score": 8.2,
        "known_pros": [
            "Glass back build feels extremely premium",
            "MicroSD expansion storage slot",
            "Four years of guaranteed OS updates"
        ],
        "known_cons": [
            "Thick bezels look dated",
            "Charging speeds are slow at 25W"
        ],
        "known_issues": [
            "Virtual proximity sensor can fail occasionally during long calls"
        ],
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
        "base_price": 449.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Exynos 1480",
                "processor_score": 6800,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.6,
                "price_adjust": -100.0
            },
            {
                "ram": 12,
                "storage": 256,
                "processor": "Exynos 1480",
                "processor_score": 6800,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.6,
                "price_adjust": 30.0
            }
        ]
    },
    {
        "name": "Apple iPhone SE 4",
        "brand": "Apple",
        "phone_type": "budget",
        "manufacturer": "Apple",
        "model_number": "A3112",
        "build_score": 7.8,
        "known_pros": [
            "Flagship Apple A18 performance chip",
            "Compact lightweight screen structure",
            "Long software update cycle"
        ],
        "known_cons": [
            "Only one single rear camera lens",
            "Small battery capacity mAh limits play time"
        ],
        "known_issues": [
            "Screen has thick borders compared to Android rivals"
        ],
        "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
        "base_price": 429.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Apple A18",
                "processor_score": 8600,
                "camera_mp": 48.0,
                "battery_mah": 3279,
                "screen_size": 6.1,
                "price_adjust": 0.0
            },
            {
                "ram": 8,
                "storage": 256,
                "processor": "Apple A18",
                "processor_score": 8600,
                "camera_mp": 48.0,
                "battery_mah": 3279,
                "screen_size": 6.1,
                "price_adjust": 100.0
            }
        ]
    },
    {
        "name": "Google Pixel 9 Pro",
        "brand": "Google",
        "phone_type": "photography",
        "manufacturer": "Google",
        "model_number": "G4S1M",
        "build_score": 8.8,
        "known_pros": [
            "Incredible AI camera image processing",
            "Beautiful symmetrical screen borders",
            "Seven years of updates support"
        ],
        "known_cons": [
            "Tensor processor runs hot under 3D gaming tests",
            "Slow charging limits"
        ],
        "known_issues": [
            "Fingerprint reader can fail under matte glass protectors"
        ],
        "image_url": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80",
        "base_price": 999.0,
        "configs": [
            {
                "ram": 16,
                "storage": 128,
                "processor": "Tensor G4",
                "processor_score": 8800,
                "camera_mp": 50.0,
                "battery_mah": 5060,
                "screen_size": 6.3,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 256,
                "processor": "Tensor G4",
                "processor_score": 8800,
                "camera_mp": 50.0,
                "battery_mah": 5060,
                "screen_size": 6.3,
                "price_adjust": 100.0
            },
            {
                "ram": 16,
                "storage": 512,
                "processor": "Tensor G4",
                "processor_score": 8800,
                "camera_mp": 50.0,
                "battery_mah": 5060,
                "screen_size": 6.3,
                "price_adjust": 250.0
            }
        ]
    },
    {
        "name": "OnePlus Nord 5",
        "brand": "OnePlus",
        "phone_type": "budget",
        "manufacturer": "OnePlus",
        "model_number": "CPH2715",
        "build_score": 8.3,
        "known_pros": [
            "Superb Snapdragon 8s Gen 3 performance",
            "Gorgeous 1.5K flat AMOLED display",
            "Extremely fast 100W charging"
        ],
        "known_cons": [
            "Plastic frame feels less premium than Nord 4 metal",
            "No headphone jack"
        ],
        "known_issues": [
            "Aggressive RAM management in background"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 336.7,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 8s Gen 3",
                "processor_score": 8500,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": -20.0
            },
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8s Gen 3",
                "processor_score": 8500,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "processor": "Snapdragon 8s Gen 3",
                "processor_score": 8500,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": 40.0
            }
        ]
    },
    {
        "name": "OnePlus Nord 6",
        "brand": "OnePlus",
        "phone_type": "budget",
        "manufacturer": "OnePlus",
        "model_number": "CPH2815",
        "build_score": 8.4,
        "known_pros": [
            "Superb Snapdragon 8s Gen 4 performance",
            "Gorgeous 1.5K flat AMOLED display",
            "Extremely fast 100W charging"
        ],
        "known_cons": [
            "Plastic frame feels less premium than Nord 4 metal",
            "No headphone jack"
        ],
        "known_issues": [
            "Aggressive RAM management in background"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 346.9,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 8s Gen 4",
                "processor_score": 8700,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": -30.0
            },
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8s Gen 4",
                "processor_score": 8700,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": 0.0
            },
            {
                "ram": 16,
                "storage": 512,
                "processor": "Snapdragon 8s Gen 4",
                "processor_score": 8700,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.74,
                "price_adjust": 40.0
            }
        ]
    },
    {
        "name": "iQOO Neo 9 Pro",
        "brand": "iQOO",
        "phone_type": "gaming",
        "manufacturer": "iQOO",
        "model_number": "I2301",
        "build_score": 8.4,
        "known_pros": [
            "Flagship-grade Snapdragon 8 Gen 2 power",
            "Superb 144Hz gaming refresh rate",
            "Very fast 120W charging"
        ],
        "known_cons": [
            "Funtouch OS has pre-installed apps",
            "Plastic frame design"
        ],
        "known_issues": [
            "Slight warming near the camera module during extended gaming"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 357.1,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Snapdragon 8 Gen 2",
                "processor_score": 8900,
                "camera_mp": 50.0,
                "battery_mah": 5160,
                "screen_size": 6.78,
                "price_adjust": -20.0
            },
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 8 Gen 2",
                "processor_score": 8900,
                "camera_mp": 50.0,
                "battery_mah": 5160,
                "screen_size": 6.78,
                "price_adjust": 0.0
            },
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 8 Gen 2",
                "processor_score": 8900,
                "camera_mp": 50.0,
                "battery_mah": 5160,
                "screen_size": 6.78,
                "price_adjust": 30.0
            }
        ]
    },
    {
        "name": "Poco F6",
        "brand": "Poco",
        "phone_type": "gaming",
        "manufacturer": "Xiaomi",
        "model_number": "POCO-F6",
        "build_score": 8.2,
        "known_pros": [
            "Outstanding performance value Snapdragon 8s Gen 3",
            "Lighter weight and comfortable hold",
            "90W fast charging support"
        ],
        "known_cons": [
            "Average battery longevity under gaming",
            "HyperOS has bloatware"
        ],
        "known_issues": [
            "Slight thermal throttling under sustained heavy stress tests"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 306.1,
        "configs": [
            {
                "ram": 8,
                "storage": 256,
                "processor": "Snapdragon 8s Gen 3",
                "processor_score": 8600,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.67,
                "price_adjust": 0.0
            },
            {
                "ram": 12,
                "storage": 512,
                "processor": "Snapdragon 8s Gen 3",
                "processor_score": 8600,
                "camera_mp": 50.0,
                "battery_mah": 5000,
                "screen_size": 6.67,
                "price_adjust": 40.0
            }
        ]
    },
    {
        "name": "Realme GT 6T",
        "brand": "Realme",
        "phone_type": "gaming",
        "manufacturer": "Realme",
        "model_number": "GT-6T",
        "build_score": 8.3,
        "known_pros": [
            "Brightest 6000 nits LTPO AMOLED display",
            "Extremely long-lasting 5500mAh battery",
            "120W charging speed"
        ],
        "known_cons": [
            "Camera setup lacks a telephoto lens",
            "Glossy back panel attracts fingerprints"
        ],
        "known_issues": [
            "Auto-brightness can be slow to adjust in dim rooms"
        ],
        "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
        "base_price": 316.3,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Snapdragon 7+ Gen 3",
                "processor_score": 8100,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.78,
                "price_adjust": -10.0
            },
            {
                "ram": 12,
                "storage": 256,
                "processor": "Snapdragon 7+ Gen 3",
                "processor_score": 8100,
                "camera_mp": 50.0,
                "battery_mah": 5500,
                "screen_size": 6.78,
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Galaxy S24",
        "brand": "Samsung",
        "phone_type": "flagship",
        "manufacturer": "Samsung",
        "model_number": "SM-S921B",
        "build_score": 8.7,
        "known_pros": [
            "Compact lightweight design with premium armor aluminum",
            "Seven years of OS update cycle",
            "Excellent dynamic AMOLED display color"
        ],
        "known_cons": [
            "Exynos processor runs warmer than Snapdragon variants",
            "Slow charging limits to 25W"
        ],
        "known_issues": [
            "Speaker grill can sound slightly tinny at high volumes"
        ],
        "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
        "base_price": 549.0,
        "configs": [
            {
                "ram": 8,
                "storage": 128,
                "processor": "Exynos 2400",
                "processor_score": 9100,
                "camera_mp": 50.0,
                "battery_mah": 4000,
                "screen_size": 6.2,
                "price_adjust": 0.0
            },
            {
                "ram": 8,
                "storage": 256,
                "processor": "Exynos 2400",
                "processor_score": 9100,
                "camera_mp": 50.0,
                "battery_mah": 4000,
                "screen_size": 6.2,
                "price_adjust": 40.0
            }
        ]
    }
]

        # =====================================================================
        # 3. MONITORS DEFINITIONS (7 Realistic models)
        # =====================================================================
        base_monitors = [
    {
        "name": "Acer Nitro QG221Q",
        "brand": "Acer",
        "monitor_type": "budget",
        "manufacturer": "Acer",
        "model_number": "QG221Q",
        "base_price": 56.1,
        "configs": [
            {
                "size": 21.5,
                "res": 1080,
                "refresh": 100,
                "panel_score": 7.3,
                "color_accuracy_delta_e": 2.4,
                "response_time_ms": 1.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "BenQ GW2283",
        "brand": "BenQ",
        "monitor_type": "budget",
        "manufacturer": "BenQ",
        "model_number": "GW2283",
        "base_price": 71.4,
        "configs": [
            {
                "size": 21.5,
                "res": 1080,
                "refresh": 60,
                "panel_score": 7.5,
                "color_accuracy_delta_e": 2.2,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 22MP410-B",
        "brand": "LG",
        "monitor_type": "budget",
        "manufacturer": "LG",
        "model_number": "22MP410-B",
        "base_price": 66.3,
        "configs": [
            {
                "size": 21.5,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.2,
                "color_accuracy_delta_e": 2.5,
                "response_time_ms": 5.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ViewSonic VA2409m",
        "brand": "ViewSonic",
        "monitor_type": "budget",
        "manufacturer": "ViewSonic",
        "model_number": "VA2409m",
        "base_price": 74.5,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 100,
                "panel_score": 7.6,
                "color_accuracy_delta_e": 2.1,
                "response_time_ms": 4.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "MSI PRO MP273",
        "brand": "MSI",
        "monitor_type": "programming",
        "manufacturer": "MSI",
        "model_number": "MP273",
        "base_price": 102.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1080,
                "refresh": 75,
                "panel_score": 8.1,
                "color_accuracy_delta_e": 1.9,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Smart Monitor M7 4K",
        "brand": "Samsung",
        "monitor_type": "highres",
        "manufacturer": "Samsung",
        "model_number": "LS32BM700",
        "base_price": 255.0,
        "configs": [
            {
                "size": 32.0,
                "res": 2160,
                "refresh": 60,
                "panel_score": 9.0,
                "color_accuracy_delta_e": 1.3,
                "response_time_ms": 4.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Dell S2722QC 4K USB-C",
        "brand": "Dell",
        "monitor_type": "highres",
        "manufacturer": "Dell",
        "model_number": "S2722QC",
        "base_price": 306.0,
        "configs": [
            {
                "size": 27.0,
                "res": 2160,
                "refresh": 60,
                "panel_score": 9.3,
                "color_accuracy_delta_e": 1.0,
                "response_time_ms": 4.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Dell P2422H 24-inch",
        "brand": "Dell",
        "monitor_type": "programming",
        "manufacturer": "Dell",
        "model_number": "P2422H",
        "base_price": 163.2,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 60,
                "panel_score": 8.4,
                "color_accuracy_delta_e": 1.7,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 27QN600-B QHD",
        "brand": "LG",
        "monitor_type": "designer",
        "manufacturer": "LG",
        "model_number": "27QN600-B",
        "base_price": 244.8,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 75,
                "panel_score": 8.8,
                "color_accuracy_delta_e": 1.4,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "BenQ GW2785TC",
        "brand": "BenQ",
        "monitor_type": "programming",
        "manufacturer": "BenQ",
        "model_number": "GW2785TC",
        "base_price": 214.2,
        "configs": [
            {
                "size": 27.0,
                "res": 1080,
                "refresh": 75,
                "panel_score": 8.5,
                "color_accuracy_delta_e": 1.8,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS VA27EHE FHD",
        "brand": "ASUS",
        "monitor_type": "office",
        "manufacturer": "ASUS",
        "model_number": "VA27EHE",
        "base_price": 132.6,
        "configs": [
            {
                "size": 27.0,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.8,
                "color_accuracy_delta_e": 2.2,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Odyssey G5 27",
        "brand": "Samsung",
        "monitor_type": "gaming",
        "manufacturer": "Samsung",
        "model_number": "LC27G55TQWWXXL",
        "base_price": 224.4,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 144,
                "panel_score": 8.6,
                "color_accuracy_delta_e": 2.0,
                "response_time_ms": 1.0,
                "panel_type": "VA 1000R",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Dell G2724D Gaming",
        "brand": "Dell",
        "monitor_type": "gaming",
        "manufacturer": "Dell",
        "model_number": "G2724D",
        "base_price": 255.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 165,
                "panel_score": 9.1,
                "color_accuracy_delta_e": 1.1,
                "response_time_ms": 1.0,
                "panel_type": "Fast IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 27UP850-W 4K",
        "brand": "LG",
        "monitor_type": "highres",
        "manufacturer": "LG",
        "model_number": "27UP850-W",
        "base_price": 387.6,
        "configs": [
            {
                "size": 27.0,
                "res": 2160,
                "refresh": 60,
                "panel_score": 9.4,
                "color_accuracy_delta_e": 0.9,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "BenQ EW3270U 4K",
        "brand": "BenQ",
        "monitor_type": "highres",
        "manufacturer": "BenQ",
        "model_number": "EW3270U",
        "base_price": 346.8,
        "configs": [
            {
                "size": 31.5,
                "res": 2160,
                "refresh": 60,
                "panel_score": 9.1,
                "color_accuracy_delta_e": 1.2,
                "response_time_ms": 4.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "MSI G244F 170Hz",
        "brand": "MSI",
        "monitor_type": "competitive",
        "manufacturer": "MSI",
        "model_number": "G244F",
        "base_price": 112.2,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 170,
                "panel_score": 8.6,
                "color_accuracy_delta_e": 1.8,
                "response_time_ms": 1.0,
                "panel_type": "Rapid IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 24GN650-B UltraGear",
        "brand": "LG",
        "monitor_type": "competitive",
        "manufacturer": "LG",
        "model_number": "24GN650-B",
        "base_price": 137.7,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 144,
                "panel_score": 8.7,
                "color_accuracy_delta_e": 1.6,
                "response_time_ms": 1.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Acer Nitro XV272U V3",
        "brand": "Acer",
        "monitor_type": "competitive",
        "manufacturer": "Acer",
        "model_number": "XV272U-V3",
        "base_price": 183.6,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 180,
                "panel_score": 9.0,
                "color_accuracy_delta_e": 1.2,
                "response_time_ms": 0.5,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ViewSonic VX2418-P-MHD",
        "brand": "ViewSonic",
        "monitor_type": "competitive",
        "manufacturer": "ViewSonic",
        "model_number": "VX2418-P-MHD",
        "base_price": 107.1,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 165,
                "panel_score": 8.3,
                "color_accuracy_delta_e": 2.0,
                "response_time_ms": 1.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Acer HA220Q",
        "brand": "Acer",
        "monitor_type": "budget",
        "manufacturer": "Acer",
        "model_number": "HA220Q",
        "base_price": 61.2,
        "configs": [
            {
                "size": 21.5,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.2,
                "color_accuracy_delta_e": 2.5,
                "response_time_ms": 4.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Dell E2016HV",
        "brand": "Dell",
        "monitor_type": "budget",
        "manufacturer": "Dell",
        "model_number": "E2016HV",
        "base_price": 56.1,
        "configs": [
            {
                "size": 19.5,
                "res": 900,
                "refresh": 60,
                "panel_score": 6.8,
                "color_accuracy_delta_e": 3.2,
                "response_time_ms": 5.0,
                "panel_type": "TN",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "HP V22v FHD",
        "brand": "HP",
        "monitor_type": "budget",
        "manufacturer": "HP",
        "model_number": "V22v",
        "base_price": 64.2,
        "configs": [
            {
                "size": 21.5,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.0,
                "color_accuracy_delta_e": 2.8,
                "response_time_ms": 5.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Lenovo D22-20",
        "brand": "Lenovo",
        "monitor_type": "budget",
        "manufacturer": "Lenovo",
        "model_number": "D22-20",
        "base_price": 69.3,
        "configs": [
            {
                "size": 21.5,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.1,
                "color_accuracy_delta_e": 2.6,
                "response_time_ms": 5.0,
                "panel_type": "TN",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "MSI PRO MP241X",
        "brand": "MSI",
        "monitor_type": "budget",
        "manufacturer": "MSI",
        "model_number": "MP241X",
        "base_price": 76.5,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.6,
                "color_accuracy_delta_e": 2.2,
                "response_time_ms": 4.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 27MP400",
        "brand": "LG",
        "monitor_type": "programming",
        "manufacturer": "LG",
        "model_number": "27MP400-B",
        "base_price": 122.4,
        "configs": [
            {
                "size": 27.0,
                "res": 1080,
                "refresh": 75,
                "panel_score": 8.0,
                "color_accuracy_delta_e": 2.0,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS VP249QGR Gaming",
        "brand": "ASUS",
        "monitor_type": "gaming",
        "manufacturer": "ASUS",
        "model_number": "VP249QGR",
        "base_price": 132.6,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 144,
                "panel_score": 8.5,
                "color_accuracy_delta_e": 1.8,
                "response_time_ms": 1.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS ProArt PA247CV",
        "brand": "ASUS",
        "monitor_type": "design",
        "manufacturer": "ASUS",
        "model_number": "PA247CV",
        "base_price": 204.0,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 75,
                "panel_score": 9.2,
                "color_accuracy_delta_e": 0.9,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Dell P2722H Professional",
        "brand": "Dell",
        "monitor_type": "designer",
        "manufacturer": "Dell",
        "model_number": "P2722H",
        "base_price": 193.8,
        "configs": [
            {
                "size": 27.0,
                "res": 1080,
                "refresh": 60,
                "panel_score": 8.6,
                "color_accuracy_delta_e": 1.5,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 27UP650 4K UHD",
        "brand": "LG",
        "monitor_type": "designer",
        "manufacturer": "LG",
        "model_number": "27UP650-W",
        "base_price": 275.4,
        "configs": [
            {
                "size": 27.0,
                "res": 2160,
                "refresh": 60,
                "panel_score": 9.3,
                "color_accuracy_delta_e": 1.0,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 27GN800 UltraGear",
        "brand": "LG",
        "monitor_type": "gaming",
        "manufacturer": "LG",
        "model_number": "27GN800-B",
        "base_price": 234.6,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 144,
                "panel_score": 8.9,
                "color_accuracy_delta_e": 1.4,
                "response_time_ms": 1.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Gigabyte M27Q QHD",
        "brand": "Gigabyte",
        "monitor_type": "gaming",
        "manufacturer": "Gigabyte",
        "model_number": "M27Q-EK",
        "base_price": 270.4,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 170,
                "panel_score": 9.1,
                "color_accuracy_delta_e": 1.2,
                "response_time_ms": 0.5,
                "panel_type": "SS IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Acer EK220Q",
        "brand": "Acer",
        "monitor_type": "budget",
        "manufacturer": "Acer",
        "model_number": "EK220Q-A",
        "build_score": 7.5,
        "known_pros": [
            "Ultra affordable price tag",
            "100Hz refresh rate smooth browsing",
            "Flicker-less technology"
        ],
        "known_cons": [
            "Basic VA panel viewing angles",
            "No height adjustment"
        ],
        "known_issues": [
            "VESA mount screw holes are shallow"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 66.3,
        "configs": [
            {
                "size": 21.5,
                "res": 1080,
                "refresh": 100,
                "panel_score": 6.5,
                "color_accuracy_delta_e": 3.0,
                "response_time_ms": 5.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "BenQ GW2480",
        "brand": "BenQ",
        "monitor_type": "budget",
        "manufacturer": "BenQ",
        "model_number": "GW2480",
        "build_score": 8.1,
        "known_pros": [
            "Eye-Care Brightness Intelligence sensor",
            "Slim bezel IPS display",
            "Built-in cable management"
        ],
        "known_cons": [
            "60Hz refresh rate limit",
            "Basic 250 nits brightness"
        ],
        "known_issues": [
            "Auto-brightness sensor can be over-sensitive in dark rooms"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 91.8,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 60,
                "panel_score": 7.8,
                "color_accuracy_delta_e": 2.2,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 24MP400",
        "brand": "LG",
        "monitor_type": "budget",
        "manufacturer": "LG",
        "model_number": "24MP400-B",
        "build_score": 8.0,
        "known_pros": [
            "3-side virtually borderless design",
            "AMD FreeSync support",
            "Reader mode for eye comfort"
        ],
        "known_cons": [
            "75Hz refresh rate",
            "No built-in speakers"
        ],
        "known_issues": [
            "Stand tilt adjustment feels stiff out of box"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 81.6,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.5,
                "color_accuracy_delta_e": 2.4,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ViewSonic VA2432-MHD",
        "brand": "ViewSonic",
        "monitor_type": "budget",
        "manufacturer": "ViewSonic",
        "model_number": "VA2432-MHD",
        "build_score": 8.0,
        "known_pros": [
            "SuperClear IPS panel technology",
            "Dual integrated speakers",
            "HDMI and DisplayPort inputs"
        ],
        "known_cons": [
            "Power LED is bright at night",
            "75Hz maximum refresh"
        ],
        "known_issues": [
            "Menu button navigation takes time to learn"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 86.7,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 75,
                "panel_score": 7.6,
                "color_accuracy_delta_e": 2.1,
                "response_time_ms": 4.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Smart Monitor M5",
        "brand": "Samsung",
        "monitor_type": "programming",
        "manufacturer": "Samsung",
        "model_number": "LS27C500",
        "build_score": 8.4,
        "known_pros": [
            "Smart TV OS built-in with remote",
            "AirPlay 2 & Wireless DeX support",
            "Office 365 cloud desktop integration"
        ],
        "known_cons": [
            "FHD resolution on 27-inch panel",
            "60Hz refresh rate"
        ],
        "known_issues": [
            "Tizen OS app store has minor lag when launching Netflix"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 153.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1080,
                "refresh": 60,
                "panel_score": 8.0,
                "color_accuracy_delta_e": 2.0,
                "response_time_ms": 4.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Acer Nitro VG271U",
        "brand": "Acer",
        "monitor_type": "gaming",
        "manufacturer": "Acer",
        "model_number": "VG271U-M3",
        "build_score": 8.7,
        "known_pros": [
            "2K QHD 180Hz IPS display at under \u20b920k",
            "95% DCI-P3 wide color gamut",
            "HDR10 support"
        ],
        "known_cons": [
            "Stand lacks height adjustment",
            "Speakers are weak"
        ],
        "known_issues": [
            "Slight backlight bleed on bottom corners"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 204.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 180,
                "panel_score": 8.8,
                "color_accuracy_delta_e": 1.4,
                "response_time_ms": 1.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ViewSonic ColorPro VP2468a",
        "brand": "ViewSonic",
        "monitor_type": "design",
        "manufacturer": "ViewSonic",
        "model_number": "VP2468a",
        "build_score": 9.1,
        "known_pros": [
            "100% sRGB factory-calibrated Delta E < 2",
            "USB-C with 65W power delivery",
            "Pantone validated color accuracy"
        ],
        "known_cons": [
            "1080p resolution",
            "60Hz refresh rate"
        ],
        "known_issues": [
            "Auto pivot sensor requires software driver installation"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 224.5,
        "configs": [
            {
                "size": 23.8,
                "res": 1080,
                "refresh": 60,
                "panel_score": 9.3,
                "color_accuracy_delta_e": 0.8,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "BenQ PD2500Q Designer",
        "brand": "BenQ",
        "monitor_type": "design",
        "manufacturer": "BenQ",
        "model_number": "PD2500Q",
        "build_score": 9.2,
        "known_pros": [
            "2K 1440p high pixel density 25-inch panel",
            "CAD/CAM & Animation display modes",
            "Technicolor Color Certified"
        ],
        "known_cons": [
            "Thicker bezels",
            "60Hz refresh rate"
        ],
        "known_issues": [
            "DisplayPort daisy-chaining requires DP 1.2 MST support"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 250.0,
        "configs": [
            {
                "size": 25.0,
                "res": 1440,
                "refresh": 60,
                "panel_score": 9.4,
                "color_accuracy_delta_e": 0.9,
                "response_time_ms": 4.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "ASUS ROG Swift PG27AQN",
        "brand": "ASUS",
        "monitor_type": "gaming",
        "manufacturer": "ASUS",
        "model_number": "PG27AQN",
        "build_score": 9.3,
        "known_pros": [
            "Extreme 360Hz refresh rate at 1440p",
            "Ultrafast IPS panel with 1ms response",
            "NVIDIA Reflex Analyzer built-in"
        ],
        "known_cons": [
            "High premium price for esports monitor",
            "No internal speakers"
        ],
        "known_issues": [
            "Active cooling fan runs softly inside monitor housing"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 899.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 360,
                "panel_score": 9.5,
                "color_accuracy_delta_e": 1.2,
                "response_time_ms": 1.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 27GP850-B UltraGear",
        "brand": "LG",
        "monitor_type": "gaming",
        "manufacturer": "LG",
        "model_number": "27GP850-B",
        "build_score": 8.8,
        "known_pros": [
            "Nano IPS display with 1ms GtG speed",
            "180Hz overclocked smooth motion",
            "VESA DisplayHDR 400 certified"
        ],
        "known_cons": [
            "Contrast ratio is mediocre (1000:1)",
            "HDR brightness is basic"
        ],
        "known_issues": [
            "IPS glow in dark room viewing"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 399.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 180,
                "panel_score": 8.8,
                "color_accuracy_delta_e": 1.5,
                "response_time_ms": 1.0,
                "panel_type": "Nano IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung ViewFinity S8 4K",
        "brand": "Samsung",
        "monitor_type": "design",
        "manufacturer": "Samsung",
        "model_number": "S27B800",
        "build_score": 8.6,
        "known_pros": [
            "Matte display finish eliminates glare",
            "USB-C with 90W power delivery charge",
            "98% DCI-P3 wide color gamut"
        ],
        "known_cons": [
            "Refresh rate capped at 60Hz",
            "Plastic stand base takes up desk space"
        ],
        "known_issues": [
            "USB hub turns off in deep standby"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 499.0,
        "configs": [
            {
                "size": 27.0,
                "res": 2160,
                "refresh": 60,
                "panel_score": 9.0,
                "color_accuracy_delta_e": 0.9,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "AOC 24G2",
        "brand": "AOC",
        "monitor_type": "gaming",
        "build_score": 7.2,
        "known_pros": [
            "Exceptional value for budget gaming setup",
            "Fluid high refresh rate with stand height adjustment",
            "Vibrant colors on IPS screen"
        ],
        "known_cons": [
            "1080p resolution has standard screen clarity",
            "Plastic frame feels light and budget"
        ],
        "known_issues": [
            "Speakers are quiet and tinny"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 180.0,
        "configs": [
            {
                "size": 24.0,
                "res": 1080,
                "refresh": 144,
                "panel_score": 7.0,
                "color_accuracy_delta_e": 2.8,
                "response_time_ms": 1.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            },
            {
                "size": 24.0,
                "res": 1080,
                "refresh": 165,
                "panel_score": 7.0,
                "color_accuracy_delta_e": 2.6,
                "response_time_ms": 1.0,
                "panel_type": "IPS",
                "price_adjust": 20.0
            }
        ]
    },
    {
        "name": "ASUS ProArt PA278QV",
        "brand": "ASUS",
        "monitor_type": "design",
        "build_score": 7.6,
        "known_pros": [
            "Calman Verified factory color calibration out of the box",
            "Ergonomic stand with full pivot height adjustment",
            "Affordable professional color display"
        ],
        "known_cons": [
            "75Hz refresh rate is not suitable for high-speed esports",
            "No HDR support"
        ],
        "known_issues": [
            "Integrated speakers sound very flat"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 310.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 75,
                "panel_score": 7.5,
                "color_accuracy_delta_e": 1.0,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "BenQ PD2700Q",
        "brand": "BenQ",
        "monitor_type": "design",
        "build_score": 7.7,
        "known_pros": [
            "100% sRGB and Rec. 709 color gamut accuracy",
            "Dedicated CAD/CAM and Animation layout screen modes",
            "Dualview feature allows side-by-side mode review"
        ],
        "known_cons": [
            "Thick traditional bezels look chunky",
            "Only 60Hz screen refresh rate"
        ],
        "known_issues": [
            "Stand base is wide and heavy"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 350.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 60,
                "panel_score": 7.6,
                "color_accuracy_delta_e": 1.1,
                "response_time_ms": 5.0,
                "panel_type": "IPS",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Dell UltraSharp U2723QE",
        "brand": "Dell",
        "monitor_type": "design",
        "build_score": 8.5,
        "known_pros": [
            "IPS Black panel double contrast compared to standard IPS",
            "Rich USB-C hub connectivity with KVM",
            "Superb factory calibration setup"
        ],
        "known_cons": [
            "Limited to 60Hz, not suited for competitive play",
            "Response time is average"
        ],
        "known_issues": [
            "Stand pivot rotation can feel slightly stiff out of the box"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 520.0,
        "configs": [
            {
                "size": 27.0,
                "res": 2160,
                "refresh": 60,
                "panel_score": 8.5,
                "color_accuracy_delta_e": 0.8,
                "response_time_ms": 5.0,
                "panel_type": "IPS Black",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "LG 27GR95QE UltraGear",
        "brand": "LG",
        "monitor_type": "gaming",
        "build_score": 9.2,
        "known_pros": [
            "Absolute infinite contrast and deep OLED blacks",
            "Instantaneous 0.03ms pixel response time",
            "High 240Hz screen refresh rate"
        ],
        "known_cons": [
            "Matte anti-glare screen coating looks slightly grainy on white web pages",
            "OLED pixel layout can cause slight text color fringing"
        ],
        "known_issues": [
            "ABL (Auto Brightness Limiter) dims display under full white windows"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 900.0,
        "configs": [
            {
                "size": 27.0,
                "res": 1440,
                "refresh": 240,
                "panel_score": 9.5,
                "color_accuracy_delta_e": 1.8,
                "response_time_ms": 0.03,
                "panel_type": "OLED",
                "price_adjust": 0.0
            }
        ]
    },
    {
        "name": "Samsung Odyssey G7",
        "brand": "Samsung",
        "monitor_type": "gaming",
        "build_score": 8.2,
        "known_pros": [
            "Aggressive 1000R curve offers extreme immersion",
            "240Hz refresh rate is lightning fast",
            "Deep blacks from high contrast VA panel"
        ],
        "known_cons": [
            "Screen curve distorts straight lines in design apps",
            "Narrow viewing angles"
        ],
        "known_issues": [
            "Scanlines visible under specific high contrast color grids"
        ],
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
        "base_price": 550.0,
        "configs": [
            {
                "size": 32.0,
                "res": 1440,
                "refresh": 240,
                "panel_score": 7.0,
                "color_accuracy_delta_e": 2.5,
                "response_time_ms": 1.0,
                "panel_type": "VA",
                "price_adjust": 0.0
            }
        ]
    }
]

        # Process and save Laptops
        for base in base_laptops:
            base_price = base["base_price"]
            configs = base["configs"]
            for idx, config in enumerate(configs):
                ram = config["ram"]
                stor = config["storage"]
                cpu = config["cpu"]
                gpu = config["gpu"]
                refresh = config["refresh"]
                price = (base_price + config["price_adjust"]) * 98.0

                specs = base.copy()
                specs.pop("base_price", None)
                specs.pop("configs", None)

                cpu_multi_core, cpu_single_core, ai_score_tops, gpu_name, gpu_score_3dmark, gaming_fps_1080p, gaming_fps_1440p, ray_tracing_score = get_laptop_performance_metrics(
                    cpu, gpu, ram
                )

                specs.update({
                    "ram_gb": ram,
                    "storage_gb": stor,
                    "cpu_multi_core": cpu_multi_core,
                    "cpu_single_core": cpu_single_core,
                    "ai_score_tops": ai_score_tops,
                    "gpu_name": gpu_name,
                    "gpu_score_3dmark": gpu_score_3dmark,
                    "gaming_fps_1080p": gaming_fps_1080p,
                    "gaming_fps_1440p": gaming_fps_1440p,
                    "ray_tracing_score": ray_tracing_score,
                    "cpu_score": cpu_multi_core,
                    "gpu_score": gpu_score_3dmark,
                    "refresh_rate_hz": refresh,
                    "gpu_brand": "NVIDIA" if "RTX" in gpu or "GeForce" in gpu_name else "Intel" if "Intel" in gpu_name else "AMD" if "Radeon" in gpu_name else "Apple",
                    "gpu_model": gpu_name.split("GeForce ")[-1] if "GeForce" in gpu_name else gpu_name,
                    "cpu_brand": "Apple" if "Apple" in cpu else "Intel" if "Intel" in cpu else "AMD",
                    "cpu_model": cpu,
                    "estimated_office_hours": round(base["battery_capacity_wh"] / (3.0 if base["brand"] == "Apple" else 5.5), 1),
                    "gaming_hours": round(base["battery_capacity_wh"] / (45.0 if base["gpu_type"] == "dedicated" else 25.0), 1),
                    "video_playback_hours": round(base["battery_capacity_wh"] / (2.5 if base["brand"] == "Apple" else 4.5), 1),
                    "source": "Seed Catalog",
                    "model_number": f"{base['model_number']}-{ram}-{stor}",
                    "release_year": 2025,
                    "last_verified": "2026-06-12",
                    "region": "IN",
                    "currency": "USD",
                    "tags": [base["laptop_type"], base["brand"].lower()]
                })

                sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{ram}-{stor}-r{idx}"
                name = f"{base['name']} ({ram}GB RAM, {stor}GB SSD)"

                v_key = f"{ram}GB-{stor}GB-{cpu}"
                img_url = specs.get("image_url")
                products.append(Product(
                    sku=sku,
                    name=name,
                    category="laptop",
                    price_inr=price,
                    specs=specs,
                    is_active=True,
                    brand=base["brand"],
                    product_family=base["name"],
                    model=base["name"],
                    variant_key=v_key,
                    source_type="real_seed",
                    source_reference="Seed Catalog v2.0",
                    identity_verified=True,
                    spec_verified=False,
                    image_verified=False,
                    price_verified=True,
                    verification_status="partially_verified",
                    confidence_level=0.75,
                    spec_coverage=0.85,
                    image_url=img_url,
                    image_match_level="verified_exact_model" if base["brand"] in ["Apple", "Dell", "HP", "Lenovo"] else "verified_product_family",
                    ingestion_status="recommendation_eligible"
                ))

        # Process and save Smartphones
        for base in base_smartphones:
            base_price = base["base_price"]
            configs = base["configs"]
            for idx, config in enumerate(configs):
                ram = config["ram"]
                stor = config["storage"]
                processor = config["processor"]
                proc_score = config["processor_score"]
                camera = config["camera_mp"]
                battery = config["battery_mah"]
                size = config["screen_size"]
                price = (base_price + config["price_adjust"]) * 98.0

                specs = base.copy()
                specs.pop("base_price", None)
                specs.pop("configs", None)

                specs.update({
                    "ram_gb": ram,
                    "storage_gb": stor,
                    "processor_name": processor,
                    "processor_score": proc_score,
                    "camera_mp": camera,
                    "battery_mah": battery,
                    "screen_size": size,
                    "source": "Seed Catalog",
                    "model_number": f"{base['model_number']}-{ram}-{stor}",
                    "release_year": 2025,
                    "last_verified": "2026-06-12",
                    "region": "IN",
                    "currency": "USD",
                    "tags": [base["phone_type"], base["brand"].lower()]
                })

                sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{ram}-{stor}-r{idx}"
                name = f"{base['name']} ({ram}GB RAM, {stor}GB Storage)"

                v_key = f"{ram}GB-{stor}GB"
                img_url = specs.get("image_url")
                products.append(Product(
                    sku=sku,
                    name=name,
                    category="smartphone",
                    price_inr=price,
                    specs=specs,
                    is_active=True,
                    brand=base["brand"],
                    product_family=base["name"],
                    model=base["name"],
                    variant_key=v_key,
                    source_type="real_seed",
                    source_reference="Seed Catalog v2.0",
                    identity_verified=True,
                    spec_verified=False,
                    image_verified=False,
                    price_verified=True,
                    verification_status="partially_verified",
                    confidence_level=0.75,
                    spec_coverage=0.85,
                    image_url=img_url,
                    image_match_level="verified_exact_model" if base["brand"] in ["Apple", "Samsung", "Google"] else "verified_product_family",
                    ingestion_status="recommendation_eligible"
                ))

        # Process and save Monitors
        for base in base_monitors:
            base_price = base["base_price"]
            configs = base["configs"]
            for idx, config in enumerate(configs):
                size = config["size"]
                res = config["res"]
                refresh = config["refresh"]
                panel_score = config["panel_score"]
                delta_e = config["color_accuracy_delta_e"]
                response = config["response_time_ms"]
                panel = config["panel_type"]
                price = (base_price + config["price_adjust"]) * 98.0

                specs = base.copy()
                specs.pop("base_price", None)
                specs.pop("configs", None)

                specs.update({
                    "screen_size_inches": size,
                    "resolution_p": res,
                    "refresh_rate_hz": refresh,
                    "panel_score": panel_score,
                    "color_accuracy_delta_e": delta_e,
                    "response_time_ms": response,
                    "panel_type": panel,
                    "color_accuracy_score": max(1.0, 10.0 - (delta_e * 2.0)),
                    "color_accurate": (base["monitor_type"] == "design"),
                    "source": "Seed Catalog",
                    "model_number": f"{base['brand'].upper()}-{int(size)}-{res}-{refresh}",
                    "release_year": 2025,
                    "last_verified": "2026-06-12",
                    "region": "IN",
                    "currency": "USD",
                    "tags": [base["monitor_type"], base["brand"].lower()]
                })

                sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{int(size)}-{res}-{refresh}-{idx}"
                name = f"{base['name']} {int(size)}\" ({res}p, {refresh}Hz)"

                v_key = f"{int(size)}in-{res}p-{refresh}Hz-{panel}"
                img_url = specs.get("image_url")
                products.append(Product(
                    sku=sku,
                    name=name,
                    category="monitor",
                    price_inr=price,
                    specs=specs,
                    is_active=True,
                    brand=base["brand"],
                    product_family=base["name"],
                    model=base["name"],
                    variant_key=v_key,
                    source_type="real_seed",
                    source_reference="Seed Catalog v2.0",
                    identity_verified=True,
                    spec_verified=False,
                    image_verified=False,
                    price_verified=True,
                    verification_status="partially_verified",
                    confidence_level=0.75,
                    spec_coverage=0.85,
                    image_url=img_url,
                    image_match_level="verified_product_family",
                    ingestion_status="recommendation_eligible"
                ))

        # =====================================================================
        # 4. PROCEDURAL CATALOG EXPANSION (40,000+ Products)
        # =====================================================================
        import random
        
        # Colors and Sellers for realistic listing variation
        COLORS = ["Shadow Black", "Performance Blue", "Ceramic White", "Space Gray", "Silver", "Midnight", "Abyss Blue", "Platinum Silver", "Storm Grey", "Slate Gray"]
        PHONE_COLORS = ["Obsidian", "Porcelain", "Titanium Gray", "Titanium Black", "Titanium Silver", "Charcoal", "Mint", "Bay Blue", "Rose", "Starlight"]
        SELLERS = ["Appario Retail", "RetailNet", "Darshita Electronics", "SV Peripheral", "SuperCom Net", "Cocoblu Retail"]

        # A. Procedurally generate 15,000 Laptops (Real configs only)
        logger.info("Generating 15,000 procedural laptops...")
        for i in range(15000):
            base = random.choice(base_laptops)
            config = random.choice(base["configs"])
            
            ram = config["ram"]
            stor = config["storage"]
            cpu = config["cpu"]
            gpu = config["gpu"]
            refresh = config["refresh"]
            
            # Base price + config adjustment
            base_price = base["base_price"]
            price = (base_price + config["price_adjust"]) * 98.0
            
            # Add minor seller price noise (+/- $15)
            price += random.uniform(-1500.0, 1500.0)
            price = max(25000.0, round(price, 2))

            cpu_multi_core, cpu_single_core, ai_score_tops, gpu_name, gpu_score_3dmark, gaming_fps_1080p, gaming_fps_1440p, ray_tracing_score = get_laptop_performance_metrics(
                cpu, gpu, ram
            )

            specs = base.copy()
            specs.pop("base_price", None)
            specs.pop("configs", None)

            specs.update({
                "ram_gb": ram,
                "storage_gb": stor,
                "cpu_multi_core": cpu_multi_core,
                "cpu_single_core": cpu_single_core,
                "ai_score_tops": ai_score_tops,
                "gpu_name": gpu_name,
                "gpu_score_3dmark": gpu_score_3dmark,
                "gaming_fps_1080p": gaming_fps_1080p,
                "gaming_fps_1440p": gaming_fps_1440p,
                "ray_tracing_score": ray_tracing_score,
                "cpu_score": cpu_multi_core,
                "gpu_score": gpu_score_3dmark,
                "refresh_rate_hz": refresh,
                "gpu_brand": "NVIDIA" if "RTX" in gpu or "GeForce" in gpu_name else "Intel" if "Intel" in gpu_name else "AMD" if "Radeon" in gpu_name else "Apple",
                "gpu_model": gpu_name.split("GeForce ")[-1] if "GeForce" in gpu_name else gpu_name,
                "cpu_brand": "Apple" if "Apple" in cpu else "Intel" if "Intel" in cpu else "AMD",
                "cpu_model": cpu,
                "estimated_office_hours": round(base["battery_capacity_wh"] / (3.0 if base["brand"] == "Apple" else 5.5), 1),
                "gaming_hours": round(base["battery_capacity_wh"] / (45.0 if base["gpu_type"] == "dedicated" else 25.0), 1),
                "video_playback_hours": round(base["battery_capacity_wh"] / (2.5 if base["brand"] == "Apple" else 4.5), 1),
                "source": "Procedural Catalog",
                "model_number": f"{base['model_number']}-{ram}-{stor}-proc-{i}",
                "release_year": 2025,
                "last_verified": "2026-06-12",
                "region": "IN",
                "currency": "USD",
                "tags": [base["laptop_type"], base["brand"].lower()]
            })

            color = random.choice(COLORS)
            seller = random.choice(SELLERS)
            sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{ram}-{stor}-proc-{i}"
            name = f"{base['name']} ({ram}GB RAM, {stor}GB SSD, {cpu}) - {color}"

            v_key = f"{ram}GB-{stor}GB-{cpu}-syn-{i}"
            img_url = specs.get("image_url")
            products.append(Product(
                sku=sku,
                name=name,
                category="laptop",
                price_inr=price,
                specs=specs,
                is_active=True,
                brand=base["brand"],
                product_family=base["name"],
                model=base["name"],
                variant_key=v_key,
                source_type="synthetic",
                source_reference="Procedural Benchmark Catalog",
                identity_verified=False,
                spec_verified=False,
                image_verified=False,
                price_verified=False,
                verification_status="unverified",
                confidence_level=0.50,
                spec_coverage=0.60,
                image_url=img_url,
                image_match_level="unverified",
                ingestion_status="recommendation_eligible"
            ))

        # B. Procedurally generate 15,000 Smartphones (Real configs only)
        logger.info("Generating 15,000 procedural smartphones...")
        for i in range(15000):
            base = random.choice(base_smartphones)
            config = random.choice(base["configs"])
            
            ram = config["ram"]
            stor = config["storage"]
            processor = config["processor"]
            proc_score = config["processor_score"]
            camera = config["camera_mp"]
            battery = config["battery_mah"]
            size = config["screen_size"]
            
            base_price = base["base_price"]
            price = (base_price + config["price_adjust"]) * 98.0
            
            # Add minor seller price noise (+/- $10)
            price += random.uniform(-10.0, 10.0)
            price = max(150.0, round(price, 2))

            specs = base.copy()
            specs.pop("base_price", None)
            specs.pop("configs", None)

            specs.update({
                "ram_gb": ram,
                "storage_gb": stor,
                "processor_name": processor,
                "processor_score": proc_score,
                "camera_mp": camera,
                "battery_mah": battery,
                "screen_size": size,
                "source": "Procedural Catalog",
                "model_number": f"{base['model_number']}-{ram}-{stor}-proc-{i}",
                "release_year": 2025,
                "last_verified": "2026-06-12",
                "region": "IN",
                "currency": "USD",
                "tags": [base["phone_type"], base["brand"].lower()]
            })

            color = random.choice(PHONE_COLORS)
            sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{ram}-{stor}-proc-{i}"
            name = f"{base['name']} ({ram}GB RAM, {stor}GB Storage) - {color}"

            v_key = f"{ram}GB-{stor}GB-syn-{i}"
            img_url = specs.get("image_url")
            products.append(Product(
                sku=sku,
                name=name,
                category="smartphone",
                price_inr=price,
                specs=specs,
                is_active=True,
                brand=base["brand"],
                product_family=base["name"],
                model=base["name"],
                variant_key=v_key,
                source_type="synthetic",
                source_reference="Procedural Benchmark Catalog",
                identity_verified=False,
                spec_verified=False,
                image_verified=False,
                price_verified=False,
                verification_status="unverified",
                confidence_level=0.50,
                spec_coverage=0.60,
                image_url=img_url,
                image_match_level="unverified",
                ingestion_status="recommendation_eligible"
            ))

        # C. Procedurally generate 10,000 Monitors (Real configs only)
        logger.info("Generating 10,000 procedural monitors...")
        for i in range(10000):
            base = random.choice(base_monitors)
            config = random.choice(base["configs"])
            
            size = config["size"]
            res = config["res"]
            refresh = config["refresh"]
            panel_score = config["panel_score"]
            delta_e = config["color_accuracy_delta_e"]
            response = config["response_time_ms"]
            panel = config["panel_type"]
            
            base_price = base["base_price"]
            price = (base_price + config["price_adjust"]) * 98.0
            
            # Add minor seller price noise (+/- $8)
            price += random.uniform(-8.0, 8.0)
            price = max(10000.0, round(price, 2))

            specs = base.copy()
            specs.pop("base_price", None)
            specs.pop("configs", None)

            specs.update({
                "screen_size_inches": size,
                "resolution_p": res,
                "refresh_rate_hz": refresh,
                "panel_score": panel_score,
                "color_accuracy_delta_e": delta_e,
                "response_time_ms": response,
                "panel_type": panel,
                "color_accuracy_score": max(1.0, 10.0 - (delta_e * 2.0)),
                "color_accurate": base["monitor_type"] == "design",
                "source": "Procedural Catalog",
                "model_number": f"{base['brand'].upper()}-{int(size)}-{res}-{refresh}-proc-{i}",
                "release_year": 2025,
                "last_verified": "2026-06-12",
                "region": "IN",
                "currency": "USD",
                "tags": [base["monitor_type"], base["brand"].lower()]
            })

            sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{int(size)}-{res}-{refresh}-proc-{i}"
            name = f"{base['name']} {int(size)}\" ({res}p, {refresh}Hz, {panel})"

            v_key = f"{int(size)}in-{res}p-{refresh}Hz-syn-{i}"
            img_url = specs.get("image_url")
            products.append(Product(
                sku=sku,
                name=name,
                category="monitor",
                price_inr=price,
                specs=specs,
                is_active=True,
                brand=base["brand"],
                product_family=base["name"],
                model=base["name"],
                variant_key=v_key,
                source_type="synthetic",
                source_reference="Procedural Benchmark Catalog",
                identity_verified=False,
                spec_verified=False,
                image_verified=False,
                price_verified=False,
                verification_status="unverified",
                confidence_level=0.50,
                spec_coverage=0.60,
                image_url=img_url,
                image_match_level="unverified",
                ingestion_status="recommendation_eligible"
            ))

        # D. Bulk insert in chunks of 5,000 for maximum database efficiency
        chunk_size = 5000
        logger.info(f"Bulk inserting {len(products)} products in chunks of {chunk_size}...")
        for k in range(0, len(products), chunk_size):
            chunk = products[k:k+chunk_size]
            session.add_all(chunk)
            await session.commit()
            logger.info(f"  Inserted chunk {k//chunk_size + 1}/{(len(products)-1)//chunk_size + 1}...")

        
        # Insert initial verified INR PriceObservations for all real seed products
        from app.models.price_observation import PriceObservation
        real_prods = [p for p in products if p.source_type == "real_seed"]
        logger.info(f"Seeding {len(real_prods)} verified INR price observations...")
        price_obs_list = []
        for p in real_prods:
            price_obs_list.append(PriceObservation(
                product_id=p.id,
                amount=float(p.price_inr),
                currency="INR",
                source="official_store",
                availability="in_stock"
            ))
        session.add_all(price_obs_list)
        await session.commit()

        logger.info(f"Successfully seeded database with procedurally expanded high-fidelity catalog containing {len(products)} products.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_database())
