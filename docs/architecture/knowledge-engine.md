# Nexus — Knowledge Engine Architectural Specification

This document defines the production-grade architecture, ingestion pipelines, normalization systems, database schemas, and retrieval structures of the **Nexus Knowledge Engine**. The Knowledge Engine serves as the single source of truth for all product facts, configurations, pricing, and benchmark indices. It is responsible for supplying the Decision Engine with clean, high-fidelity datasets.

---

## 1. Knowledge Engine Overview

The **Knowledge Engine** isolates the complex, messy world of product web scrapers, unstructured data, retailer feeds, and inconsistent specifications from the deterministic, sub-millisecond evaluation logic of the **Decision Engine**.

```
[ INGESTION LAYER ]
 (Scrapers, Feeds, APIs)
        │
        ▼
[ PROCESSING PIPELINE ]
 (Validation ──► Normalization ──► Deduplication ──► Resolution ──► Standardization ──► Q-Scoring)
        │
        ▼
[ STORAGE & INDEXING ]
 (PostgreSQL JSONB/TSV ──► pgvector ──► Redis Cache)
        │
        ▼
[ SERVICE INTERFACE ] ◄───────────────────────────┐
 (Knowledge API Contracts)                       │
        │                                 [ CACHE INVALIDATION ]
        ▼                                        │
[ DECISION ENGINE ] ─────────────────────────────┘
 (Utility Evaluations)
```

### 1.1 Purpose
The purpose of the Knowledge Engine is to build, maintain, and expose a highly accurate, clean, structured, and constantly updated catalog of products and their physical specifications, performance benchmarks, and pricing parameters.

### 1.2 Responsibilities
* **Ingest**: Pull or receive raw product data from disparate sources (PDFs, HTML, APIs, XML feeds).
* **Normalize**: Standardize units (inches, cm, grams, lbs, Wh, mAh) into a canonical system.
* **Resolve**: Identify when two records from different sources represent the exact same physical product (Entity Resolution).
* **Standardize**: Map proprietary and inconsistent vendor nomenclature to canonical specification schemas.
* **Audit**: Assess the quality, completeness, and freshness of each product profile and assign a dynamic quality score ($Q$-score).
* **Serve**: Provide high-speed, query-optimized API interfaces supporting full-text, faceted, and hybrid vector searches.

### 1.3 Inputs
* Manufacturer spec sheets (HTML parsers, PDF extractors).
* Retailer product feeds (Amazon PA-API, eBay, Best Buy, Walmart APIs).
* Public datasets (Benchmark databases, open-source hardware directories).
* AI extraction queues (unstructured text parsed using LLMs).
* Manual curation (Admin portal overrides).

### 1.4 Outputs
* Validated canonical product profiles (PostgreSQL JSONB).
* Time-series price charts and availability indices.
* Benchmark profiles mapping hardware performance indices.
* Standardized API responses optimized for decision matrix scoring.

### 1.5 Boundaries with the Decision Engine
To maintain strict architectural separation, the boundary between the two engines is defined as follows:

| Attribute | Knowledge Engine | Decision Engine |
|---|---|---|
| **Domain** | Product Facts, Specs, Prices, and Quality. | User Preferences, Weights, and Utility Scoring. |
| **State** | Persistent database state of the physical world. | Transient user session state and decision criteria. |
| **Logic** | Data ingestion, unit conversion, deduplication. | Multi-Criteria Decision Analysis (MCDA), trade-off analysis. |
| **Computation** | Scheduled cron tasks, scrapers, vector indexing. | Real-time, dynamic mathematical recalculation on user input. |
| **Evaluation** | Validates if data is complete and self-consistent. | Evaluates if a product is "good" or "bad" *for a specific user*. |

---

## 2. Product Knowledge Model

We represent candidate product profiles using a relational schema mapped to JSONB validation layers. The following entity-relationship model defines the structure required for complete product intelligence:

