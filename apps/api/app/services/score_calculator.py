from typing import Dict, Any
import re

class ScoreCalculator:
    """Computes category-specific suitability scores dynamically from raw specifications."""

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val = val.strip()
            try:
                return float(val)
            except ValueError:
                pass
            match = re.search(r'[-+]?\d*\.\d+|\d+', val)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    pass
        return default

    @staticmethod
    def calculate_all(category: str, specs: Dict[str, Any], price_inr: float) -> Dict[str, float]:
        """Calculates suitability scores for all personas based on the product category."""
        category_lower = category.lower()
        if category_lower == "laptop":
            return {
                "gaming_score": ScoreCalculator._laptop_gaming(specs),
                "programming_score": ScoreCalculator._laptop_programming(specs),
                "creator_score": ScoreCalculator._laptop_creator(specs),
                "business_score": ScoreCalculator._laptop_business(specs),
                "student_score": ScoreCalculator._laptop_student(specs, price_inr)
            }
        elif category_lower == "smartphone":
            return {
                "gaming_score": ScoreCalculator._phone_gaming(specs),
                "programming_score": ScoreCalculator._phone_programming(specs),
                "creator_score": ScoreCalculator._phone_creator(specs),
                "business_score": ScoreCalculator._phone_business(specs),
                "student_score": ScoreCalculator._phone_student(specs, price_inr)
            }
        elif category_lower == "monitor":
            return {
                "gaming_score": ScoreCalculator._monitor_gaming(specs),
                "programming_score": ScoreCalculator._monitor_programming(specs),
                "creator_score": ScoreCalculator._monitor_creator(specs),
                "business_score": ScoreCalculator._monitor_business(specs),
                "student_score": ScoreCalculator._monitor_student(specs, price_inr)
            }
        
        # Default fallback
        return {
            "gaming_score": 5.0,
            "programming_score": 5.0,
            "creator_score": 5.0,
            "business_score": 5.0,
            "student_score": 5.0
        }

    # ==========================================
    # LAPTOP FORMULAS
    # ==========================================

    @staticmethod
    def _laptop_gaming(specs: Dict[str, Any]) -> float:
        # 1. GPU Type
        gpu_type = specs.get("gpu_type", "integrated")
        gpu_type_val = 10.0 if gpu_type == "dedicated" else 2.0

        # 2. 3DMark Score (normalized out of 15000)
        gpu_3dmark = ScoreCalculator._safe_float(specs.get("gpu_score_3dmark", 1000))
        gpu_3dmark_val = min(10.0, (gpu_3dmark / 15000.0) * 10.0)

        # 3. Refresh Rate (60Hz = 3.0, 120Hz = 6.0, 144Hz = 8.0, 240Hz+ = 10.0)
        refresh = ScoreCalculator._safe_float(specs.get("refresh_rate_hz", 60))
        if refresh >= 240:
            refresh_val = 10.0
        elif refresh >= 144:
            refresh_val = 8.5
        elif refresh >= 120:
            refresh_val = 7.0
        else:
            refresh_val = 3.0

        # 4. Cooling Score
        cooling = ScoreCalculator._safe_float(specs.get("cooling_score", 5.0))

        # Weighting: 35% GPU Type, 35% 3DMark, 15% Refresh Rate, 15% Cooling
        score = (0.35 * gpu_type_val) + (0.35 * gpu_3dmark_val) + (0.15 * refresh_val) + (0.15 * cooling)
        return round(score, 1)

    @staticmethod
    def _laptop_programming(specs: Dict[str, Any]) -> float:
        # 1. CPU Multi-core (normalized out of 20000)
        multi_core = ScoreCalculator._safe_float(specs.get("cpu_multi_core", 5000))
        cpu_val = min(10.0, (multi_core / 20000.0) * 10.0)

        # 2. RAM (8GB = 4.0, 16GB = 7.5, 32GB = 9.5, 64GB = 10.0)
        ram = ScoreCalculator._safe_float(specs.get("ram_gb", 8))
        if ram >= 64:
            ram_val = 10.0
        elif ram >= 32:
            ram_val = 9.5
        elif ram >= 16:
            ram_val = 7.5
        else:
            ram_val = 4.0

        # 3. Linux Support / OS
        os = specs.get("operating_system", "Windows 11")
        linux_ok = specs.get("linux_supported", True)
        if "macOS" in os:
            os_val = 9.0  # macOS is highly rated, but not native Linux
        elif linux_ok:
            os_val = 10.0
        else:
            os_val = 7.0  # Windows 11 without good Linux support

        # 4. Storage speed / capacity (256GB = 4, 512GB = 7, 1TB+ = 10)
        storage = ScoreCalculator._safe_float(specs.get("storage_gb", 256))
        storage_val = 10.0 if storage >= 1024 else (7.0 if storage >= 512 else 4.0)

        # Weighting: 35% CPU, 30% RAM, 20% OS/Linux, 15% Storage
        score = (0.35 * cpu_val) + (0.30 * ram_val) + (0.20 * os_val) + (0.15 * storage_val)
        return round(score, 1)

    @staticmethod
    def _laptop_creator(specs: Dict[str, Any]) -> float:
        # 1. Color Accuracy Delta E (lower is better; <=1.0 = 10.0, >=4.0 = 1.0)
        delta_e = ScoreCalculator._safe_float(specs.get("color_accuracy_delta_e", 3.0))
        color_val = max(1.0, 10.0 - (delta_e * 2.0)) if delta_e <= 4.0 else 1.0

        # 2. Gamut coverage (DCI-P3 / AdobeRGB percentage)
        gamut = ScoreCalculator._safe_float(specs.get("dci_p3_coverage", specs.get("adobe_rgb_coverage", 70.0)))
        gamut_val = min(10.0, (gamut / 100.0) * 10.0)

        # 3. Display Brightness (normalized out of 600 nits)
        brightness = ScoreCalculator._safe_float(specs.get("brightness_nits", 250))
        brightness_val = min(10.0, (brightness / 600.0) * 10.0)

        # 4. Rendering power: CPU Multi-core (50%) & GPU 3DMark (50%)
        multi_core = ScoreCalculator._safe_float(specs.get("cpu_multi_core", 5000))
        cpu_val = min(10.0, (multi_core / 20000.0) * 10.0)
        gpu_3dmark = ScoreCalculator._safe_float(specs.get("gpu_score_3dmark", 1000))
        gpu_val = min(10.0, (gpu_3dmark / 15000.0) * 10.0)
        render_val = (0.5 * cpu_val) + (0.5 * gpu_val)

        # Weighting: 30% Color Accuracy, 25% Gamut, 15% Brightness, 30% Rendering Power
        score = (0.30 * color_val) + (0.25 * gamut_val) + (0.15 * brightness_val) + (0.30 * render_val)
        return round(score, 1)

    @staticmethod
    def _laptop_business(specs: Dict[str, Any]) -> float:
        # 1. Estimated Office Battery hours (normalized out of 18 hours)
        battery = ScoreCalculator._safe_float(specs.get("estimated_office_hours", 6.0))
        battery_val = min(10.0, (battery / 18.0) * 10.0)

        # 2. Weight (lower is better; <=1.0kg = 10.0, >=2.2kg = 2.0)
        weight = ScoreCalculator._safe_float(specs.get("weight_kg", 1.8))
        if weight <= 1.0:
            weight_val = 10.0
        elif weight >= 2.2:
            weight_val = 2.0
        else:
            weight_val = 10.0 - ((weight - 1.0) / 1.2) * 8.0

        # 3. Build Material & Quality
        build = ScoreCalculator._safe_float(specs.get("build_score", 7.0))

        # 4. Webcam resolution (1080p = 10, 720p = 5)
        webcam = specs.get("webcam", "720p")
        webcam_val = 10.0 if "1080" in webcam or "FHD" in webcam.upper() else 5.0

        # Weighting: 35% Battery, 35% Weight, 15% Build Quality, 15% Webcam
        score = (0.35 * battery_val) + (0.35 * weight_val) + (0.15 * build) + (0.15 * webcam_val)
        return round(score, 1)

    @staticmethod
    def _laptop_student(specs: Dict[str, Any], price_inr: float) -> float:
        # 1. Price Utility (lower price is better; <=$400 = 10.0, >=$1800 = 2.0)
        if price_inr <= 40000:
            price_val = 10.0
        elif price_inr >= 180000:
            price_val = 2.0
        else:
            price_val = 10.0 - ((price_inr - 40000) / 140000.0) * 8.0

        # 2. Battery Office hours (normalized out of 15 hours)
        battery = ScoreCalculator._safe_float(specs.get("estimated_office_hours", 6.0))
        battery_val = min(10.0, (battery / 15.0) * 10.0)

        # 3. Weight (lower is better; <=1.2kg = 10.0, >=2.2kg = 2.0)
        weight = ScoreCalculator._safe_float(specs.get("weight_kg", 1.8))
        if weight <= 1.2:
            weight_val = 10.0
        elif weight >= 2.2:
            weight_val = 2.0
        else:
            weight_val = 10.0 - ((weight - 1.2) / 1.0) * 8.0

        # Weighting: 45% Price, 30% Battery, 25% Weight
        score = (0.45 * price_val) + (0.30 * battery_val) + (0.25 * weight_val)
        return round(score, 1)

    # ==========================================
    # SMARTPHONE FORMULAS
    # ==========================================

    @staticmethod
    def _phone_gaming(specs: Dict[str, Any]) -> float:
        # 1. Processor Performance Score (normalized out of 11000)
        processor = ScoreCalculator._safe_float(specs.get("processor_score", 4000))
        cpu_val = min(10.0, (processor / 11000.0) * 10.0)

        # 2. RAM (4GB = 4, 6GB = 6, 8GB = 8, 12GB+ = 10)
        ram = ScoreCalculator._safe_float(specs.get("ram_gb", 6))
        ram_val = 10.0 if ram >= 12 else (8.0 if ram >= 8 else (6.0 if ram >= 6 else 4.0))

        # 3. Battery capacity (normalized out of 6000mAh)
        battery = ScoreCalculator._safe_float(specs.get("battery_mah", 3000))
        battery_val = min(10.0, (battery / 6000.0) * 10.0)

        # Weighting: 50% Processor, 25% RAM, 25% Battery
        score = (0.50 * cpu_val) + (0.25 * ram_val) + (0.25 * battery_val)
        return round(score, 1)

    @staticmethod
    def _phone_programming(specs: Dict[str, Any]) -> float:
        # Developers care about RAM and screen size for terminal reading
        ram = ScoreCalculator._safe_float(specs.get("ram_gb", 6))
        ram_val = 10.0 if ram >= 12 else (8.0 if ram >= 8 else 5.0)

        screen = ScoreCalculator._safe_float(specs.get("screen_size", 6.1))
        screen_val = min(10.0, ((screen - 5.5) / 1.5) * 10.0) if screen >= 5.5 else 4.0

        processor = ScoreCalculator._safe_float(specs.get("processor_score", 4000))
        cpu_val = min(10.0, (processor / 11000.0) * 10.0)

        # Weighting: 40% RAM, 30% Screen Size, 30% Processor
        score = (0.40 * ram_val) + (0.30 * screen_val) + (0.30 * cpu_val)
        return round(score, 1)

    @staticmethod
    def _phone_creator(specs: Dict[str, Any]) -> float:
        # Camera Megapixels (normalized out of 200MP)
        camera = ScoreCalculator._safe_float(specs.get("camera_mp", 12.0))
        camera_val = min(10.0, (camera / 200.0) * 10.0)
        # Capture raw sensor size bonus
        if camera >= 108.0:
            camera_val = max(camera_val, 9.5)

        # Storage capacity (64GB = 3, 128GB = 6, 256GB = 8, 512GB+ = 10)
        storage = ScoreCalculator._safe_float(specs.get("storage_gb", 128))
        storage_val = 10.0 if storage >= 512 else (8.0 if storage >= 256 else (6.0 if storage >= 128 else 3.0))

        # Processor power for video rendering
        processor = ScoreCalculator._safe_float(specs.get("processor_score", 4000))
        cpu_val = min(10.0, (processor / 11000.0) * 10.0)

        # Weighting: 50% Camera, 30% Storage, 20% Processor
        score = (0.50 * camera_val) + (0.30 * storage_val) + (0.20 * cpu_val)
        return round(score, 1)

    @staticmethod
    def _phone_business(specs: Dict[str, Any]) -> float:
        # Battery capacity (mAh)
        battery = ScoreCalculator._safe_float(specs.get("battery_mah", 3000))
        battery_val = min(10.0, (battery / 6000.0) * 10.0)

        # Storage capacity
        storage = ScoreCalculator._safe_float(specs.get("storage_gb", 128))
        storage_val = 10.0 if storage >= 256 else 7.0

        # Build Score
        build = ScoreCalculator._safe_float(specs.get("build_score", 7.0))

        # Weighting: 40% Battery, 30% Storage, 30% Build Quality
        score = (0.40 * battery_val) + (0.30 * storage_val) + (0.30 * build)
        return round(score, 1)

    @staticmethod
    def _phone_student(specs: Dict[str, Any], price_inr: float) -> float:
        # Price utility (lower is better; <=$200 = 10.0, >=$1200 = 2.0)
        if price_inr <= 20000:
            price_val = 10.0
        elif price_inr >= 120000:
            price_val = 2.0
        else:
            price_val = 10.0 - ((price_inr - 20000) / 100000.0) * 8.0

        # Battery capacity
        battery = ScoreCalculator._safe_float(specs.get("battery_mah", 3500))
        battery_val = min(10.0, (battery / 5500.0) * 10.0)

        # Weighting: 60% Price, 40% Battery
        score = (0.60 * price_val) + (0.40 * battery_val)
        return round(score, 1)

    # ==========================================
    # MONITOR FORMULAS
    # ==========================================

    @staticmethod
    def _monitor_gaming(specs: Dict[str, Any]) -> float:
        # Refresh rate (normalized out of 360Hz)
        refresh = ScoreCalculator._safe_float(specs.get("refresh_rate_hz", 60))
        refresh_val = min(10.0, (refresh / 360.0) * 10.0)
        if refresh >= 144:
            refresh_val = max(refresh_val, 8.0)

        # Response time (lower is better; <=0.1ms = 10.0, >=5.0ms = 2.0)
        response = ScoreCalculator._safe_float(specs.get("response_time_ms", 5.0))
        if response <= 0.1:
            response_val = 10.0
        elif response >= 5.0:
            response_val = 2.0
        else:
            response_val = 10.0 - ((response - 0.1) / 4.9) * 8.0

        # Curved/Aspect Ratio bonus
        gaming_suited = specs.get("gaming_suited", True)
        suit_val = 10.0 if gaming_suited else 5.0

        # Weighting: 40% Refresh Rate, 40% Response Time, 20% Gaming suitability
        score = (0.40 * refresh_val) + (0.40 * response_val) + (0.20 * suit_val)
        return round(score, 1)

    @staticmethod
    def _monitor_programming(specs: Dict[str, Any]) -> float:
        # Display resolution (1080p = 5.0, 1440p = 8.5, 2160p = 10.0)
        res = ScoreCalculator._safe_float(specs.get("resolution_p", 1080))
        res_val = 10.0 if res >= 2160 else (8.5 if res >= 1440 else 5.0)

        # Display size (inches) (24" = 5.0, 27" = 8.0, 32"+ = 10.0)
        size = ScoreCalculator._safe_float(specs.get("screen_size_inches", 24))
        size_val = 10.0 if size >= 32 else (8.0 if size >= 27 else 5.0)

        # Eye comfort score
        eye = ScoreCalculator._safe_float(specs.get("eye_comfort_score", 7.0))

        # Weighting: 40% Resolution, 40% Size, 20% Eye Comfort
        score = (0.40 * res_val) + (0.40 * size_val) + (0.20 * eye)
        return round(score, 1)

    @staticmethod
    def _monitor_creator(specs: Dict[str, Any]) -> float:
        # Color accuracy Delta E (lower is better; <=1.0 = 10.0, >=3.0 = 2.0)
        delta_e = ScoreCalculator._safe_float(specs.get("color_accuracy_delta_e", 3.0))
        color_val = max(2.0, 10.0 - (delta_e * 4.0)) if delta_e <= 3.0 else 2.0

        # Gamut coverage (AdobeRGB or DCI-P3)
        gamut = ScoreCalculator._safe_float(specs.get("adobe_rgb_coverage", specs.get("dci_p3_coverage", 70.0)))
        gamut_val = min(10.0, (gamut / 100.0) * 10.0)

        # Resolution
        res = ScoreCalculator._safe_float(specs.get("resolution_p", 1080))
        res_val = 10.0 if res >= 2160 else (8.0 if res >= 1440 else 4.0)

        # Panel Score
        panel = ScoreCalculator._safe_float(specs.get("panel_score", 7.0))

        # Weighting: 35% Color Accuracy, 25% Gamut, 20% Resolution, 20% Panel Quality
        score = (0.35 * color_val) + (0.25 * gamut_val) + (0.20 * res_val) + (0.20 * panel)
        return round(score, 1)

    @staticmethod
    def _monitor_business(specs: Dict[str, Any]) -> float:
        # Eye comfort is crucial
        eye = ScoreCalculator._safe_float(specs.get("eye_comfort_score", 7.0))

        # Connectivity options (USB-C support is a huge bonus)
        has_usbc = specs.get("ports", {}).get("usb_c", False)
        usbc_val = 10.0 if has_usbc else 5.0

        # Size
        size = ScoreCalculator._safe_float(specs.get("screen_size_inches", 24))
        size_val = 10.0 if size >= 27 else 6.0

        # Weighting: 40% Eye Comfort, 30% Connectivity, 30% Size
        score = (0.40 * eye) + (0.30 * usbc_val) + (0.30 * size_val)
        return round(score, 1)

    @staticmethod
    def _monitor_student(specs: Dict[str, Any], price_inr: float) -> float:
        # Price utility (lower is better; <=$150 = 10.0, >=$1000 = 2.0)
        if price_inr <= 15000:
            price_val = 10.0
        elif price_inr >= 100000:
            price_val = 2.0
        else:
            price_val = 10.0 - ((price_inr - 15000) / 85000.0) * 8.0

        # Size
        size = ScoreCalculator._safe_float(specs.get("screen_size_inches", 24))
        size_val = 10.0 if size >= 27 else 7.0

        # Weighting: 70% Price, 30% Size
        score = (0.70 * price_val) + (0.30 * size_val)
        return round(score, 1)
