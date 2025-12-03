from fastapi import FastAPI, UploadFile, File, HTTPException
from starlette.responses import JSONResponse
import numpy as np
import soundfile as sf
import time
import io

app = FastAPI()

FRAME_DURATION_MS = 20  # frame size for short-time analysis
ENERGY_THRESHOLD = 0.01  # baseline energy threshold
ZCR_THRESHOLD = 0.1  # zero-crossing rate threshold


@app.post("/audio")
async def detect_presence(file: UploadFile = File(...)):
    try:
        start_time = time.time()
        data_bytes = await file.read()
        audio_file = io.BytesIO(data_bytes)

        signal, samplerate = sf.read(audio_file)
        if signal.ndim > 1:
            signal = signal.mean(axis=1)  # mono

        duration_sec = len(signal) / samplerate
        frame_size = int((FRAME_DURATION_MS / 1000) * samplerate)
        frame_stride = frame_size  # no overlap

        high_energy_frames = 0
        zcr_total = []
        energy_total = []

        for i in range(0, len(signal) - frame_size, frame_stride):
            frame = signal[i : i + frame_size]
            energy = np.sqrt(np.mean(np.square(frame)))
            zcr = ((frame[:-1] * frame[1:]) < 0).sum() / len(frame)

            energy_total.append(energy)
            zcr_total.append(zcr)

            if energy > ENERGY_THRESHOLD and zcr > ZCR_THRESHOLD:
                high_energy_frames += 1

        energy_avg = np.mean(energy_total)
        zcr_avg = np.mean(zcr_total)
        presence = str(high_energy_frames > 3)  # heuristic

        confidence = min(1.0, (high_energy_frames * frame_size / len(signal)))

        processing_time = time.time() - start_time

        return JSONResponse(
            {
                "presence": presence,
                "confidence": round(confidence, 2),
                "metrics": {
                    "input_length_seconds": round(duration_sec, 2),
                    "inference_duration_seconds": round(processing_time, 3),
                    "avg_energy": round(energy_avg, 6),
                    "avg_zcr": round(zcr_avg, 4),
                    "active_frames": high_energy_frames,
                    "frame_count": len(energy_total),
                },
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Audio processing failed: {str(e)}"
        )