```mermaid
erDiagram
    BRAND ||--oN PRODUCT : "manufactures"
    CATEGORY ||--oN PRODUCT : "classifies"
    PRODUCT ||--oN PRODUCT_SPECIFICATION : "holds"
    PRODUCT ||--oN PRODUCT_PRICE : "lists"
    PRODUCT ||--oN PRODUCT_IMAGE : "displays"
    PRODUCT ||--oN PRODUCT_REVIEW : "aggregates"
    PRODUCT ||--oN PRODUCT_BENCHMARK : "measures"
    PRODUCT ||--oN PRODUCT_COMPATIBILITY : "relates_to"
    PRODUCT ||--oN PRODUCT_ACCESSORY : "pairs_with"
    PRODUCT ||--oN PRODUCT_WARRANTY : "covers"
    PRODUCT ||--oN KNOWLEDGE_SOURCE : "cites"
    PRODUCT ||--oN PRODUCT_VERSION_HISTORY : "versions"
    RETAILER ||--oN PRODUCT_PRICE : "offers"

    PRODUCT {
        uuid id PK
        varchar sku UK "Unique internal SKU"
        varchar mpn "Manufacturer Part Number"
        varchar upc "Universal Product Code"
        varchar name "Standardized product name"
        uuid brand_id FK
        uuid category_id FK
        varchar status "active | discontinued | draft"
        float quality_score "Computed Q-score"
        jsonb canonical_specs "Validated canonical attributes"
        timestamptz created_at
        timestamptz updated_at
        integer version "Optimistic locking version counter"
    }

    BRAND {
        uuid id PK
        varchar name UK
        uuid parent_brand_id FK "For sub-brands (e.g. Alienware under Dell)"
        varchar logo_url
        varchar website
        float trust_rating "0.0 to 1.0 brand reliability weight"
    }

    CATEGORY {
        uuid id PK
        varchar name
        varchar slug UK
        uuid parent_id FK "Hierarchical taxonomy"
        jsonb spec_schema "JSON Schema validating canonical_specs for this category"
    }

    PRODUCT_PRICE {
        uuid id PK
        uuid product_id FK
        uuid retailer_id FK
        numeric price_usd "Current price in USD"
        numeric original_price "MSRP/List price"
        numeric discount_percent
        varchar product_url "Deep link to retailer page"
        boolean is_available "In-stock indicator"
        varchar stock_status "in_stock | out_of_stock | pre_order"
        timestamptz last_checked_at
    }

    RETAILER {
        uuid id PK
        varchar name UK
        varchar domain
        float trust_score "Retailer shipping/listing reliability"
        boolean api_partner "Direct API vs scraping fallback"
        boolean is_active
    }

    PRODUCT_IMAGE {
        uuid id PK
        uuid product_id FK
        varchar url
        integer width
        integer height
        varchar color_tag "E.g. space_gray, midnight"
        boolean is_primary
        integer sort_order
    }

    PRODUCT_REVIEW {
        uuid id PK
        uuid product_id FK
        varchar source_url
        varchar author
        float rating "Normalized rating scale"
        float max_rating "Standard base (e.g. 5 or 10)"
        varchar sentiment "positive | neutral | negative"
        text content "Raw review snippet"
        text summary "AI generated summary of the review"
        jsonb pros "Extracted pros tags"
        jsonb cons "Extracted cons tags"
        timestamptz reviewed_at
    }

    PRODUCT_BENCHMARK {
        uuid id PK
        uuid product_id FK
        varchar benchmark_name "E.g. Cinebench R23 Single, Geekbench 6 Multi"
        varchar category "cpu | gpu | storage"
        float score
        integer percentile
        varchar source_url
        timestamptz last_updated_at
    }

    PRODUCT_COMPATIBILITY {
        uuid id PK
        uuid product_a_id FK
        uuid product_b_id FK
        varchar compatibility_type "compatible | incompatible | adapter_required"
        text notes
    }

    PRODUCT_ACCESSORY {
        uuid id PK
        uuid product_id FK
        uuid accessory_product_id FK "Self-referencing relation"
        varchar relationship_type "essential | recommended | optional"
        integer sort_order
    }

    PRODUCT_WARRANTY {
        uuid id PK
        uuid product_id FK
        integer duration_months
        varchar warranty_type "manufacturer | retailer | extended"
        text coverage_details
        varchar country "ISO country code constraint"
    }

    KNOWLEDGE_SOURCE {
        uuid id PK
        uuid product_id FK
        varchar source_type "manufacturer_site | retailer_feed | public_db | scraper"
        varchar url
        float confidence_multiplier "Source reliability adjustment"
        jsonb raw_payload "Snapshot of raw data for audit"
        timestamptz scraped_at
    }

    PRODUCT_VERSION_HISTORY {
        uuid id PK
        uuid product_id FK
        varchar change_type "spec_update | price_change | status_change | merge"
        uuid changed_by FK "Curator UUID or System Agent ID"
        jsonb before_payload
        jsonb after_payload
        timestamptz created_at
    }
```

---

