from fastapi import FastAPI
from app.google_image import router as google_image_router

app = FastAPI(title="Vertex Image Backend", version="4.2.0")
app.include_router(google_image_router)
