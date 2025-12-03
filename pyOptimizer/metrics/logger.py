import csv
import os
from datetime import datetime


class ExperimentLogger:
    def log(self, rows: list[dict], filename: str = "experiment_log.csv"):
        header_written = os.path.exists(filename)
        write_header = not header_written
        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            if write_header:
                writer.writeheader()
                self.header_written = True
            writer.writerows(rows)
