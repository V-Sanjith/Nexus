import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import yaml
from pydantic import BaseModel, Field
import structlog
from app.services.decision_engine import DecisionAttribute

logger = structlog.get_logger()

class SubcategoryConfig(BaseModel):
    keywords: List[str]
    default_persona: str

class AttributeConfig(BaseModel):
    key: str
    name: str
    type: str
    is_hard_filter: bool = False

class QuestionConfig(BaseModel):
    order_index: int
    question_text: str
    input_type: str
    options: Dict[str, Any]
    inr_options: Optional[Dict[str, Any]] = None
    maps_to: str

class DisplaySpecConfig(BaseModel):
    key: str
    label: str
    unit: Optional[str] = ""

class SimilarityKeysConfig(BaseModel):
    spec_keys: List[str]
    use_case_key: str

class TradeoffComparisonConfig(BaseModel):
    key: str
    name: str
    type: str
    unit: str
    precision: Optional[int] = None
    format_int: Optional[bool] = None

class FallbackConstraintConfig(BaseModel):
    tolerance: float
    weight: float

class FallbackConfig(BaseModel):
    max_results: int = 10
    constraints: Dict[str, FallbackConstraintConfig] = Field(default_factory=dict)

class CategoryConfig(BaseModel):
    category: str
    display_name: str
    description: str
    keywords: List[str]
    subcategories: Dict[str, SubcategoryConfig] = Field(default_factory=dict)
    attributes: List[AttributeConfig]
    personas: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    questions: List[QuestionConfig]
    display_specs: List[DisplaySpecConfig]
    similarity_keys: SimilarityKeysConfig
    tradeoff_comparisons: List[TradeoffComparisonConfig]
    fallback: Optional[FallbackConfig] = None
    
    # Subtype-specific merged configurations
    subtype: Optional[str] = None
    catalog_filters: Dict[str, Any] = Field(default_factory=dict)
    compatibility_rules: Dict[str, Any] = Field(default_factory=dict)

class SubtypeConfig(BaseModel):
    subtype: str
    category: str
    display_name: str
    description: Optional[str] = None
    default_persona: str
    catalog_filters: Dict[str, Any] = Field(default_factory=dict)
    questions: List[QuestionConfig]
    compatibility_rules: Dict[str, Any] = Field(default_factory=dict)
    fallback: Optional[FallbackConfig] = None
    
    # Overrides
    attributes: Optional[List[AttributeConfig]] = None
    personas: Optional[Dict[str, Dict[str, float]]] = None
    display_specs: Optional[List[DisplaySpecConfig]] = None
    tradeoff_comparisons: Optional[List[TradeoffComparisonConfig]] = None

class PersonaConfig(BaseModel):
    name: str
    weights: Dict[str, Dict[str, float]] = Field(default_factory=dict)

