from app.db import Database
from app.core.config import settings

db = Database(settings.db_path)