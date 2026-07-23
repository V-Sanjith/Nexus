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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 7.8,
                "known_pros": ["Excellent value for budget gaming", "Upgradeability for both RAM and SSD", "Sturdy hinge design"],
                "known_cons": ["Screen color accuracy and brightness are low", "Plastic chassis feels cheap"],
                "known_issues": ["Screen wobble when gaming under fan noise"],
                "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
                "base_price": 600.0,
                "configs": [
                    {"ram": 8, "storage": 512, "cpu": "AMD Ryzen 5 7640HS", "gpu": "RTX 4050", "refresh": 144, "price_adjust": -100.0},  # approx ₹41,500
                    {"ram": 16, "storage": 512, "cpu": "AMD Ryzen 5 7640HS", "gpu": "RTX 4050", "refresh": 144, "price_adjust": 0.0},     # approx ₹49,800 (< ₹50k!)
                    {"ram": 16, "storage": 1024, "cpu": "Intel Core i5-13420H", "gpu": "RTX 4050", "refresh": 144, "price_adjust": 100.0},  # approx ₹58,100 (₹50k-70k)
                    {"ram": 16, "storage": 1024, "cpu": "AMD Ryzen 7 7840HS", "gpu": "RTX 4060", "refresh": 144, "price_adjust": 250.0}   # approx ₹70,550 (₹70k-90k)
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 8.0,
                "known_pros": ["Very lightweight for a gaming laptop", "Dual M.2 SSD slots for expansion", "Highly competitive price"],
                "known_cons": ["Battery life is short under general use", "Quiet speakers"],
                "known_issues": ["Keyboard deck flexes slightly under heavy typing"],
                "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
                "base_price": 650.0,
                "configs": [
                    {"ram": 8, "storage": 512, "cpu": "Intel Core i5-13420H", "gpu": "RTX 4050", "refresh": 144, "price_adjust": 0.0},     # approx ₹63,700
                    {"ram": 16, "storage": 512, "cpu": "Intel Core i5-13420H", "gpu": "RTX 4050", "refresh": 144, "price_adjust": 50.0},    # approx ₹68,600
                    {"ram": 16, "storage": 1024, "cpu": "Intel Core i7-13620H", "gpu": "RTX 4060", "refresh": 144, "price_adjust": 200.0}   # approx ₹83,300
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 8.2,
                "known_pros": ["Superb 100% sRGB display at an affordable price", "Excellent keyboard layout with numpad", "Very stable gaming thermals"],
                "known_cons": ["Power brick is extremely heavy and bulky", "Chassis is thick plastic"],
                "known_issues": ["Battery drains slightly even when plugged in under extreme turbo load"],
                "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
                "base_price": 800.0,
                "configs": [
                    {"ram": 12, "storage": 512, "cpu": "Intel Core i5-13450HX", "gpu": "RTX 4050", "refresh": 144, "price_adjust": -80.0},  # approx ₹59,760 (₹50k-70k)
                    {"ram": 16, "storage": 512, "cpu": "Intel Core i5-13450HX", "gpu": "RTX 4060", "refresh": 144, "price_adjust": 50.0},   # approx ₹70,550 (₹70k-90k)
                    {"ram": 16, "storage": 1024, "cpu": "Intel Core i7-13700HX", "gpu": "RTX 4060", "refresh": 144, "price_adjust": 180.0}, # approx ₹81,340 (₹80k-100k)
                    {"ram": 24, "storage": 1024, "cpu": "AMD Ryzen 7 7840HX", "gpu": "RTX 4060", "refresh": 144, "price_adjust": 250.0}   # approx ₹87,150 (₹80k-100k)
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 8.5,
                "known_pros": ["Massive 90Wh battery offers top-class runtime", "Military-grade durable chassis", "Good keyboard with RGB backlighting"],
                "known_cons": ["Fans are loud under performance mode", "Screen has average viewing angles"],
                "known_issues": ["Wi-Fi card can sometimes disconnect under heavy network load"],
                "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
                "base_price": 950.0,
                "configs": [
                    {"ram": 16, "storage": 512, "cpu": "AMD Ryzen 5 7535HS", "gpu": "RTX 4050", "refresh": 144, "price_adjust": -100.0},  # approx ₹70,550 (₹70k-90k)
                    {"ram": 16, "storage": 1024, "cpu": "AMD Ryzen 7 7735HS", "gpu": "RTX 4060", "refresh": 144, "price_adjust": 50.0},   # approx ₹83,000 (₹80k-100k)
                    {"ram": 32, "storage": 1024, "cpu": "AMD Ryzen 7 7735HS", "gpu": "RTX 4060", "refresh": 144, "price_adjust": 200.0}   # approx ₹95,450 (₹90k-110k)
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
                "upgradeability": {"ram": False, "ssd": True},
                "repairability_score": 7.2,
                "known_pros": ["Stunning Nebula HDR OLED display", "Thin and lightweight aluminum chassis", "Excellent speakers and trackpad"],
                "known_cons": ["RAM is completely soldered and cannot be upgraded", "Chassis gets warm under heavy gaming"],
                "known_issues": ["Slight screen glare in bright outdoor environments"],
                "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
                "base_price": 1400.0,
                "configs": [
                    {"ram": 16, "storage": 512, "cpu": "AMD Ryzen 7 8840HS", "gpu": "RTX 4060", "refresh": 120, "price_adjust": -100.0},  # approx ₹107,900
                    {"ram": 16, "storage": 1024, "cpu": "AMD Ryzen 9 8945HS", "gpu": "RTX 4070", "refresh": 120, "price_adjust": 100.0},   # approx ₹147,000 (< 150k!)
                    {"ram": 32, "storage": 1024, "cpu": "AMD Ryzen 9 8945HS", "gpu": "RTX 4070", "refresh": 120, "price_adjust": 300.0},  # approx ₹141,100
                    {"ram": 32, "storage": 2048, "cpu": "AMD Ryzen 9 8945HS", "gpu": "RTX 4070", "refresh": 120, "price_adjust": 400.0}   # approx ₹149,400
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 7.5,
                "known_pros": ["Mini-LED display with extreme HDR brightness", "Unrivaled gaming frame rates (RTX 4080/4090)", "Tri-Fan cooling system prevents throttling"],
                "known_cons": ["Extremely heavy and thick chassis", "Very poor battery life under gaming"],
                "known_issues": ["Coil whine sometimes audible in silent environment under GPU transition"],
                "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
                "base_price": 2400.0,
                "configs": [
                    {"ram": 16, "storage": 1024, "cpu": "Intel Core i9-14900HX", "gpu": "RTX 4080", "refresh": 240, "price_adjust": -150.0}, # approx ₹186,750 (₹150k+!)
                    {"ram": 32, "storage": 1024, "cpu": "Intel Core i9-14900HX", "gpu": "RTX 4080", "refresh": 240, "price_adjust": 0.0},    # approx ₹199,200 (₹150k+!)
                    {"ram": 32, "storage": 2048, "cpu": "Intel Core i9-14900HX", "gpu": "RTX 4090", "refresh": 240, "price_adjust": 500.0},  # approx ₹240,700 (₹150k+!)
                    {"ram": 64, "storage": 2048, "cpu": "Intel Core i9-14900HX", "gpu": "RTX 4090", "refresh": 240, "price_adjust": 800.0}   # approx ₹265,600 (₹150k+!)
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 8.8,
                "known_pros": ["Excellent keyboard feedback and TrackPoint", "Strong entry-level durability and ports", "Upgradable memory slot"],
                "known_cons": ["Chassis has slightly thick screen bezels", "Speakers are average"],
                "known_issues": ["Trackpad clicks can feel stiff initially"],
                "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
                "base_price": 650.0,
                "configs": [
                    {"ram": 8, "storage": 256, "cpu": "AMD Ryzen 5 7530U", "gpu": "Integrated", "refresh": 60, "price_adjust": -100.0},  # approx ₹45,650
                    {"ram": 16, "storage": 512, "cpu": "AMD Ryzen 5 7530U", "gpu": "Integrated", "refresh": 60, "price_adjust": 0.0},     # approx ₹53,950 (< ₹60k!)
                    {"ram": 16, "storage": 512, "cpu": "AMD Ryzen 7 7730U", "gpu": "Integrated", "refresh": 60, "price_adjust": 80.0}      # approx ₹60,590
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 8.5,
                "known_pros": ["Highly repairable with dual SODIMM slots", "Lightweight aluminum deck", "Robust enterprise security"],
                "known_cons": ["Battery life is standard", "Display colors are a bit muted"],
                "known_issues": ["CPU fan cycles frequently under fast multitasking"],
                "image_url": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=500&q=80",
                "base_price": 700.0,
                "configs": [
                    {"ram": 8, "storage": 256, "cpu": "Intel Core i5-1335U", "gpu": "Integrated", "refresh": 60, "price_adjust": -100.0},  # approx ₹49,800
                    {"ram": 16, "storage": 512, "cpu": "Intel Core i5-1335U", "gpu": "Integrated", "refresh": 60, "price_adjust": 0.0},     # approx ₹58,100 (< ₹60k!)
                    {"ram": 16, "storage": 512, "cpu": "Intel Core i7-1355U", "gpu": "Integrated", "refresh": 60, "price_adjust": 100.0}     # approx ₹66,400
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
                "upgradeability": {"ram": False, "ssd": True},
                "repairability_score": 8.2,
                "known_pros": ["Extremely lightweight carbon fiber chassis", "Legendary comfortable business keyboard", "Superb security and TrackPoint"],
                "known_cons": ["Soldered memory cannot be upgraded", "High premium pricing"],
                "known_issues": ["Chassis collects fingerprint smudges easily"],
                "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
                "base_price": 1500.0,
                "configs": [
                    {"ram": 16, "storage": 512, "cpu": "Intel Core Ultra 7 155U", "gpu": "Integrated", "refresh": 60, "price_adjust": 0.0},    # approx ₹124,500
                    {"ram": 32, "storage": 1024, "cpu": "Intel Core Ultra 7 155U", "gpu": "Integrated", "refresh": 60, "price_adjust": 200.0}, # approx ₹141,100
                    {"ram": 64, "storage": 2048, "cpu": "Intel Core Ultra 7 155U", "gpu": "Integrated", "refresh": 60, "price_adjust": 500.0}  # approx ₹166,000
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
                "upgradeability": {"ram": False, "ssd": True},
                "repairability_score": 6.0,
                "known_pros": ["Gorgeous borderless InfinityEdge display", "Excellent rendering speed", "Large high-fidelity haptic trackpad"],
                "known_cons": ["Very heavy at 2.2kg", "Soldered RAM limits modifications"],
                "known_issues": ["Requires USB-C dongles for legacy ports"],
                "image_url": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=500&q=80",
                "base_price": 1800.0,
                "configs": [
                    {"ram": 16, "storage": 512, "cpu": "Intel Core Ultra 7 155H", "gpu": "RTX 4050", "refresh": 120, "price_adjust": 0.0},     # approx ₹149,400
                    {"ram": 32, "storage": 1024, "cpu": "Intel Core Ultra 9 185H", "gpu": "RTX 4060", "refresh": 120, "price_adjust": 300.0},  # approx ₹174,300
                    {"ram": 64, "storage": 2048, "cpu": "Intel Core Ultra 9 185H", "gpu": "RTX 4070", "refresh": 120, "price_adjust": 700.0}   # approx ₹207,500
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
                "upgradeability": {"ram": False, "ssd": False},
                "repairability_score": 5.0,
                "known_pros": ["Exceptional liquid retina XDR screen contrast", "Incredible battery runtime up to 22 hours", "Completely silent fans under compiler load"],
                "known_cons": ["Soldered storage and memory cannot be altered", "High premium cost entry barrier"],
                "known_issues": ["Slight screen ghosting during high-speed gaming tests"],
                "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
                "base_price": 2499.0,
                "configs": [
                    {"ram": 18, "storage": 512, "cpu": "Apple M3 Pro", "gpu": "M3 Pro", "refresh": 120, "price_adjust": 0.0},      # approx ₹207,417
                    {"ram": 36, "storage": 1024, "cpu": "Apple M3 Pro", "gpu": "M3 Pro", "refresh": 120, "price_adjust": 400.0},   # approx ₹240,617
                    {"ram": 48, "storage": 2048, "cpu": "Apple M3 Max", "gpu": "M3 Max", "refresh": 120, "price_adjust": 1000.0}   # approx ₹290,417
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
                "upgradeability": {"ram": False, "ssd": False},
                "repairability_score": 4.5,
                "known_pros": ["Completely silent fanless design", "Lightweight and portable aluminum body", "Outstanding battery runtime"],
                "known_cons": ["Soldered memory cannot be upgraded", "Supports only one external display natively"],
                "known_issues": ["Throttles slightly under continuous sustained multi-core compiler workloads"],
                "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
                "base_price": 999.0,
                "configs": [
                    {"ram": 8, "storage": 256, "cpu": "Apple M3", "gpu": "M3", "refresh": 60, "price_adjust": 0.0},      # approx ₹82,917
                    {"ram": 16, "storage": 512, "cpu": "Apple M3", "gpu": "M3", "refresh": 60, "price_adjust": 200.0},   # approx ₹99,517
                    {"ram": 24, "storage": 1024, "cpu": "Apple M3", "gpu": "M3", "refresh": 60, "price_adjust": 500.0}   # approx ₹124,417
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 7.8,
                "known_pros": ["Very affordable student pricing", "Dual upgradeable memory slots", "Compact chassis weight"],
                "known_cons": ["Average brightness limit nits", "Speakers lack bass depth"],
                "known_issues": ["Chassis flexes slightly under heavy hand pressure"],
                "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
                "base_price": 600.0,
                "configs": [
                    {"ram": 8, "storage": 256, "cpu": "Intel Core i5-1340P", "gpu": "Intel Graphics", "refresh": 90, "price_adjust": -50.0}, # approx ₹45,650
                    {"ram": 16, "storage": 512, "cpu": "Intel Core i5-1340P", "gpu": "Intel Graphics", "refresh": 90, "price_adjust": 50.0},  # approx ₹53,950
                    {"ram": 16, "storage": 1024, "cpu": "Intel Core i7-1360P", "gpu": "Intel Graphics", "refresh": 90, "price_adjust": 150.0} # approx ₹62,250
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
                "upgradeability": {"ram": True, "ssd": True},
                "repairability_score": 9.0,
                "known_pros": ["Pre-installed Ubuntu Linux with full hardware certification", "Excellent keyboard feedback", "Very modular design with high repairability"],
                "known_cons": ["Plastic build feels less premium than T-series", "Charging brick is basic"],
                "known_issues": ["Fingerprint reader requires proprietary driver on some distros"],
                "image_url": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=500&q=80",
                "base_price": 750.0,
                "configs": [
                    {"ram": 16, "storage": 512, "cpu": "AMD Ryzen 5 7535U", "gpu": "Radeon", "refresh": 60, "price_adjust": -50.0}, # approx ₹58,100
                    {"ram": 16, "storage": 512, "cpu": "AMD Ryzen 7 7735U", "gpu": "Radeon", "refresh": 60, "price_adjust": 50.0},  # approx ₹66,400
                    {"ram": 32, "storage": 1024, "cpu": "AMD Ryzen 7 7735U", "gpu": "Radeon", "refresh": 60, "price_adjust": 200.0} # approx ₹78,850
                ]
            }
        ]

        # =====================================================================
        # 2. SMARTPHONES DEFINITIONS (8 Realistic models)
        # =====================================================================
        base_smartphones = [
            {
                "name": "Samsung Galaxy S25 Ultra",
                "brand": "Samsung",
                "phone_type": "flagship",
                "manufacturer": "Samsung",
                "model_number": "SM-S938B",
                "build_score": 9.0,
                "known_pros": ["Phenomenal 200MP camera resolution and zoom", "Integrated S-Pen stylus with low lag", "Corning Gorilla Armor screen reduces reflection"],
                "known_cons": ["Extremely boxy corners feel uncomfortable", "Very expensive price entry barrier"],
                "known_issues": ["Haptic motor vibrates slightly weaker than previous models"],
                "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
                "base_price": 1299.0,
                "configs": [
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 8 Gen 4", "processor_score": 9200, "camera_mp": 200.0, "battery_mah": 5000, "screen_size": 6.8, "price_adjust": 0.0},    # approx ₹107,817
                    {"ram": 12, "storage": 512, "processor": "Snapdragon 8 Gen 4", "processor_score": 9200, "camera_mp": 200.0, "battery_mah": 5000, "screen_size": 6.8, "price_adjust": 100.0},  # approx ₹116,117
                    {"ram": 16, "storage": 1024, "processor": "Snapdragon 8 Gen 4", "processor_score": 9200, "camera_mp": 200.0, "battery_mah": 5000, "screen_size": 6.8, "price_adjust": 300.0} # approx ₹132,717
                ]
            },
            {
                "name": "Apple iPhone 16 Pro Max",
                "brand": "Apple",
                "phone_type": "flagship",
                "manufacturer": "Apple",
                "model_number": "A3296",
                "build_score": 9.2,
                "known_pros": ["Superb 4K video recording with Dolby Vision", "Unrivaled processor speed", "Exceptional titanium build aesthetics"],
                "known_cons": ["Charging limits to 27W maximum speed", "Very expensive flagship pricing"],
                "known_issues": ["Slight lens flares under direct streetlights at night"],
                "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
                "base_price": 1199.0,
                "configs": [
                    {"ram": 8, "storage": 256, "processor": "Apple A18 Pro", "processor_score": 10000, "camera_mp": 48.0, "battery_mah": 4685, "screen_size": 6.9, "price_adjust": 0.0},    # approx ₹99,517
                    {"ram": 8, "storage": 512, "processor": "Apple A18 Pro", "processor_score": 10000, "camera_mp": 48.0, "battery_mah": 4685, "screen_size": 6.9, "price_adjust": 200.0},  # approx ₹116,117
                    {"ram": 8, "storage": 1024, "processor": "Apple A18 Pro", "processor_score": 10000, "camera_mp": 48.0, "battery_mah": 4685, "screen_size": 6.9, "price_adjust": 400.0}  # approx ₹132,717
                ]
            },
            {
                "name": "OnePlus 13",
                "brand": "OnePlus",
                "phone_type": "gaming",
                "manufacturer": "OnePlus",
                "model_number": "CPH2609",
                "build_score": 8.5,
                "known_pros": ["Superb gaming frame rates and thermal vapor chamber", "Incredible 100W wired / 50W wireless charging", "Vast 6000mAh battery capacity"],
                "known_cons": ["Telephoto zoom lens is basic", "Alert slider gathers pocket lint easily"],
                "known_issues": ["Display switches aggressively between refresh rates under battery saver"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 799.0,
                "configs": [
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 8 Gen 4", "processor_score": 9600, "camera_mp": 50.0, "battery_mah": 6000, "screen_size": 6.82, "price_adjust": 0.0},    # approx ₹66,317
                    {"ram": 16, "storage": 512, "processor": "Snapdragon 8 Gen 4", "processor_score": 9600, "camera_mp": 50.0, "battery_mah": 6000, "screen_size": 6.82, "price_adjust": 100.0},  # approx ₹74,617
                    {"ram": 24, "storage": 1024, "processor": "Snapdragon 8 Gen 4", "processor_score": 9600, "camera_mp": 50.0, "battery_mah": 6000, "screen_size": 6.82, "price_adjust": 200.0} # approx ₹82,917
                ]
            },
            {
                "name": "Nothing Phone 2a",
                "brand": "Nothing",
                "phone_type": "budget",
                "manufacturer": "Nothing",
                "model_number": "A104",
                "build_score": 8.0,
                "known_pros": ["Distinctive transparent glyph back layout", "Completely clean operating system interface", "Long battery endurance screen"],
                "known_cons": ["Plastic back scratches very easily", "No wireless charging coil"],
                "known_issues": ["Glyph lights occasionally blink out of sync with ringtone presets"],
                "image_url": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80",
                "base_price": 349.0,
                "configs": [
                    {"ram": 8, "storage": 128, "processor": "Dimensity 7200 Pro", "processor_score": 7000, "camera_mp": 50.0, "battery_mah": 5000, "screen_size": 6.7, "price_adjust": -99.0},    # approx ₹24,500 (< ₹25k!)
                    {"ram": 8, "storage": 128, "processor": "Dimensity 7200 Pro", "processor_score": 7000, "camera_mp": 50.0, "battery_mah": 5000, "screen_size": 6.7, "price_adjust": 0.0},     # approx ₹34,202 (< ₹35k!)
                    {"ram": 12, "storage": 256, "processor": "Dimensity 7200 Pro", "processor_score": 7000, "camera_mp": 50.0, "battery_mah": 5000, "screen_size": 6.7, "price_adjust": 50.0}     # approx ₹39,102
                ]
            },
            {
                "name": "OnePlus Nord 4",
                "brand": "OnePlus",
                "phone_type": "budget",
                "manufacturer": "OnePlus",
                "model_number": "CPH2621",
                "build_score": 8.1,
                "known_pros": ["Premium metal unibody chassis design", "Exceptional 80W rapid charging speeds", "Bright 120Hz AMOLED panel"],
                "known_cons": ["Pre-installed bloatware apps", "Average low-light camera photos"],
                "known_issues": ["Metal back conducts heat quickly under gaming"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 285.70,
                "configs": [
                    {"ram": 8, "storage": 128, "processor": "Snapdragon 7+ Gen 3", "processor_score": 8200, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": -29.0}, # approx ₹34,300 (< ₹35k!)
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 7+ Gen 3", "processor_score": 8200, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": 20.0}   # approx ₹39,102
                ]
            },
            {
                "name": "Samsung Galaxy A55",
                "brand": "Samsung",
                "phone_type": "budget",
                "manufacturer": "Samsung",
                "model_number": "SM-A556B",
                "build_score": 8.2,
                "known_pros": ["Glass back build feels extremely premium", "MicroSD expansion storage slot", "Four years of guaranteed OS updates"],
                "known_cons": ["Thick bezels look dated", "Charging speeds are slow at 25W"],
                "known_issues": ["Virtual proximity sensor can fail occasionally during long calls"],
                "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
                "base_price": 449.0,
                "configs": [
                    {"ram": 8, "storage": 128, "processor": "Exynos 1480", "processor_score": 6800, "camera_mp": 50.0, "battery_mah": 5000, "screen_size": 6.6, "price_adjust": -100.0},   # approx ₹34,202 (< ₹35k!)
                    {"ram": 12, "storage": 256, "processor": "Exynos 1480", "processor_score": 6800, "camera_mp": 50.0, "battery_mah": 5000, "screen_size": 6.6, "price_adjust": 30.0}     # approx ₹46,942
                ]
            },
            {
                "name": "Apple iPhone SE 4",
                "brand": "Apple",
                "phone_type": "budget",
                "manufacturer": "Apple",
                "model_number": "A3112",
                "build_score": 7.8,
                "known_pros": ["Flagship Apple A18 performance chip", "Compact lightweight screen structure", "Long software update cycle"],
                "known_cons": ["Only one single rear camera lens", "Small battery capacity mAh limits play time"],
                "known_issues": ["Screen has thick borders compared to Android rivals"],
                "image_url": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&q=80",
                "base_price": 429.0,
                "configs": [
                    {"ram": 8, "storage": 128, "processor": "Apple A18", "processor_score": 8600, "camera_mp": 48.0, "battery_mah": 3279, "screen_size": 6.1, "price_adjust": 0.0},       # approx ₹35,607
                    {"ram": 8, "storage": 256, "processor": "Apple A18", "processor_score": 8600, "camera_mp": 48.0, "battery_mah": 3279, "screen_size": 6.1, "price_adjust": 100.0}      # approx ₹43,907
                ]
            },
            {
                "name": "Google Pixel 9 Pro",
                "brand": "Google",
                "phone_type": "photography",
                "manufacturer": "Google",
                "model_number": "G4S1M",
                "build_score": 8.8,
                "known_pros": ["Incredible AI camera image processing", "Beautiful symmetrical screen borders", "Seven years of updates support"],
                "known_cons": ["Tensor processor runs hot under 3D gaming tests", "Slow charging limits"],
                "known_issues": ["Fingerprint reader can fail under matte glass protectors"],
                "image_url": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=500&q=80",
                "base_price": 999.0,
                "configs": [
                    {"ram": 16, "storage": 128, "processor": "Tensor G4", "processor_score": 8800, "camera_mp": 50.0, "battery_mah": 5060, "screen_size": 6.3, "price_adjust": 0.0},       # approx ₹82,917
                    {"ram": 16, "storage": 256, "processor": "Tensor G4", "processor_score": 8800, "camera_mp": 50.0, "battery_mah": 5060, "screen_size": 6.3, "price_adjust": 100.0},     # approx ₹91,217
                    {"ram": 16, "storage": 512, "processor": "Tensor G4", "processor_score": 8800, "camera_mp": 50.0, "battery_mah": 5060, "screen_size": 6.3, "price_adjust": 250.0}     # approx ₹103,667
                ]
            },
            {
                "name": "OnePlus Nord 5",
                "brand": "OnePlus",
                "phone_type": "budget",
                "manufacturer": "OnePlus",
                "model_number": "CPH2715",
                "build_score": 8.3,
                "known_pros": ["Superb Snapdragon 8s Gen 3 performance", "Gorgeous 1.5K flat AMOLED display", "Extremely fast 100W charging"],
                "known_cons": ["Plastic frame feels less premium than Nord 4 metal", "No headphone jack"],
                "known_issues": ["Aggressive RAM management in background"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 336.70,
                "configs": [
                    {"ram": 8, "storage": 256, "processor": "Snapdragon 8s Gen 3", "processor_score": 8500, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": -20.0}, # approx ₹31,036
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 8s Gen 3", "processor_score": 8500, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": 0.0},  # approx ₹32,999
                    {"ram": 16, "storage": 512, "processor": "Snapdragon 8s Gen 3", "processor_score": 8500, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": 40.0}   # approx ₹36,919
                ]
            },
            {
                "name": "OnePlus Nord 6",
                "brand": "OnePlus",
                "phone_type": "budget",
                "manufacturer": "OnePlus",
                "model_number": "CPH2815",
                "build_score": 8.4,
                "known_pros": ["Superb Snapdragon 8s Gen 4 performance", "Gorgeous 1.5K flat AMOLED display", "Extremely fast 100W charging"],
                "known_cons": ["Plastic frame feels less premium than Nord 4 metal", "No headphone jack"],
                "known_issues": ["Aggressive RAM management in background"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 346.90,
                "configs": [
                    {"ram": 8, "storage": 256, "processor": "Snapdragon 8s Gen 4", "processor_score": 8700, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": -30.0}, # approx ₹31,056
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 8s Gen 4", "processor_score": 8700, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": 0.0},  # approx ₹33,999
                    {"ram": 16, "storage": 512, "processor": "Snapdragon 8s Gen 4", "processor_score": 8700, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.74, "price_adjust": 40.0}   # approx ₹37,919
                ]
            },
            {
                "name": "iQOO Neo 9 Pro",
                "brand": "iQOO",
                "phone_type": "gaming",
                "manufacturer": "iQOO",
                "model_number": "I2301",
                "build_score": 8.4,
                "known_pros": ["Flagship-grade Snapdragon 8 Gen 2 power", "Superb 144Hz gaming refresh rate", "Very fast 120W charging"],
                "known_cons": ["Funtouch OS has pre-installed apps", "Plastic frame design"],
                "known_issues": ["Slight warming near the camera module during extended gaming"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 357.10,
                "configs": [
                    {"ram": 8, "storage": 128, "processor": "Snapdragon 8 Gen 2", "processor_score": 8900, "camera_mp": 50.0, "battery_mah": 5160, "screen_size": 6.78, "price_adjust": -20.0}, # approx ₹33,035
                    {"ram": 8, "storage": 256, "processor": "Snapdragon 8 Gen 2", "processor_score": 8900, "camera_mp": 50.0, "battery_mah": 5160, "screen_size": 6.78, "price_adjust": 0.0},  # approx ₹34,999
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 8 Gen 2", "processor_score": 8900, "camera_mp": 50.0, "battery_mah": 5160, "screen_size": 6.78, "price_adjust": 30.0}  # approx ₹37,939
                ]
            },
            {
                "name": "Poco F6",
                "brand": "Poco",
                "phone_type": "gaming",
                "manufacturer": "Xiaomi",
                "model_number": "POCO-F6",
                "build_score": 8.2,
                "known_pros": ["Outstanding performance value Snapdragon 8s Gen 3", "Lighter weight and comfortable hold", "90W fast charging support"],
                "known_cons": ["Average battery longevity under gaming", "HyperOS has bloatware"],
                "known_issues": ["Slight thermal throttling under sustained heavy stress tests"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 306.10,
                "configs": [
                    {"ram": 8, "storage": 256, "processor": "Snapdragon 8s Gen 3", "processor_score": 8600, "camera_mp": 50.0, "battery_mah": 5000, "screen_size": 6.67, "price_adjust": 0.0},  # approx ₹29,997
                    {"ram": 12, "storage": 512, "processor": "Snapdragon 8s Gen 3", "processor_score": 8600, "camera_mp": 50.0, "battery_mah": 5000, "screen_size": 6.67, "price_adjust": 40.0}  # approx ₹33,917
                ]
            },
            {
                "name": "Realme GT 6T",
                "brand": "Realme",
                "phone_type": "gaming",
                "manufacturer": "Realme",
                "model_number": "GT-6T",
                "build_score": 8.3,
                "known_pros": ["Brightest 6000 nits LTPO AMOLED display", "Extremely long-lasting 5500mAh battery", "120W charging speed"],
                "known_cons": ["Camera setup lacks a telephoto lens", "Glossy back panel attracts fingerprints"],
                "known_issues": ["Auto-brightness can be slow to adjust in dim rooms"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 316.30,
                "configs": [
                    {"ram": 8, "storage": 128, "processor": "Snapdragon 7+ Gen 3", "processor_score": 8100, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.78, "price_adjust": -10.0}, # approx ₹29,997
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 7+ Gen 3", "processor_score": 8100, "camera_mp": 50.0, "battery_mah": 5500, "screen_size": 6.78, "price_adjust": 0.0}   # approx ₹30,997
                ]
            },
            {
                "name": "OnePlus 12",
                "brand": "OnePlus",
                "phone_type": "gaming",
                "manufacturer": "OnePlus",
                "model_number": "CPH2581",
                "build_score": 8.8,
                "known_pros": ["Stunning 2K 120Hz display screen", "Exceptional Snapdragon 8 Gen 3 performance", "Huge 5400mAh battery with 100W charging"],
                "known_cons": ["Large camera bump is heavy", "USB-C port alert slider collects dust"],
                "known_issues": ["Occasional refresh rate drop in heavy multitasking"],
                "image_url": "https://images.unsplash.com/photo-1565849904461-04a58ad377e0?w=500&q=80",
                "base_price": 539.0,
                "configs": [
                    {"ram": 12, "storage": 256, "processor": "Snapdragon 8 Gen 3", "processor_score": 9500, "camera_mp": 50.0, "battery_mah": 5400, "screen_size": 6.82, "price_adjust": 0.0},    # approx ₹52,822
                    {"ram": 16, "storage": 512, "processor": "Snapdragon 8 Gen 3", "processor_score": 9500, "camera_mp": 50.0, "battery_mah": 5400, "screen_size": 6.82, "price_adjust": 50.0}     # approx ₹57,722
                ]
            },
            {
                "name": "Samsung Galaxy S24",
                "brand": "Samsung",
                "phone_type": "flagship",
                "manufacturer": "Samsung",
                "model_number": "SM-S921B",
                "build_score": 8.7,
                "known_pros": ["Compact lightweight design with premium armor aluminum", "Seven years of OS update cycle", "Excellent dynamic AMOLED display color"],
                "known_cons": ["Exynos processor runs warmer than Snapdragon variants", "Slow charging limits to 25W"],
                "known_issues": ["Speaker grill can sound slightly tinny at high volumes"],
                "image_url": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500&q=80",
                "base_price": 549.0,
                "configs": [
                    {"ram": 8, "storage": 128, "processor": "Exynos 2400", "processor_score": 9100, "camera_mp": 50.0, "battery_mah": 4000, "screen_size": 6.2, "price_adjust": 0.0},      # approx ₹53,802
                    {"ram": 8, "storage": 256, "processor": "Exynos 2400", "processor_score": 9100, "camera_mp": 50.0, "battery_mah": 4000, "screen_size": 6.2, "price_adjust": 40.0}      # approx ₹57,722
                ]
            }
        ]

        # =====================================================================
        # 3. MONITORS DEFINITIONS (7 Realistic models)
        # =====================================================================
        base_monitors = [
            {
                "name": "AOC 24G2",
                "brand": "AOC",
                "monitor_type": "gaming",
                "build_score": 7.2,
                "known_pros": ["Exceptional value for budget gaming setup", "Fluid high refresh rate with stand height adjustment", "Vibrant colors on IPS screen"],
                "known_cons": ["1080p resolution has standard screen clarity", "Plastic frame feels light and budget"],
                "known_issues": ["Speakers are quiet and tinny"],
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "base_price": 180.0,
                "configs": [
                    {"size": 24.0, "res": 1080, "refresh": 144, "panel_score": 7.0, "color_accuracy_delta_e": 2.8, "response_time_ms": 1.0, "panel_type": "IPS", "price_adjust": 0.0},     # approx ₹14,940
                    {"size": 24.0, "res": 1080, "refresh": 165, "panel_score": 7.0, "color_accuracy_delta_e": 2.6, "response_time_ms": 1.0, "panel_type": "IPS", "price_adjust": 20.0}      # approx ₹16,600
                ]
            },
            {
                "name": "LG 27GP850-B UltraGear",
                "brand": "LG",
                "monitor_type": "gaming",
                "build_score": 8.0,
                "known_pros": ["Extremely fast pixel response time with zero blur", "G-Sync and FreeSync Premium verified", "Vibrant Nano IPS display colors"],
                "known_cons": ["Contrast ratio is low for dark room sessions", "Deep stand footprint takes up desk space"],
                "known_issues": ["Typical IPS glow visible in dark corners under dim room light"],
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "base_price": 350.0,
                "configs": [
                    {"size": 27.0, "res": 1440, "refresh": 165, "panel_score": 8.0, "color_accuracy_delta_e": 2.1, "response_time_ms": 1.0, "panel_type": "Nano IPS", "price_adjust": 0.0},  # approx ₹29,050
                    {"size": 27.0, "res": 1440, "refresh": 180, "panel_score": 8.0, "color_accuracy_delta_e": 2.0, "response_time_ms": 1.0, "panel_type": "Nano IPS", "price_adjust": 30.0}   # approx ₹31,540
                ]
            },
            {
                "name": "ASUS ProArt PA278QV",
                "brand": "ASUS",
                "monitor_type": "design",
                "build_score": 7.6,
                "known_pros": ["Calman Verified factory color calibration out of the box", "Ergonomic stand with full pivot height adjustment", "Affordable professional color display"],
                "known_cons": ["75Hz refresh rate is not suitable for high-speed esports", "No HDR support"],
                "known_issues": ["Integrated speakers sound very flat"],
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "base_price": 310.0,
                "configs": [
                    {"size": 27.0, "res": 1440, "refresh": 75, "panel_score": 7.5, "color_accuracy_delta_e": 1.0, "response_time_ms": 5.0, "panel_type": "IPS", "price_adjust": 0.0}       # approx ₹25,730
                ]
            },
            {
                "name": "BenQ PD2700Q",
                "brand": "BenQ",
                "monitor_type": "design",
                "build_score": 7.7,
                "known_pros": ["100% sRGB and Rec. 709 color gamut accuracy", "Dedicated CAD/CAM and Animation layout screen modes", "Dualview feature allows side-by-side mode review"],
                "known_cons": ["Thick traditional bezels look chunky", "Only 60Hz screen refresh rate"],
                "known_issues": ["Stand base is wide and heavy"],
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "base_price": 350.0,
                "configs": [
                    {"size": 27.0, "res": 1440, "refresh": 60, "panel_score": 7.6, "color_accuracy_delta_e": 1.1, "response_time_ms": 5.0, "panel_type": "IPS", "price_adjust": 0.0}       # approx ₹29,050
                ]
            },
            {
                "name": "Dell UltraSharp U2723QE",
                "brand": "Dell",
                "monitor_type": "design",
                "build_score": 8.5,
                "known_pros": ["IPS Black panel double contrast compared to standard IPS", "Rich USB-C hub connectivity with KVM", "Superb factory calibration setup"],
                "known_cons": ["Limited to 60Hz, not suited for competitive play", "Response time is average"],
                "known_issues": ["Stand pivot rotation can feel slightly stiff out of the box"],
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "base_price": 520.0,
                "configs": [
                    {"size": 27.0, "res": 2160, "refresh": 60, "panel_score": 8.5, "color_accuracy_delta_e": 0.8, "response_time_ms": 5.0, "panel_type": "IPS Black", "price_adjust": 0.0} # approx ₹43,160
                ]
            },
            {
                "name": "LG 27GR95QE UltraGear",
                "brand": "LG",
                "monitor_type": "gaming",
                "build_score": 9.2,
                "known_pros": ["Absolute infinite contrast and deep OLED blacks", "Instantaneous 0.03ms pixel response time", "High 240Hz screen refresh rate"],
                "known_cons": ["Matte anti-glare screen coating looks slightly grainy on white web pages", "OLED pixel layout can cause slight text color fringing"],
                "known_issues": ["ABL (Auto Brightness Limiter) dims display under full white windows"],
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "base_price": 900.0,
                "configs": [
                    {"size": 27.0, "res": 1440, "refresh": 240, "panel_score": 9.5, "color_accuracy_delta_e": 1.8, "response_time_ms": 0.03, "panel_type": "OLED", "price_adjust": 0.0}    # approx ₹74,700
                ]
            },
            {
                "name": "Samsung Odyssey G7",
                "brand": "Samsung",
                "monitor_type": "gaming",
                "build_score": 8.2,
                "known_pros": ["Aggressive 1000R curve offers extreme immersion", "240Hz refresh rate is lightning fast", "Deep blacks from high contrast VA panel"],
                "known_cons": ["Screen curve distorts straight lines in design apps", "Narrow viewing angles"],
                "known_issues": ["Scanlines visible under specific high contrast color grids"],
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "base_price": 550.0,
                "configs": [
                    {"size": 32.0, "res": 1440, "refresh": 240, "panel_score": 7.0, "color_accuracy_delta_e": 2.5, "response_time_ms": 1.0, "panel_type": "VA", "price_adjust": 0.0}       # approx ₹45,650
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

                sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{ram}-{stor}-{idx}"
                name = f"{base['name']} ({ram}GB RAM, {stor}GB SSD)"

                products.append(Product(
                    sku=sku,
                    name=name,
                    category="laptop",
                    price_inr=price,
                    specs=specs,
                    is_active=True
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

                sku = f"{base['brand'].lower()}-{base['name'].lower().replace(' ', '-')}-{ram}-{stor}-{idx}"
                name = f"{base['name']} ({ram}GB RAM, {stor}GB Storage)"

                products.append(Product(
                    sku=sku,
                    name=name,
                    category="smartphone",
                    price_inr=price,
                    specs=specs,
                    is_active=True
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

                products.append(Product(
                    sku=sku,
                    name=name,
                    category="monitor",
                    price_inr=price,
                    specs=specs,
                    is_active=True
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

            products.append(Product(
                sku=sku,
                name=name,
                category="laptop",
                price_inr=price,
                specs=specs,
                is_active=True
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

            products.append(Product(
                sku=sku,
                name=name,
                category="smartphone",
                price_inr=price,
                specs=specs,
                is_active=True
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

            products.append(Product(
                sku=sku,
                name=name,
                category="monitor",
                price_inr=price,
                specs=specs,
                is_active=True
            ))

        # D. Bulk insert in chunks of 5,000 for maximum database efficiency
        chunk_size = 5000
        logger.info(f"Bulk inserting {len(products)} products in chunks of {chunk_size}...")
        for k in range(0, len(products), chunk_size):
            chunk = products[k:k+chunk_size]
            session.add_all(chunk)
            await session.commit()
            logger.info(f"  Inserted chunk {k//chunk_size + 1}/{(len(products)-1)//chunk_size + 1}...")

        logger.info(f"Successfully seeded database with procedurally expanded high-fidelity catalog containing {len(products)} products.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_database())
