import os
import shutil
import logging
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pyrogram import Client

# Render Logs-এ স্পষ্ট মেসেজ দেখার জন্য Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram Credentials
API_ID = int(os.getenv("API_ID", "32989580"))
API_HASH = os.getenv("API_HASH", "484e782c53527de90df7edb86d3a6b2b")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8859619385:AAF-q17-PWBvr-3fLPdyGQnv6R4PPxk9fvk")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004461200243"))

# in_memory=True দিলে Render-এ session file লক হয়ে সার্ভার ক্র্যাশ করবে না
bot = Client(
    "tg_cloud_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

app = FastAPI(title="Telegram Cloud Storage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    try:
        logger.info("Starting Telegram Bot...")
        await bot.start()
        logger.info("Bot started successfully!")
    except Exception as e:
        logger.error(f"Failed to start Telegram Bot: {e}")

@app.on_event("shutdown")
async def shutdown():
    try:
        await bot.stop()
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")

@app.get("/", response_class=HTMLResponse)
async def home():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html ফাইল পাওয়া যায়নি!</h1>"

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    os.makedirs("temp", exist_ok=True)
    file_path = os.path.join("temp", file.filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        msg = await bot.send_document(
            chat_id=CHANNEL_ID,
            document=file_path,
            caption=f"Uploaded: {file.filename}"
        )
        
        if os.path.exists(file_path):
            os.remove(file_path)
        
        base_url = str(request.base_url).rstrip("/")
        download_url = f"{base_url}/download/{msg.id}/{file.filename}"
        
        return {
            "status": "success",
            "file_name": file.filename,
            "message_id": msg.id,
            "download_url": download_url
        }
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{message_id}/{filename}")
async def download_file(message_id: int, filename: str):
    try:
        msg = await bot.get_messages(CHANNEL_ID, message_id)
        if not msg or not msg.media:
            raise HTTPException(status_code=404, detail="File not found")
        
        async def stream_generator():
            async for chunk in bot.stream_media(msg):
                yield chunk

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        return StreamingResponse(
            stream_generator(), 
            media_type="application/octet-stream",
            headers=headers
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
