import json
import os
from datetime import datetime


class DataLogger:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)

    def log_jsonl(self, filename, record):
        if not self.output_dir:
            return
        record = dict(record)
        record.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        path = os.path.join(self.output_dir, filename)
        with open(path, "a") as log_file:
            log_file.write(json.dumps(record, sort_keys=True) + "\n")