## 3. Data Sources & Ingestion

The Knowledge Engine pulls data from a variety of sources. Each source is assigned an immutable **Base Trust Level** ($T_{\text{source}} \in [0.0, 1.0]$) that determines how the system resolves conflicts when multiple sources report different values for the same specification.

| Data Source Type | Collection Mechanism | Base Trust ($T_{\text{source}}$) | Update Pattern | Target Specs |
|---|---|---|---|---|
| **Official Manufacturer Specs** | Automated crawling of spec sheets, PDF manuals, and press kits. | `1.00` | Triggers on product launch or major hardware revisions. | Physical dims, materials, display tech, battery capacity, ports, processor details. |
| **Manual Curator Overrides** | Administrative database entry via the Nexus backoffice portal. | `1.00` | Ad-hoc edits based on audit flags or customer feedback. | Corrections to conflicting spec fields, custom tagging, metadata fixes. |
| **Retailer APIs** | Direct API integration (Amazon PA-API, eBay, Best Buy, Walmart APIs). | `0.90` (Pricing)<br>`0.60` (Specs) | Hourly for pricing and availability; weekly for specs. | Real-time pricing, stock indicators, shipping costs, retailer promotional tags. |
| **Public Datasets** | Bulk ETL uploads from hardware benchmark sites (Geekbench, 3DMark, PassMark). | `0.90` | Weekly cron synchronization. | CPU performance indices, GPU frame rate scores, SSD IOPS measures. |
| **AI-Assisted Extraction** | Extraction from review sites (RTINGS, Tom's Hardware, YouTube reviews via transcription). | `0.70` | Weekly cron sweeps. | Real-world battery life, noise levels, heat dissipation profiles, qualitative pros/cons. |
| **Community Contributions** | Registered users submitting corrections (wiki-style editing model). | `0.50` (Requires Approval) | Real-time submissions; held in review queue. | Minor spec corrections, real-world quirks, compatibility confirmations. |

### 3.1 Conflict Resolution Algorithm
When two sources suggest different values for a specification parameter $P$, the system resolves the value using a trust-based priority selection. Let $V_i$ be the value reported by source $S_i$ with trust level $T_i$:

$$V_{\text{canonical}} = V_k \quad \text{where} \quad T_k = \max(T_i)$$

If two sources report conflicting data and $T_i = T_j$, the engine:
1. Keeps the existing database value if one of the sources matches it.
2. If both are new values, the engine flags the record with `needs_human_moderation = true`, suspends quality verification, and triggers an alert in the Curator dashboard.

---

## 4. Knowledge Processing Pipeline

Raw data moves through an asynchronous, distributed execution pipeline designed to guarantee data sanitization, schema alignment, and performance before storage. The pipeline runs as a series of Celery tasks backed by a RabbitMQ broker.

```
[ Raw JSON/HTML Ingestion ]
            │
            ▼
┌───────────────────────────┐
│  1. Schema Validation     │ ──► [Fail] ──► [ Dead Letter Queue ]
└───────────────────────────┘
            │ [Pass]
            ▼
┌───────────────────────────┐
│  2. Normalization         │ (Unicode normalization, unit conversions)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  3. Deduplication         │ (SKU / UPC / MPN matching)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  4. Entity Resolution     │ (Fuzzy matching, Jaro-Winkler string similarity)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  5. Spec Standardization  │ (Mapping keys to Category JSON Schemas)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  6. Quality Scoring       │ (Completeness, inconsistency checks)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  7. Transactional Storage  │ (PostgreSQL UPSERT & version log write)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  8. Search Indexing       │ (FTS tsvector compilation, pgvector sync)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  9. Redis Cache Sync      │ (Invalidation of listing keys, update hot cache)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  10. Search Serving       │ (Exposing results to client requests)
└───────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│  11. Recommendation Feed  │ (Passing dataset to Decision Engine context)
└───────────────────────────┘
```

### Stage Explanations

1. **Schema Validation**: Checks if the raw input conforms to the scraper's payload contract. Missing core identifier keys (e.g., brand, raw title, source URL) routes the payload directly to the Dead Letter Queue (DLQ).
2. **Normalization**: Sanitizes unicode representations (NFC standard), strips HTML tags, formats dates, and converts weights, dimensions, capacities, and frequencies into float-based base metrics (e.g. converting `3 lbs` to `1.36` and tracking unit `kg`).
3. **Deduplication**: Fast index matching. Queries existing PostgreSQL indexes for SKU, UPC, EAN, or MPN matches. If a match is found, the pipeline routes the payload into the update stream rather than the insertion stream.
4. **Entity Resolution**: For payloads lacking globally unique identifiers (like UPC), the engine executes fuzzy title matching (Jaro-Winkler with threshold $s \ge 0.88$) combined with model number extractions (e.g. matching `MacBook Air 13" 2024` with `Apple MBA 13 M3 8GB/256GB`).
5. **Specification Standardization**: Maps unstructured key-value specs into the target Category schema. For example, mapping `"Graphics card"`, `"GPU Interface"`, and `"Video Card"` into the standardized key `gpu_model`.
6. **Quality Scoring**: Executes the Data Quality check rules to evaluate data fidelity, calculating the record's initial $Q$-score.
7. **Transactional Storage**: Executes transactional updates inside PostgreSQL using optimistic concurrency control. An update checks the `version` column to prevent racing writes:
   ```sql
   UPDATE product SET canonical_specs = :new_specs, version = version + 1 WHERE id = :id AND version = :current_version;
   ```
8. **Search Indexing**: Compiles search terms into a combined `tsvector` column. Generates text embedding vectors (e.g. 768-dimensions) using the Gemini embedding API and updates the pgvector indices.
9. **Redis Cache Sync**: Dynamically invalidates cached queries that are sensitive to the updated product. Publishes a Redis pub/sub message to notify WebSocket handlers of changes to price/availability.
10. **Search Serving**: Exposes the updated index for full-text search queries.
11. **Recommendation Feed**: Flags the product profiles as available for the Decision Engine to pull for user evaluation sessions.

---

## 5. Canonical Specification System

To prevent different vendor nomenclatures from breaking scoring algorithms, the Knowledge Engine maintains strict canonical schema configurations per product category.

### 5.1 Canonical Schema Configurations (Laptop Category Example)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "LaptopCanonicalSpecs",
  "type": "object",
  "properties": {
    "cpu": {
      "type": "object",
      "properties": {
        "model_key": { "type": "string" },
        "cores": { "type": "integer" },
        "threads": { "type": "integer" },
        "base_clock_ghz": { "type": "number" },
        "boost_clock_ghz": { "type": "number" }
      },
      "required": ["model_key", "cores"]
    },
    "gpu": {
      "type": "object",
      "properties": {
        "model_key": { "type": "string" },
        "vram_gb": { "type": "integer" },
        "tgp_watts": { "type": "integer" }
      },
      "required": ["model_key"]
    },
    "ram": {
      "type": "object",
      "properties": {
        "capacity_gb": { "type": "integer" },
        "type": { "type": "string", "enum": ["ddr4", "ddr5", "lpddr5", "lpddr5x"] },
        "speed_mhz": { "type": "integer" }
      },
      "required": ["capacity_gb"]
    },
    "storage": {
      "type": "object",
      "properties": {
        "capacity_gb": { "type": "integer" },
        "type": { "type": "string", "enum": ["ssd_nvme", "ssd_sata", "hdd"] }
      },
      "required": ["capacity_gb", "type"]
    },
    "display": {
      "type": "object",
      "properties": {
        "size_inches": { "type": "number" },
        "width_pixels": { "type": "integer" },
        "height_pixels": { "type": "integer" },
        "refresh_rate_hz": { "type": "integer" },
        "panel_type": { "type": "string", "enum": ["ips", "oled", "mini_led", "tn"] },
        "brightness_nits": { "type": "integer" }
      },
      "required": ["size_inches", "width_pixels", "height_pixels"]
    },
    "battery": {
      "type": "object",
      "properties": {
        "capacity_wh": { "type": "number" },
        "cells": { "type": "integer" }
      },
      "required": ["capacity_wh"]
    },
    "weight_kg": { "type": "number" },
    "dimensions_mm": {
      "type": "object",
      "properties": {
        "width": { "type": "number" },
        "depth": { "type": "number" },
        "height": { "type": "number" }
      },
      "required": ["width", "depth", "height"]
    },
    "ports": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": { "type": "string", "enum": ["usb_a", "usb_c", "thunderbolt_4", "hdmi", "sd_reader", "audio_jack"] },
          "count": { "type": "integer" }
        },
        "required": ["type", "count"]
      }
    },
    "connectivity": {
      "type": "object",
      "properties": {
        "wifi_standard": { "type": "string", "enum": ["wifi_5", "wifi_6", "wifi_6e", "wifi_7"] },
        "bluetooth_version": { "type": "number" }
      }
    },
    "camera": {
      "type": "object",
      "properties": {
        "resolution_vertical": { "type": "integer" },
        "has_privacy_shutter": { "type": "boolean" }
      }
    },
    "operating_system": {
      "type": "string",
      "enum": ["windows_11_home", "windows_11_pro", "macos", "linux_ubuntu", "chrome_os", "no_os"]
    }
  }
}
```

### 5.2 Mapping Vendor Conventions
A series of deterministic Regex mappings and dictionary translation engines standardize incoming string inputs into the category's canonical variables:

```
[ Vendor String Input ] ──► [ Regex Matcher ] ──► [ Dict Translation ] ──► [ Schema Sanitizer ]
```

* **CPU Model Standardization**:
  * Vendor Input: `"Intel® Core™ i7-13700H Processor (24M Cache, up to 5.00 GHz)"`
  * Regex Matcher: `i7[- ]?13700[hH]`
  * Dictionary output: `intel_core_i7_13700h`
* **RAM Capacity Standardization**:
  * Vendor Input: `"16.0 GB (8.0 GB x 2) DDR5 Dual Channel"`
  * Parser: Matches digits immediately preceding `GB`, parses `16` directly.
* **Weight Unit Normalization**:
  * Vendor Input: `"Weight: 4.85 lbs"`
  * Parser: detects `lbs` -> multiplies value ($4.85 \times 0.45359237$) -> outputs `2.2` kg.

---

## 6. Search Architecture

The search system is a hybrid engine designed to process search parameters, structured database filters, dynamic counts, and semantic matches.

```
                  ┌──────────────────────┐
                  │  Search Request URL  │
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │ Query Parser Router  │
                  └──────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
