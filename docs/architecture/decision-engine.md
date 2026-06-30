# Nexus — Decision Engine Mathematical Specification

This document defines the mathematical models, scoring algorithms, and multi-criteria decision analysis (MCDA) pipelines of the Nexus Decision Engine. It serves as the logical specification for database querying and reasoning calculation.

---

## 1. Decision Pipeline

The Decision Engine processes user inputs and catalog specifications through a deterministic 13-stage pipeline to generate a verdict without LLM reasoning drift:

```
[ User Input ] ──► [ Validation ] ──► [ Hard Constraints ] ──► [ Normalization ]
                                                                      │
                                                                      ▼
[ Scoring Engine ] ◄── [ Penalty/Bonus ] ◄── [ Weight Engine ] ◄── [ Soft Filters ]
        │
        ▼
[ Trade-off Engine ] ──► [ Ranking ] ──► [ Confidence ] ──► [ Evidence & Explanation ]
```

### Stage Explanations

1. **User Input Ingestion**: Receives priority weight sliders, categorical constraints, and exclusion choices.
2. **Validation**: Verifies formatting structure and checks that priority sliders are within the $[0, 5]$ bounds.
3. **Constraint Compilation**: Converts categorical requirements (e.g., "Max Price: $1500$") into database filters.
4. **Hard Filtering**: Queries the product database, eliminating any candidate option that fails a hard constraint (e.g., discarding products costing over $1500$).
5. **Normalization**: Scales the raw specification metrics of remaining candidates into a normalized range of $[0.0, 1.0]$.
6. **Soft Filtering**: Evaluates non-blocking user preferences (such as color or preferred brand) to determine adjustments.
7. **Weight Engine**: Normalizes user priority sliders into coefficients summing to $1.0$.
8. **Scoring Engine**: Computes the dot product of normalized specification vectors and normalized priority weights.
9. **Penalty & Bonus Processor**: Deducts points for minor preference failures (e.g. heavy weight) or adds bonuses for outstanding values.
10. **Trade-off Analysis**: Compares candidates pairwise to compile trade-offs (e.g., higher performance at the cost of higher weight).
11. **Ranking Engine**: Sorts candidates, runs tie-breaker algorithms, and outputs the top $N$ options.
12. **Confidence Engine**: Evaluates metadata completeness, specification reliability, and data age to calculate a matching confidence score.
13. **Evidence & Explanation Builder**: Collects source data (benchmarks, pricing tables) and formats the output for the AI justification layer.

---

## 2. Decision Variables

Every category has defined criteria variables. For the default Laptop category, we specify the following variables:

| Variable | Data Type | Value Range | Default Weight | Validation Rules | Default Value | Priority |
|---|---|---|---|---|---|---|
| **Budget** | Decimal | $[0.00, 10000.00]$ | Hard Filter | Must be $\ge 0$ | $1500.00$ | Critical |
| **Weight** | Decimal (kg) | $[0.50, 5.00]$ | Soft / Dynamic | Must be $\ge 0$ | $1.80$ | High |
| **RAM** | Integer (GB) | $[8, 128]$ | Hard Filter | Power of 2 | $16$ | High |
| **Battery Life** | Decimal (hrs) | $[2.0, 30.0]$ | Dynamic | Must be $\ge 0$ | $8.0$ | Medium |
| **CPU Performance** | Integer (Score) | $[0, 50000]$ | Dynamic | Benchmark range | $10000$ | High |
| **GPU Performance** | Integer (Score) | $[0, 40000]$ | Dynamic | Benchmark range | $2000$ | Medium |
| **Storage** | Integer (GB) | $[128, 8192]$ | Hard Filter | Power of 2 | $512$ | Medium |
| **Screen Size** | Decimal (in) | $[10.0, 20.0]$ | Soft Filter | Must be $\ge 0$ | $14.0$ | Medium |

---

## 3. Hard Constraints

Hard constraints are boolean filters evaluated directly on the database query layer (using SQL `WHERE` clauses) before any mathematical scoring takes place.

### Why Hard Constraints are Evaluated First

1. **Computational Efficiency**: Filtering out invalid candidates early reduces the active set from thousands of products to a handful of qualifying options, preventing redundant matrix multiplications.
2. **Cognitive Integrity**: If a user specifies a strict budget limit of $1200$, a $1300$ laptop must never be recommended—no matter how high its specifications are. Hard constraints prevent over-performing but disqualified products from skewing the normalized scoring scale.

---

## 4. Soft Constraints

Soft constraints are user preferences (e.g. "I prefer Apple", "I prefer Space Gray") that do not disqualify a product if unmet.

### Scoring Impact

