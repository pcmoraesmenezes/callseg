"""Log estruturado em JSON, uma linha por evento."""

import json
import logging


class JsonFormatter(logging.Formatter):
    """Formata cada registro como um objeto JSON, incluindo os campos passados em `extra={"fields": {...}}`."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        entry.update(getattr(record, "fields", {}))
        return json.dumps(entry, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    """Liga o log JSON no logger `segmenter` e devolve esse logger."""
    logger = logging.getLogger("segmenter")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