┌──────────────────────┐            ┌──────────────────────┐
│ Lexical Query FTS    │            │ Semantic Embeddings  │
│ (PostgreSQL tsvector)│            │ (pgvector cosine)    │
└──────────────────────┘            └──────────────────────┘
            │                                   │
            └─────────────────┬─────────────────┘
                              ▼
                  ┌──────────────────────┐
                  │ Hybrid Fusion Ranker │ (RRF Formula Combine)
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │   Faceted Filter     │ (Price, RAM, Brand)
                  └──────────────────────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │     Final Output     │
                  └────────────────└─────┘
```

### 6.1 Full-Text Search (FTS)
The search queries a database-compiled `tsv_search` search vector column:
```sql
ALTER TABLE product ADD COLUMN tsv_search tsvector;
CREATE INDEX idx_product_tsv_search ON product USING gin(tsv_search);
```
The search vector joins the product name, brand name, category title, and canonical specifications text keys.

### 6.2 Structured Filters
Dynamic filtering uses B-tree indexes for structured scalar values and a GIN index for JSONB objects:
```sql
CREATE INDEX idx_product_specs_gin ON product USING gin(canonical_specs jsonb_path_ops);
```
This index speeds up operations matching keys, such as retrieving all laptops containing a specific processor brand:
```sql
SELECT * FROM product WHERE canonical_specs @> '{"cpu": {"model_key": "intel_core_i7_13700h"}}';
```

### 6.3 Hybrid Search
Hybrid search combines keyword matching scores with semantic vectors:
1. **Keyword Search**: Retrieves matching documents using `ts_rank_cd`.
2. **Semantic Search**: Searches vectors using Cosine Similarity metrics via pgvector.
3. **Combination**: Results are merged using **Reciprocal Rank Fusion (RRF)**:

$$\text{RRF Score}(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$

Where $M$ represents the search models (Lexical and Semantic), $r_m(d)$ is the rank position of document $d$ within model $m$, and $k$ is a constant ($60$).

### 6.4 Faceted Search
To generate search filters with matching counts (e.g. showing "Intel (12)" or "8GB RAM (5)"), the query performs dynamic aggregations over JSONB keys:
```sql
SELECT 
    canonical_specs->'ram'->>'capacity_gb' AS ram_capacity, 
    COUNT(*) as count
