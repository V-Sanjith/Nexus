from prometheus_client import Counter, Histogram

# HTTP Metrics
http_requests_total = Counter(
    "nexus_http_requests_total",
    "Total count of HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "nexus_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"]
)

# AI Metrics
llm_call_total = Counter(
    "nexus_llm_calls_total",
    "Total count of LLM generations",
    ["model", "status"]
)

llm_call_duration_seconds = Histogram(
    "nexus_llm_call_duration_seconds",
    "LLM API latency in seconds",
    ["model"]
)
