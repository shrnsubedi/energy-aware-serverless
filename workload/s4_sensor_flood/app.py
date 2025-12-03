from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from typing import List
from starlette.responses import Response
import pandas as pd
import requests
import time
import os

app = FastAPI()

CRUNCHER_URL = os.getenv(
    "CRUNCHER_URL", "http://s3-sensorcruncher.default.svc.cluster.local"
)


@app.post("/upload")
async def upload_csv(batch_size: int = Query(), file: UploadFile = File(...)):
    try:
        start_time = time.time()
        df = pd.read_csv(file.file)
        total_rows = len(df)
        batches_sent = 0

        total_request_bytes = 0
        total_response_bytes = 0

        for i in range(0, total_rows, batch_size):
            batch = df.iloc[i : i + batch_size].to_dict(orient="records")
            json_payload = str(batch).encode("utf-8")
            total_request_bytes += len(json_payload)

            res = requests.post(f"{CRUNCHER_URL}/process", json=batch, timeout=5)
            total_response_bytes += len(res.content)

            if res.status_code != 200:
                raise HTTPException(
                    status_code=502, detail="Failed to send batch to SensorCruncher"
                )
            batches_sent += 1

        duration = time.time() - start_time
        total_traffic_bytes = total_request_bytes + total_response_bytes

        return {
            "message": "Upload and dispatch complete",
            "metrics": {
                "batch_size": batch_size,
                "rows_total": total_rows,
                "batches_sent": batches_sent,
                "dispatch_duration_seconds": duration,
                "total_traffic_bytes": total_traffic_bytes,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")
