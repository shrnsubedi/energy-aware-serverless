from fastapi import FastAPI, Request, HTTPException
from typing import List, Dict
import time
import statistics

app = FastAPI()


@app.post("/process")
async def process_batch(request: Request):
    try:
        start = time.time()
        data: List[Dict] = await request.json()

        if not data:
            raise ValueError("Empty batch")

        temperatures = [row["temperature"] for row in data if "temperature" in row]
        humidities = [row["humidity"] for row in data if "humidity" in row]
        pressures = [row["pressure"] for row in data if "pressure" in row]

        stats = {
            "row_count": len(data),
            "temperature_avg": (
                round(statistics.mean(temperatures), 2) if temperatures else None
            ),
            "humidity_avg": (
                round(statistics.mean(humidities), 2) if humidities else None
            ),
            "pressure_avg": round(statistics.mean(pressures), 2) if pressures else None,
        }

        duration = time.time() - start

        return {
            "summary": stats,
            "metrics": {
                "batch_processing_seconds": duration,
                "rows_processed": len(data),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Processing failed: {str(e)}")
