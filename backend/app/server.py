"""Production entry point; configuration is loaded fail-closed from environment."""

from backend.app.core.settings import Settings
from backend.app.main import create_app

app = create_app(Settings.from_environment())
