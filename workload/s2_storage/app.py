# modeldepot/app.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
import os

app = FastAPI()
MODEL_DIR = os.getenv("MODEL_DIR", "./models")

os.makedirs(MODEL_DIR, exist_ok=True)


@app.get("/model/{name}")
async def get_model(name: str):
    path = os.path.join(MODEL_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Model not found")

    return FileResponse(path, filename=name, media_type="application/octet-stream")


@app.post("/upload")
async def upload_model(file: UploadFile = File(...)):
    dest_path = os.path.join(MODEL_DIR, file.filename)
    with open(dest_path, "wb") as f:
        contents = await file.read()
        f.write(contents)

    return {
        "message": f"Model '{file.filename}' uploaded successfully",
        "size_bytes": os.path.getsize(dest_path),
    }
