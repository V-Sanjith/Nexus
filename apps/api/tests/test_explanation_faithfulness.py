from app.services.explanation_builder import ExplanationBuilder, ExplanationEvidence
from app.services.category_registry import CategoryRegistry

class MockProduct:
    def __init__(self, sku, name, price_inr, specs):
        self.sku = sku
        self.name = name
        self.price_inr = price_inr
        self.specs = specs

class MockScoreResult:
    def __init__(self, product, score, confidence_score):
        self.product = product
        self.score = score
        self.confidence_score = confidence_score
        self.raw_values = specs_to_raw(product.specs)
        self.normalized_values = {k: 0.8 for k in self.raw_values}

def specs_to_raw(specs):
    return {k: v for k, v in specs.items() if isinstance(v, (int, float))}

def test_explanation_faithfulness():
    registry = CategoryRegistry()
    config = registry.get("laptop")
    
    winner_prod = MockProduct(
        sku="WINNER-1",
        name="Lenovo Legion Slim 5",
        price_inr=95000,
        specs={
            "ram_gb": 16,
            "storage_gb": 512,
            "gpu_score": 9200,
            "cpu_score": 14500,
            "battery_hours": 7.5,
            "weight_kg": 2.1
        }
    )
    
    winner_res = MockScoreResult(winner_prod, 0.92, 92.0)
    
    trace = {
        "applied_persona": "gamer",
        "status": "success",
        "catalog_filtered_out": [],
        "rejections": {},
        "rejections_by_reason": {},
        "applied_constraints": {"price_max": 100000}
    }
    
    explanation = ExplanationBuilder.build(
        winner=winner_res,
        alternatives=[],
        tradeoffs=[],
        trace=trace,
        category_config=config,
        currency_symbol="₹"
    )
    
    assert "pros" in explanation
    assert len(explanation["pros"]) > 0
    assert "evidence" in explanation
    
    # Verify every evidence item is grounded
    for ev in explanation["evidence"]:
        assert "claim" in ev
        assert "direction" in ev
        assert ev["is_supported"] is True

    print("\n[EXPLANATION FAITHFULNESS TEST] Explanation claims grounded in evidence successfully!")

if __name__ == "__main__":
    test_explanation_faithfulness()
