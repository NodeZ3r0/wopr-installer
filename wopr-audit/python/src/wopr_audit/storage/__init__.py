from wopr_audit.storage.base import BaseStorage
from wopr_audit.storage.sqlite import SQLiteStorage

__all__ = ["BaseStorage", "SQLiteStorage"]

try:
    from wopr_audit.storage.postgres import PostgresStorage
    __all__.append("PostgresStorage")
except ImportError:
    pass

try:
    from wopr_audit.storage.json_file import JSONFileStorage
    __all__.append("JSONFileStorage")
except ImportError:
    pass