class CategoryRegistry:
    _instance: Optional['CategoryRegistry'] = None
    _configs: Dict[str, CategoryConfig] = {}
    _subtypes: Dict[str, SubtypeConfig] = {}
    _personas: Dict[str, PersonaConfig] = {}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CategoryRegistry, cls).__new__(cls, *args, **kwargs)
            cls._instance._load_all_configs()
        return cls._instance

    def _load_all_configs(self):
        current_dir = Path(__file__).resolve().parent
        configs_dir = current_dir.parent / "configs"
        
        logger.info("Scanning for configs", directory=str(configs_dir))
        
        # 1. Load Categories
        if configs_dir.exists():
            for file_path in configs_dir.glob("*.yaml"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if not data:
                            continue
                        config = CategoryConfig(**data)
                        self._configs[config.category.lower()] = config
                        logger.info("Loaded category config", category=config.category, file=file_path.name)
                except Exception as e:
                    logger.error("Failed to load category config", file=file_path.name, error=str(e))
        
        # 2. Load Subtypes
        subtypes_dir = configs_dir / "subtypes"
        if subtypes_dir.exists():
            for file_path in subtypes_dir.glob("*.yaml"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if not data:
                            continue
                        subtype_cfg = SubtypeConfig(**data)
                        key = f"{subtype_cfg.category.lower()}_{subtype_cfg.subtype.lower()}"
                        self._subtypes[key] = subtype_cfg
                        logger.info("Loaded subtype config", subtype=key, file=file_path.name)
                except Exception as e:
                    logger.error("Failed to load subtype config", file=file_path.name, error=str(e))
                    
        # 3. Load Personas
        personas_dir = configs_dir / "personas"
        if personas_dir.exists():
            for file_path in personas_dir.glob("*.yaml"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if not data:
                            continue
                        persona_cfg = PersonaConfig(**data)
                        self._personas[persona_cfg.name.lower()] = persona_cfg
                        logger.info("Loaded persona weight config", persona=persona_cfg.name)
                except Exception as e:
                    logger.error("Failed to load persona config", file=file_path.name, error=str(e))

    def get(self, category_key: str, subcategory_key: Optional[str] = None) -> Optional[CategoryConfig]:
        """
        Retrieves category config. If subcategory_key (subtype) is provided and a corresponding
        subtype YAML config exists, returns a merged composite CategoryConfig.
        """
        base = self._configs.get(category_key.lower())
        if not base:
            return None
            
        if not subcategory_key or subcategory_key.lower() == "general":
            return base

        # Try to find custom subtype config
        subtype_lookup = f"{category_key.lower()}_{subcategory_key.lower()}"
        subtype_cfg = self._subtypes.get(subtype_lookup)
        if not subtype_cfg:
            return base

        # Merge subtype overrides onto the base category configuration
        merged = CategoryConfig(
            category=base.category,
            display_name=subtype_cfg.display_name,
            description=subtype_cfg.description or base.description,
            keywords=base.keywords,
            subcategories=base.subcategories,
            attributes=subtype_cfg.attributes or base.attributes,
            # Merge personas dynamically: use subtype specific or merge from centralized persona registry
            personas=subtype_cfg.personas or base.personas,
            questions=subtype_cfg.questions,
            display_specs=subtype_cfg.display_specs or base.display_specs,
            similarity_keys=base.similarity_keys,
            tradeoff_comparisons=subtype_cfg.tradeoff_comparisons or base.tradeoff_comparisons,
            subtype=subtype_cfg.subtype,
            catalog_filters=subtype_cfg.catalog_filters,
            compatibility_rules=subtype_cfg.compatibility_rules,
            fallback=subtype_cfg.fallback or base.fallback
        )
        
        # Inject centralized persona weights if they exist for this persona
        persona_name = subtype_cfg.default_persona.lower()
        if persona_name in self._personas:
            p_config = self._personas[persona_name]
            weights = p_config.weights.get(category_key.lower(), {})
            if weights:
                # Merge into personas list for this default persona
                merged.personas[subtype_cfg.default_persona] = weights
                
        return merged

    def list_categories(self) -> List[dict]:
        return [
            {
                "key": config.category,
                "display_name": config.display_name,
                "description": config.description
            }
            for config in self._configs.values()
        ]

    def match_keywords(self, text: str) -> Optional[Tuple[str, str, str]]:
        """
        Scans all category and subcategory keywords in the text.
        Returns Tuple of (category, subcategory, default_persona) if a match is found.
        """
        text_lower = text.lower()
        
        best_category: Optional[CategoryConfig] = None
        for config in self._configs.values():
            for keyword in config.keywords:
                if keyword.lower() in text_lower:
                    best_category = config
                    break
            if best_category:
                break
        
        if not best_category:
            return None
        
        best_subcategory = "general"
        best_persona = "general"
        
        for sub_name, sub_config in best_category.subcategories.items():
            for kw in sub_config.keywords:
                if kw.lower() in text_lower:
                    best_subcategory = sub_name
                    best_persona = sub_config.default_persona
                    break
            if best_subcategory != "general":
                break
                
        return best_category.category, best_subcategory, best_persona

    def get_attributes(self, category: str, subcategory: Optional[str] = None) -> List[DecisionAttribute]:
        config = self.get(category, subcategory)
        if not config:
            return []
        return [
            DecisionAttribute(
                key=attr.key,
                name=attr.name,
                type=attr.type,
                is_hard_filter=attr.is_hard_filter
            )
            for attr in config.attributes
        ]

    def get_personas(self, category: str, subcategory: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        config = self.get(category, subcategory)
        if not config:
            return {}
        return config.personas

    def get_questions(self, category: str, subcategory: Optional[str] = None, currency: str = "usd") -> List[dict]:
        config = self.get(category, subcategory)
        if not config:
            return []
        
        questions_list = []
        is_inr = currency.lower() == "inr"
        
        for q in config.questions:
            options = q.options
            if is_inr and q.inr_options:
                options = q.inr_options
            
            questions_list.append({
                "order_index": q.order_index,
                "question_text": q.question_text,
                "input_type": q.input_type,
                "options": options,
                "maps_to": q.maps_to
            })
            
        return sorted(questions_list, key=lambda x: x["order_index"])

    def get_display_specs(self, category: str, subcategory: Optional[str] = None) -> List[dict]:
        config = self.get(category, subcategory)
        if not config:
            return []
        return [spec.model_dump() for spec in config.display_specs]

    def get_similarity_config(self, category: str, subcategory: Optional[str] = None) -> dict:
        config = self.get(category, subcategory)
        if not config:
            return {}
        return config.similarity_keys.model_dump()

    def get_tradeoff_config(self, category: str, subcategory: Optional[str] = None) -> List[dict]:
        config = self.get(category, subcategory)
        if not config:
            return []
        return [t.model_dump() for t in config.tradeoff_comparisons]
