from fastapi import FastAPI, UploadFile, File, HTTPException
import os, time, requests
import numpy as np
import cv2

app = FastAPI()

MODEL_DEPOT_URL = os.getenv(
    "MODEL_DEPOT_URL", "http://s2-modeldepot.default.svc.cluster.local"
)
TMP_MODEL_DIR = "/tmp"
SHARED_MODEL_PATH = os.getenv("SHARED_MODEL_DIR", "/mnt/shared-models")

MODEL_CFG = os.path.join(TMP_MODEL_DIR, "yolov4-tiny.cfg")
MODEL_WEIGHTS = os.path.join(TMP_MODEL_DIR, "yolov4-tiny.weights")
MODEL_CLASSES = os.path.join(TMP_MODEL_DIR, "coco.names")


def ensure_model_files():
    os.makedirs(TMP_MODEL_DIR, exist_ok=True)
    files = ["yolov4-tiny.cfg", "yolov4-tiny.weights", "coco.names"]

    total_download_size = 0  # total bytes fetched

    for file in files:
        local_path = os.path.join(TMP_MODEL_DIR, file)
        if os.path.isfile(local_path):
            continue

        pvc_path = os.path.join(SHARED_MODEL_PATH, file)
        if os.path.exists(pvc_path):
            with open(pvc_path, "rb") as src, open(local_path, "wb") as dst:
                data = src.read()
                total_download_size += len(data)
                dst.write(data)

        else:
            r = requests.get(f"{MODEL_DEPOT_URL}/model/{file}", stream=True)
            if r.status_code != 200:
                raise RuntimeError(f"Failed to fetch {file} from ModelDepot")
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        total_download_size += len(chunk)
                        f.write(chunk)

    return total_download_size


def get_net():
    net = cv2.dnn.readNetFromDarknet(MODEL_CFG, MODEL_WEIGHTS)
    layer_names = net.getLayerNames()

    # Force to 1D list of indices, whether flat or [[i]]
    out_layer_indices = net.getUnconnectedOutLayers().flatten().tolist()
    out_layers = [layer_names[i - 1] for i in out_layer_indices]

    return net, out_layers


def load_classes():
    with open(MODEL_CLASSES, "r") as f:
        return [line.strip() for line in f.readlines()]


@app.post("/infer")
async def infer(file: UploadFile = File(...)):
    try:
        start_total = time.time()
        download_size = ensure_model_files()
        fetch_duration = time.time() - start_total

        classes = load_classes()
        net, out_layers = get_net()

        image_np = np.frombuffer(await file.read(), np.uint8)
        image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image decode failed")

        start_infer = time.time()
        blob = cv2.dnn.blobFromImage(
            image, 0.00392, (416, 416), swapRB=True, crop=False
        )
        net.setInput(blob)
        detections = net.forward(out_layers)

        height, width = image.shape[:2]
        boxes, confidences, class_ids = [], [], []

        for output in detections:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > 0.5:
                    center_x, center_y, w, h = (
                        detection[0:4] * np.array([width, height, width, height])
                    ).astype("int")
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)
                    boxes.append([x, y, int(w), int(h)])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)

        infer_duration = time.time() - start_infer
        detected_classes = [classes[i] for i in class_ids] if class_ids else ["Unknown"]
        confidences = [float(c) for c in confidences]
        class_ids = [int(cid) for cid in class_ids]

        return {
            "result": {
                "detected_classes": detected_classes,
                "confidences": confidences,
                "class_ids": class_ids,
            },
            "metrics": {
                "model_fetch_latency_seconds": fetch_duration,
                "model_download_bytes": download_size,
                "inference_duration_seconds": infer_duration,
                "input_size_bytes": len(image_np),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
