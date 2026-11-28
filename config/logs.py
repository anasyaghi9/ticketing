import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = dict(getattr(record, "fields", None) or {})
        data.update(  # core keys are written last, so fields can't overwrite them
            {
                "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


class PlainFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)
        fields = getattr(record, "fields", None)
        if fields:
            text += " " + " ".join(f"{key}={value}" for key, value in fields.items())
        return text
        