FROM product 
WHERE category_id = :category_id AND is_active = true
GROUP BY ram_capacity;
```

### 6.5 Ranking Function
The final search results are ranked using a multi-factor calculation weighting search relevance, product quality score, and product availability:

$$\text{SearchScore} = \text{RRFScore} \times (1.0 + \alpha \cdot \text{quality\_score}) \times (1.0 + \beta \cdot \text{is\_available})$$

* $\alpha = 0.40$ (Quality rating scale factor).
* $\beta = 0.20$ (Availability bias factor, giving a slight rank boost to in-stock products).

---

## 7. Data Quality Framework

Product profiles must pass through a strict auditing layer before being marked as clean and eligible for the Decision Engine.

### 7.1 Validation Rules

* **Missing Fields rule**:
  * Critical specifications (e.g., screen size, processor model) are mandatory. Missing variables block the record from moving out of `draft` status.
  * Standard specifications (e.g., camera resolution, weight) trigger warning audits.
* **Conflicting Specifications rule**:
  * The system performs logical cross-checks. E.g., if a system's battery capacity is marked as $99\text{Wh}$ but dimensions measure $14\text{mm} \times 8\text{mm} \times 2\text{mm}$, the system flags it as physically impossible.
  * Operating System and CPU cross-checks (e.g., an Apple M3 processor running Microsoft Windows 11).
* **Duplicate Products rule**:
  * Detects when different scrapers register matching MPNs or UPC values but assign slightly different titles.
* **Invalid Prices rule**:
  * Highlights items with a listing price $\le 0.0$.
  * Detects outlier values (e.g., a current price that deviates from the average historical price by more than $3\sigma$).
* **Outdated Records rule**:
  * Highlights product pricing logs that have not been checked in the past $48$ hours.
  * Highlights product specs that have not been verified in the past $60$ days.

### 7.2 Quality Score Formula
Every product record has a calculated Quality Score ($Q_{\text{product}} \in [0.0, 1.0]$) that penalizes data gaps and inconsistencies:

$$Q_{\text{product}} = 1.0 - \sum D_i$$

Where $D_i$ represents the penalty deduction values defined in the following table:

| Quality Rule Failure | Deduction ($D_i$) | Action Status |
|---|---|---|
| Missing critical spec parameter (e.g. CPU) | `0.40` | Drops product to `draft` (unsearchable). |
| Missing standard spec parameter (e.g. weight) | `0.10` | Remains active, logs audit warning. |
| Critical spec conflict (e.g. macOS on Intel M3) | `0.50` | Blocks entry, triggers Curator dashboard flag. |
| Price variance outlier ($>3\sigma$) | `0.30` | Suspends active price listing, triggers verification. |
| Outdated specs ($>60$ days since last check) | `0.15` | Triggers a scrape job with priority. |
| Outdated price ($>48$ hours since last check) | `0.10` | Adds price URL to the scraper queue. |

---

## 8. Product Versioning

Nexus maintains a complete history of product data changes to prevent data loss, enable historical comparisons, and support trend analysis.

```
[ Update Event ] ──► [ Diff Generator ] ──► [ Write audit_log ] ──► [ Update product record ]
```

### 8.1 Price History Logs
Price changes are written as append-only records to the `product_price_history` time-series table. Instead of updating the price in place, a trigger records historical rates:
```sql
CREATE TABLE product_price_history (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    product_id uuid NOT NULL,
    retailer_id uuid NOT NULL,
    price_usd numeric(12,2) NOT NULL,
    is_available boolean NOT NULL,
    recorded_at timestamptz DEFAULT clock_timestamp()
);
```

### 8.2 Specification Versioning
Updates to physical parameters are tracked using JSON diff logs (JSON Patch format, RFC 6902) in `product_spec_history`:
* Every specification change records the previous JSON snapshot, the updated JSON snapshot, and the ID of the user or script that made the change.
* Admins can view the changes and revert to previous versions if needed.

### 8.3 Lifecycle States & Discontinuation
Products migrate through three lifecycle states:

```
[ Draft ] ──(Specs Validation Pass)──► [ Active ] ──(End of Life Flag)──► [ Discontinued ]
```

* **Draft**: The product has been ingested but lacks core specifications or has failed schema validation checks. Draft products are excluded from user search and evaluation flows.
* **Active**: The product has a quality score $Q \ge 0.60$ and is currently sold or tracked.
* **Discontinued**: The product is no longer sold or manufactured. Discontinued products remain searchable but are excluded from active recommendation results unless the user explicitly enables a "Include Refurbished/Used Products" search toggle.

### 8.4 New Revisions
Products are linked through parent-child relations to model product generations (e.g. "Dell XPS 13 9315" is flagged as `replaced_by` -> "Dell XPS 13 9320"). This relationship helps the API suggest newer models to users who search for older or out-of-stock items.

---

## 9. Knowledge Refresh Strategy

To prevent data decay and minimize resource consumption, the system updates product records using a prioritized schedule.

### 9.1 Prioritized Refresh Schedule

```
  High Traffic / Active Sessions Product
  ├── Price Checked: Hourly
  └── Specs Verified: Every 7 Days

  Standard Catalog Product
  ├── Price Checked: Every 24 Hours
  └── Specs Verified: Every 30 Days

  Discontinued / Legacy Product
  ├── Price Checked: Every 30 Days
  └── Specs Verified: Every 90 Days
