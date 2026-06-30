import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from app.observability.config import obs_settings

def configure_error_reporting():
    if not obs_settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=obs_settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )
