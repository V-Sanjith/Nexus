# Nexus — Database Architecture & Data Access Design

This document outlines the database design conventions, index tuning plans, transactional semantics, and concurrency strategies for the Nexus PostgreSQL database.

---

## 1. ER Diagram & Relationship Model

```mermaid
erDiagram
    USERS {
        uuid id PK
        varchar email UK
        varchar password_hash
        timestamptz created_at
        timestamptz updated_at
        boolean is_deleted
        timestamptz deleted_at
    }
    
    USER_PROFILES {
        uuid user_id PK, FK
        varchar first_name
        varchar last_name
        text avatar_url
        jsonb preferences
    }

    USER_DECISION_DNA {
        uuid user_id PK, FK
        jsonb traits
        timestamptz last_calculated
    }

    DECISIONS {
        uuid id PK
        uuid user_id FK
        varchar category
        varchar title
        varchar status
        int version "Optimistic Lock"
        boolean is_deleted
        timestamptz deleted_at
    }

    QUESTIONS {
        uuid id PK
        uuid decision_id FK
        int order_index
        text question_text
        varchar input_type
        jsonb options
    }

    ANSWERS {
        uuid id PK
        uuid decision_id FK
        uuid question_id FK
        jsonb selected_value
    }

    RECOMMENDATIONS {
        uuid id PK
        uuid decision_id FK, UK
        uuid verdict_product_id FK
        numeric confidence_score
        jsonb structured_analysis
        text explanation_md
    }

    PRODUCTS {
        uuid id PK
        varchar sku UK
        varchar name
        varchar category
        numeric price_usd
        jsonb specs
        boolean is_active
    }

    DECISION_MEMORY {
        uuid id PK
        uuid user_id FK
        varchar domain_key
        jsonb domain_value
        numeric confidence
    }

    COPI_CONVERSATIONS {
        uuid id PK
        uuid decision_id FK
        uuid user_id FK
        timestamptz created_at
    }

    COPI_MESSAGES {
        uuid id PK
        uuid conversation_id FK
        varchar sender
        text content
        jsonb meta
        timestamptz created_at
    }

    SHARE_LINKS {
        uuid id PK
        uuid decision_id FK
        varchar token UK
        timestamptz expires_at
        boolean is_active
    }

    AUDIT_LOGS {
        bigint id PK
        uuid user_id FK
        varchar event_type
        text description
        varchar ip_address
        jsonb payload
        timestamptz created_at
    }

    USERS ||--|| USER_PROFILES : "has"
    USERS ||--|| USER_DECISION_DNA : "has"
    USERS ||--oN DECISIONS : "creates"
    USERS ||--oN DECISION_MEMORY : "accumulates"
    DECISIONS ||--oN QUESTIONS : "has"
    DECISIONS ||--oN ANSWERS : "receives"
    DECISIONS ||--oN RECOMMENDATIONS : "generates"
    DECISIONS ||--oN COPI_CONVERSATIONS : "has"
    DECISIONS ||--oN SHARE_LINKS : "generates"
    COPI_CONVERSATIONS ||--oN COPI_MESSAGES : "contains"
    RECOMMENDATIONS ||--|| PRODUCTS : "verdict"
    AUDIT_LOGS ||--o| USERS : "logs"
```

---

## 2. Naming Conventions

We enforce strict PostgreSQL snake_case naming standards to ensure uniform queries:

* **Tables**: Plural snake_case (e.g., `users`, `audit_logs`).
* **Columns**: Singular snake_case (e.g., `created_at`, `password_hash`).
* **Primary Keys**: Named exactly `id`.
* **Foreign Keys**: Named `<singular_parent_table_name>_id` (e.g., `user_id`).
* **Constraints**:
  - Primary Key: `pk_<table_name>` (e.g., `pk_users`).
  - Foreign Key: `fk_<table_name>_<parent_table_name>` (e.g., `fk_decisions_users`).
  - Unique Key: `uq_<table_name>_<columns>` (e.g., `uq_users_email`).
  - Index: `idx_<table_name>_<columns>` (e.g., `idx_decisions_user_id`).

---

## 3. Storage & Indexing Strategy

To maintain sub-15ms database response times under heavy concurrent loads:

1. **Foreign Key Indexes**:
   - Every column carrying a Foreign Key constraint **must be indexed**. This prevents table scans during JOIN operations (e.g., indexing `user_id` on `decisions`).
2. **JSONB Spec Querying (GIN Indexes)**:
   - The `products` table stores dynamic specifications in a `specs` JSONB column. We apply a **GIN (Generalized Inverted Index)** on this column:
     ```sql
     CREATE INDEX idx_products_specs ON products USING gin (specs);
     ```
     This enables indexed lookup when filtering candidates (e.g. `specs ->> 'ram' = '16GB'`).
3. **Compound Range Indexes**:
   - Decisions queries commonly filter by user, status, and creation date. We define a composite B-Tree index:
     ```sql
     CREATE INDEX idx_decisions_user_status_date ON decisions (user_id, status, created_at DESC);
     ```

---

## 4. Constraint Rules & Cascades

* **On Delete Cascade**:
  - Applied strictly to dependent structures that cannot exist without their parent container.
  - Examples:
    - Deleting a `Decision` cascades deletions to `questions`, `answers`, and `recommendations`.
    - Deleting a `User` cascades deletions to `user_profiles` and `user_decision_dna`.
* **On Delete Restrict**:
  - Restricts deletions of reference data that must be protected.
  - Examples:
    - Attempting to delete a `Product` is restricted if it is referenced as a verdict in a `Recommendation`.
    - Deleting a `Question` is restricted if an `Answer` references it.

---

## 5. Transaction & Concurrency Management

* **Transaction Strategy**:
  - All write transactions utilize SQLAlchemy's async connection pool.
  - Reads are stateless. Write transactions utilize a **Unit of Work** lifecycle wrapper, ensuring database changes are atomically committed or completely rolled back if an error occurs.
* **Optimistic Locking**:
  - Prevents race conditions during simultaneous user inputs (e.g., user answers a question on two devices at once).
  - The `decisions` table includes a `version` integer column. Writes update the record using a matching version check:
    ```sql
    UPDATE decisions SET status = 'ANALYZING', version = version + 1 
    WHERE id = :id AND version = :current_version;
    ```
    If no rows are updated, SQLAlchemy raises a `StaleDataError` which is caught to abort the request.

---

## 6. Soft Delete Strategy

To preserve historical telemetry data and support compliance requests, the `users` and `decisions` tables implement Soft Delete patterns:

* **Columns**: `is_deleted: BOOLEAN` (Default: `false`) and `deleted_at: TIMESTAMPTZ` (Default: `null`).
* **Queries**: All normal SELECT statements include a filtering clause:
  ```sql
  WHERE is_deleted = FALSE
  ```
* **Uniqueness Constraints**:
  - Traditional unique indexes on soft-deleted columns (like `email`) block re-registration. We resolve this by creating conditional unique indexes:
    ```sql
    CREATE UNIQUE INDEX uq_users_active_email ON users (email) WHERE is_deleted = FALSE;
    ```
    This allows a deleted email address to be reused by a new user profile.

---

## 7. Performance Recommendations

1. **Connection Pooling**: Set connection pool size to $20$ with a maximum overflow limit of $10$ per runner node to protect DB limits.
2. **Prepared Queries**: Enable prepared statement caches inside `asyncpg` to bypass query plan compilation latency.
3. **Partitioning**: Partition `audit_logs` by date ranges to keep index structures small and hot in memory cache.
