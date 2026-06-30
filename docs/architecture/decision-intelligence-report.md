# Nexus Decision Intelligence Upgrade: Benchmark Scenarios Report

* **Total Scenarios Evaluated**: 9
* **Average Precision**: 100.0% (9/9 passed)
* **Average Evaluation Runtime**: 58.42 ms
* **Average Recommendation Confidence**: 23.3%

## Scenario Results Breakdown

| ID | Scenario Name | Target SKU | Result SKU | Target Status | Result Status | Precision | Confidence | Runtime (ms) |
|---|---|---|---|---|---|---|---|---|
| 1 | Student under INR 60,000 budget | `acer-aspire-5-8-512` | `acer-aspire-5-8-512` | `success` | `success` | ✅ PASS | 30.0% | 369.5 |
| 2 | Gaming laptop under INR 1,60,000 budget | `asus-g14-2024-16-1tb` | `asus-g14-2024-16-1tb` | `success` | `success` | ✅ PASS | 30.0% | 21.6 |
| 3 | Software Engineer (Developer) | `lenovo-x1-carbon-32-1tb` | `lenovo-x1-carbon-32-1tb` | `success` | `success` | ✅ PASS | 30.0% | 18.5 |
| 4 | MBA Student (Portability focus) | `apple-mba-m3-16-512` | `apple-mba-m3-16-512` | `success` | `success` | ✅ PASS | 30.0% | 19.6 |
| 5 | Video Editor (Heavy Creator) | `dell-xps-16-32-1tb` | `dell-xps-16-32-1tb` | `success` | `success` | ✅ PASS | 30.0% | 21.7 |
| 6 | Frequent Traveller | `['apple-mba-m3-16-512', 'lenovo-x1-carbon-32-1tb']` | `lenovo-x1-carbon-32-1tb` | `success` | `success` | ✅ PASS | 30.0% | 21.4 |
| 7 | Impossible constraints (High RAM, Low budget) | `None` | `None` | `no_match_found` | `no_match_found` | ✅ PASS | 0.0% | 15.6 |
| 8 | Conflicting requirements (Max gaming + Max portability) | `asus-g14-2024-16-1tb` | `asus-g14-2024-16-1tb` | `success` | `success` | ✅ PASS | 30.0% | 22.9 |
| 9 | Extremely low budget (No catalog matches) | `None` | `None` | `no_match_found` | `no_match_found` | ✅ PASS | 0.0% | 15.1 |