```

* **Priority Ingestion Queue (Tier 1)**: Products that are in active decision sessions or have been viewed by users in the last $48$ hours.
  * Price and availability checks: Checked hourly.
  * Specs and reviews: Verified every $7$ days.
* **Standard Catalog Queue (Tier 2)**: Products that are active but have low query rates.
  * Price and availability checks: Checked daily.
  * Specs and reviews: Verified every $30$ days.
* **Legacy Queue (Tier 3)**: Products flagged as discontinued.
  * Price checks: Checked monthly.
  * Specs verification: Checked every $90$ days.

### 9.2 Cache Invalidation Flow
When a product record is updated, the system invalidates the cache using a pub/sub pattern:
1. **Invalidate Product Cache**: The cache service deletes the key `cache:product:{product_id}`.
2. **Invalidate Search Results**: The cache service invalidates listing keys matching the product's category: `cache:search:{category_slug}:*`.
3. **Notify Clients**: Updates to price or stock are published to a Redis pub/sub channel. The web server forwards these updates to active user sessions via WebSockets.

---

## 10. AI Enrichment

For unstructured text parsing, Nexus schedules background enrichment jobs using the Gemini API.

```
                    ┌─────────────────────────┐
                    │  Raw Ingestion Payload  │
                    └─────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Gemini Extraction Prompt│ (Pydantic Schema Output)
                    └─────────────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