Instead of filtering out candidates, soft constraints modify the base score:
* **Match Bonus**: Adds a flat bonus ($+0.05$ to $+0.10$) if the product meets a soft preference (e.g. is the preferred brand).
* **Mismatch Penalty**: Deducts points ($-0.05$ to $-0.10$) if the product conflicts with a preference (e.g. uses Windows when macOS is preferred).
This allows the engine to penalize but still evaluate a product if its other specifications are outstanding.

---

## 5. Weight Engine

The Weight Engine translates user priority inputs ($P_i \in [0, 5]$) into normalized weights ($W_i \in [0.0, 1.0]$):

### Weight Normalization Formula

Given $N$ active criteria, the normalized weight $W_i$ for criterion $i$ is calculated as:

$$W_i = \frac{P_i}{\sum_{j=1}^{N} P_j}$$

* **Edge Case (All Priorities set to Zero)**: If a user sets all sliders to $0$, the engine falls back to equal weights:

$$W_i = \frac{1}{N}$$

### Context-Aware Weight Balancing

The engine scales weights based on user profiles (DNA) and category requirements. For example, if a user profile indicates high sensitivity to weight, the engine adjusts the portability weight $W_{\text{portability}}$ using a scaling factor $\gamma \ge 1$:

$$W_{i,\text{adjusted}} = \frac{W_i \times \gamma_i}{\sum_{j=1}^{N} (W_j \times \gamma_j)}$$

---

## 6. Scoring Formula

We calculate a candidate's final score using Multi-Attribute Utility Theory (MAUT), adjusting for soft penalties and value bonuses:

### 1. Attribute Normalization

Before scoring, raw specification values $V_{pi}$ for product $p$ are normalized to a utility score $S_{pi} \in [0.0, 1.0]$:

* **Benefit Criteria (Larger is Better, e.g. Battery Life, RAM)**:

$$S_{pi} = \frac{V_{pi} - V_{i}^{\min}}{V_{i}^{\max} - V_{i}^{\min}}$$

* **Cost Criteria (Smaller is Better, e.g. Weight, Price)**:

$$S_{pi} = \frac{V_{i}^{\max} - V_{pi}}{V_{i}^{\max} - V_{i}^{\min}}$$

where $V_{i}^{\min}$ and $V_{i}^{\max}$ represent the boundary values for criterion $i$ within the active filtered product catalog.

### 2. Base Utility Score

The base utility score $\text{Score}_{\text{base}}(p)$ is computed as the dot product of the normalized weights and specifications vectors:

$$\text{Score}_{\text{base}}(p) = \sum_{i=1}^{N} W_i \times S_{pi}$$

### 3. Final Utility Score

The final utility score $\text{Score}_{\text{final}}(p)$ is computed by adjusting the base score for penalties and bonuses:

$$\text{Score}_{\text{final}}(p) = \text{Score}_{\text{base}}(p) - \sum_{k \in \text{Penalties}} P_k + \sum_{m \in \text{Bonuses}} B_m$$

where $P_k$ represents soft constraint penalties (e.g. brand mismatches) and $B_m$ represents value bonuses.

---

## 7. Trade-off Engine

When comparing the top candidates, the Trade-off Engine computes the specifications differences between the top-ranked options:

```
[ Product A (96%) ] ◄── Pairwise Spec Delta ──► [ Product B (92%) ]
         │                                              │
         ▼                                              ▼
  + CPU (+15%)                                   + Battery (+25%)
  + Storage (+512GB)                             + Lighter (-0.4kg)
  - Higher Price (+$250)                         - Cheaper (-$250)
```

For two products $A$ and $B$, the utility delta $\Delta_{A,B}(i)$ for criterion $i$ is:

$$\Delta_{A,B}(i) = S_{Ai} - S_{Bi}$$

* If $\Delta_{A,B}(i) > 0$, Product $A$ out-performs Product $B$ on criterion $i$.
* If $\Delta_{A,B}(i) < 0$, Product $B$ out-performs Product $A$ on criterion $i$.

These deltas are sorted by their magnitude to highlight the most significant trade-offs (e.g., "Product A offers 25% faster CPU, but is 0.4kg heavier and costs $250 more than Product B").

---

## 8. Confidence Engine

The Confidence Score $C(p) \in [0.0, 100.0]$ measures the reliability of the recommendation match using three metrics:

$$C(p) = 100 \times \left( \alpha \cdot D_p + \beta \cdot F_p + \gamma \cdot (1 - K_p) \right)$$

where the weights $\alpha$, $\beta$, and $\gamma$ sum to $1.0$ (default: $\alpha=0.4, \beta=0.3, \gamma=0.3$).

### Metric Variables

