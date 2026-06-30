from app.observability.logging import configure_logging
from app.observability.tracing import configure_tracing
from app.observability.error_reporting import configure_error_reporting

def configure_observability():
    configure_logging()
    configure_tracing()
    configure_error_reporting()