┌──────────────────────┐ ┌───────────────┐ ┌──────────────────────┐
│ Specs Inference      │ │ Sentiment     │ │ Pros & Cons          │
│ (Fill in blank nits) │ │ (Review scan) │ │ (Extract review data)│
└──────────────────────┘ └───────────────┘ └──────────────────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │ Standardized Ingestion  │
                    └─────────────────────────┘
```

### 10.1 Missing Specification Inference
When a product has missing fields, the system can infer them based on related specifications. E.g., if a processor model is known, the system can automatically infer its core count and integrated GPU type.

### 10.2 Feature Extraction
The enrichment pipeline extracts features from text descriptions (e.g. identifying terms like "Fingerprint reader", "Backlit Keyboard", or "Mux Switch") and maps them to boolean tags in the product record.

### 10.3 Product Summaries
Generates brief, bulleted summaries of product descriptions to display in search listings.

### 10.4 Review Summarization
Parses customer reviews and generates a summary that highlights key feedback points:
```
"Users praise the displays color accuracy and key travel but frequently report keyboard heating under high workloads."
```

### 10.5 Pros & Cons Extraction
Extracts structured lists of pros and cons, each annotated with a frequency indicator (e.g. `"noisy_fans": {"count": 18, "sentiment": -0.80}`).

### 10.6 Specification Comparison
Generates natural-language comparisons for product pages (e.g. `"The Asus G14 has 20% higher GPU performance than the Razer Blade 14, but runs roughly 5dB louder under load"`).

---

## 11. Knowledge API Contracts

The Decision Engine consumes the Knowledge Engine database through the following repository interfaces:

```python
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class SpecFilter(BaseModel):
    key: str
    operator: str  # "eq" | "gt" | "lt" | "contains"
    value: str

class ProductSearchRequest(BaseModel):
    category_slug: str
    query: Optional[str] = None
    filters: List[SpecFilter] = Field(default_factory=list)
    limit: int = 20
    offset: int = 0

class CanonicalProductResponse(BaseModel):
    id: UUID
    sku: str
    name: str
    brand: str
    category: str
    quality_score: float
    canonical_specs: Dict
    prices: List[Dict]
    images: List[Dict]

class PriceResponse(BaseModel):
    product_id: UUID
    retailer_name: str
    price_usd: float
    original_price: float
    is_available: bool
    product_url: str

class BenchmarkScore(BaseModel):
    benchmark_name: str
    category: str
    score: float
    percentile: int