1. **Data Completeness ($D_p$)**: The ratio of completed specification keys to the total required parameters:
   $$D_p = \frac{N_{\text{filled}}(p)}{N_{\text{total\_specs}}}$$
2. **Data Freshness ($F_p$)**: An exponential decay function measuring the time elapsed since the product specs were last verified:
   $$F_p = e^{-\lambda \cdot t}$$
   where $t$ represents age in days and $\lambda$ is the decay rate (default: $\lambda = 0.005$, yielding a $95\%$ score after $10$ days).
3. **Conflict Index ($K_p$)**: Measures the severity of conflicting user choices (e.g. requesting both "Ultra Light Weight" and "Ultra Low Price", which are naturally conflicting):
   $$K_p = \frac{1}{2} \cdot \left| S_{p,\text{Weight}} - S_{p,\text{Price}} \right|$$

---

## 9. Evidence Engine

To prevent LLM hallucinations, every recommendation must be backed by verifiable data.

### Data Collection Flow
1. **Verification**: When evaluating a candidate, the engine fetches spec records from the `products` table.
2. **Source Linking**: Each specification value can be linked to a source record containing:
   - Manufacturer spec URLs.
   - Standard benchmark database IDs (e.g., Geekbench, 3DMark).
   - Retailer pricing API timestamps.
3. **Structured Context**: This verified data is passed to the AI justification layer, ensuring the generated explanation text refers strictly to verified specs.

---

## 10. Recommendation Ranking & Selection

### 1. Selection Paging
The top $N$ products are sorted by their final utility scores. The product with the highest score is selected as the recommended verdict.

### 2. Tie-Breaking Algorithm
If two products achieve identical scores, ties are resolved using the following order of priority:
1. **Price Utility**: The product with the lower price wins.
2. **Confidence Score**: The product with the higher confidence score wins.
3. **Spec Freshness**: The product with the more recently updated database record wins.

### 3. Diversity and Duplicate Removal
To present users with a diverse set of alternatives rather than minor configurations of the same product:
* If the top results contain multiple configurations of the same chassis model (e.g., a MacBook Air with 8GB RAM and a MacBook Air with 16GB RAM), the engine **keeps only the configuration with the highest utility score**.
* Lower-ranked duplicates are removed from the alternatives list, ensuring other brand alternatives are displayed.

---

## 11. Explainability Template

The AI justification engine outputs recommendation explanations using a structured format to maintain clarity and consistency:

```markdown
### Why [Product Name]?
- **Direct Match**: Directly matches your primary requirement for [Criterion A] (offering [Value A]).
- **Value Efficiency**: Achieves a score of [Utility Score] while costing [Price] (under your budget limit by [Delta]).

### What You Give Up (Trade-offs)
- **Portability**: Is [Weight Delta] heavier than [Alternative Product].
- **Battery**: Offers [Hours Delta] less runtime compared to the category average.

### Why Others Lost
- **[Competitor Product]**: Disqualified because its price ([Price]) exceeds your budget limit, or its RAM ([RAM]) falls below your requirement.
```

---

## 12. Failure Modes & Fallbacks

| Failure Scenario | Engine Detection | Fallback Behavior |
|---|---|---|
| **Impossible Constraints** | Zero products remain after hard filtering. | The engine relaxes the most restrictive soft filters (e.g., increasing budget by $10\%$), queries the database again, and warns the user which constraints were relaxed. |
| **Conflicting Answers** | Conflict index $K_p \ge 0.8$. | Generates a diagnostic warning in the API response, prompting the UI to show a "Requirements Conflict" help tooltip. |
| **Low Confidence** | Confidence score $C(p) < 60.0$. | The engine flags the recommendation as "Draft", and triggers a background web research task (via Tavily) to verify specifications. |

---

## 13. Future Machine Learning Extension Points

We reserve the following logical interfaces to integrate machine learning models for personalized recommendation tuning in later phases:

```python
from typing import Dict, List
from uuid import UUID

class IPreferenceLearner:
    """Interface to update user DNA profiles based on feedback loops."""
    
    async def update_dna_vector(self, user_id: UUID, selected_product_id: UUID, rejected_product_ids: List[UUID]) -> Dict[str, float]:
        """
        Adjusts DNA trait weights based on user purchase choices.
        Uses Reinforcement Learning (e.g. contextual bandits) to update coefficients.
        """
        raise NotImplementedError

class IWeightOptimizer:
    """Interface to optimize criteria weights based on historical usage patterns."""
    
    async def optimize_weights(self, category: str, historical_sessions: List[dict]) -> Dict[str, float]:
        """
        Runs gradient descent or covariance analysis on historical selections
        to predict weight coefficients for new users.
        """
        raise NotImplementedError
```

***

Approved by:
- **Lead System Architect**
- **Lead Data Scientist**
