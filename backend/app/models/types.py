"""Cross-compatible column types that work with both SQLite and PostgreSQL."""
import json
import uuid

from sqlalchemy import String, Text, TypeDecorator


class GUID(TypeDecorator):
    """UUID type that works with both SQLite (stored as string) and PostgreSQL."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return value


class JSONType(TypeDecorator):
    """JSON type that works with both SQLite (stored as text) and PostgreSQL (JSONB)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                return json.loads(value)
            return value
        return value