class IProductKnowledgeProvider:
    """Interface exposed by the Knowledge Engine for internal consumption."""

    async def get_product(self, product_id: UUID) -> Optional[CanonicalProductResponse]:
        """Fetch a single normalized product record including current prices and metadata."""
        raise NotImplementedError

    async def search_products(self, request: ProductSearchRequest) -> List[CanonicalProductResponse]:
        """Execute full-text and structured filter searches on the product database."""
        raise NotImplementedError

    async def compare_products(self, product_ids: List[UUID]) -> List[CanonicalProductResponse]:
        """Fetch multiple product records side-by-side for comparison views."""
        raise NotImplementedError

    async def get_alternatives(
        self, product_id: UUID, target_features: List[str], limit: int = 5
    ) -> List[CanonicalProductResponse]:
        """Fetch similar products in the same category that match or improve on specific target features."""
        raise NotImplementedError

    async def get_similar_products(self, product_id: UUID, limit: int = 5) -> List[CanonicalProductResponse]:
        """Fetch similar products based on vector embedding similarity queries."""
        raise NotImplementedError

    async def get_latest_prices(self, product_id: UUID) -> List[PriceResponse]:
        """Fetch current prices and stock availability for a product across all retailers."""
        raise NotImplementedError

    async def get_benchmarks(self, product_id: UUID) -> List[BenchmarkScore]:
        """Fetch benchmark performance scores for a product's hardware components."""
        raise NotImplementedError
```

---

## 12. Global Scalability

To support a global catalog with millions of products across multiple countries, languages, and currencies, the Knowledge Engine adopts a decoupled architecture:

```
[ Ingestion Layer ] ──► [ Country Shard Router ] ──► [ Partitioned PostgreSQL DB ]
                                                             │
                                                             ▼
                                                    [ Dynamic Currency converter ]
                                                             │
                                                             ▼
                                                    [ Localization Lookup Service ]
```

### 12.1 Millions of Products
* **Database Partitioning**: PostgreSQL tables are partitioned by `category_id`. This keeps indexes small and search lookups fast as the database grows.
* **Write Buffering**: High-volume ingestion runs use a write-buffer pattern. Updates to pricing records are queued in Redis and flushed to PostgreSQL in batches every 5 seconds to reduce write lock contention.

### 12.2 Multi-Country Support
* Product pricing details are tracked in local tables, which dynamically adapt to different shipping rules, VAT rates, and import fees.

### 12.3 Multi-Currency
* Prices are stored in their native transaction currency (e.g. EUR, GBP, CAD) alongside their USD conversion.
* A daily task updates exchange rates in a central currency conversion table:
  $$\text{Price}_{\text{converted}} = \text{Price}_{\text{native}} \times \text{ExchangeRate}$$

### 12.4 Multi-Language
* Display fields (e.g. titles, feature summaries) are stored in translation tables or in a multi-lingual JSONB column structure:
  ```json
  "display_name": {
    "en": "Asus ROG Zephyrus G14",
    "de": "Asus ROG Zephyrus G14 Gaming Laptop"
  }
  ```
* Lexical search query parsers detect user locale and query the matching language index.

### 12.5 Multi-Retailer Integration
* Ingestion pipelines run in isolated Docker containers, allowing each retailer parser to scale independently.
* A **Retailer Adapter Pattern** standardizes raw scraping payloads into the pipeline's canonical schemas before the data reaches database layers.

---

## 13. Future Extensions

To support future platform capabilities, the database and API interfaces include the following extension points:

* **Vector Database migration**:
  * While initial vector lookups run in PostgreSQL using pgvector, the system is designed to migrate to a dedicated vector database (e.g., Qdrant or Milvus) by changing the vector provider configuration.
* **Knowledge Graphs**:
  * Relational tables (like `product_compatibility` and `product_accessories`) are designed to be exported to a graph database format (like Neo4j) to support complex compatibility queries (e.g. tracing multi-step component dependencies).
* **Retrieval-Augmented Generation (RAG)**:
  * The canonical specs and review summaries are formatted in a structured Markdown schema to make it easy to inject product data directly into LLM prompts.
* **Multi-Modal Embeddings**:
  * Extension points support generating unified vector embeddings that combine text data and product images.
* **Personalized Catalogs**:
  * Users will be able to submit custom products to their personal catalogs. These custom records are kept private to the user's workspace using row-level security (RLS) policies.
* **Community Consensus Moderation**:
  * A community validation queue will allow trusted users to review specification edits. Changes will go live once they receive a target threshold score from community reviews.

---

Approved by:
- **Lead System Architect**
- **Lead Data Engineer**
- **Principal AI Engineer**
