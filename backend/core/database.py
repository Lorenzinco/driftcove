from backend.db import Database
from backend.core.config import settings

db = Database(settings.db_path)