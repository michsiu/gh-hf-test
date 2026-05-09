import os
import uuid
import time
import hmac
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse

STATIC_DIR = "/app/static"
DB_PATH = "/app/data/files.db"
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
SECRET = os.environ.get("SECRET_KEY", "immic")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs("/app/data", exist_ok=True)

# ========== 数据库 ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            filename TEXT,
            original_name TEXT,
            size INTEGER,
            upload_time TEXT,
            expire_time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ========== 清理过期 ==========
def clean_old_files():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, filename FROM files WHERE expire_time < ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
    )
    expired = cursor.fetchall()
    for file_id, filename in expired:
        filepath = os.path.join(STATIC_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        conn.execute("DELETE FROM files WHERE id=?", (file_id,))
    conn.commit()
    conn.close()
    if expired:
        print(f"已清理 {len(expired)} 个过期文件")
    threading.Timer(3600, clean_old_files).start()

clean_old_files()

# ========== FastAPI ==========
app = FastAPI(title="临时文件中转站")

# ========== 签名 ==========
def generate_sign(file_id, expires):
    message = f"{file_id}:{expires}"
    return hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()[:16]

def verify_sign(file_id, expires, signature):
    expected = generate_sign(file_id, expires)
    if not hmac.compare_digest(signature, expected):
        return False, "签名无效"
    if int(expires) < int(time.time()):
        return False, "链接已过期"
    return True, "ok"

# ========== 页面 ==========
@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(TEMPLATE_DIR, "index.html"), encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# ========== 上传 ==========
@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    ttl: int = Query(default=86400, description="有效期秒数，默认24小时")
):
    file_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    new_name = f"{file_id}{ext}"
    new_path = os.path.join(STATIC_DIR, new_name)
    size = 0

    with open(new_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
            size += len(chunk)

    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    expire_time = (datetime.now() + timedelta(seconds=ttl)).strftime("%Y-%m-%d %H:%M:%S")
    expires_ts = int(time.time()) + ttl
    signature = generate_sign(file_id, expires_ts)

    # 动态获取 Space URL
    space_host = os.environ.get("SPACE_HOST", "micsir-tmpfiles.hf.space")
    url = f"https://{space_host}/dl/{file_id}?expires={expires_ts}&sign={signature}"

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO files VALUES (?,?,?,?,?,?)",
        (file_id, new_name, file.filename, size, upload_time, expire_time)
    )
    conn.commit()
    conn.close()

    return JSONResponse(status_code=200, content={
        "code": 200,
        "message": "上传成功",
        "data": {
            "file_id": file_id,
            "filename": file.filename,
            "size": size,
            "url": url,
            "upload_time": upload_time,
            "expire_time": expire_time,
            "ttl_seconds": ttl
        }
    })

# ========== 下载 ==========
@app.get("/dl/{file_id}")
async def download(file_id: str, expires: str = Query(...), sign: str = Query(...)):
    valid, msg = verify_sign(file_id, expires, sign)
    if not valid:
        raise HTTPException(status_code=403, detail=msg)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT filename FROM files WHERE id=?", (file_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    filepath = os.path.join(STATIC_DIR, row[0])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件已被清理")

    return FileResponse(filepath)

# ========== 查询 ==========
@app.get("/query/{file_id}")
async def query(file_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM files WHERE id=?", (file_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return JSONResponse(status_code=404, content={"code": 404, "message": "文件不存在或已过期"})

    expires_ts = int(time.time()) + 86400
    signature = generate_sign(file_id, expires_ts)
    space_host = os.environ.get("SPACE_HOST", "micsir-tmpfiles.hf.space")
    url = f"https://{space_host}/dl/{file_id}?expires={expires_ts}&sign={signature}"

    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": {
            "file_id": row[0],
            "original_name": row[2],
            "size": row[3],
            "upload_time": row[4],
            "expire_time": row[5],
            "url": url
        }
    })

# ========== 列表 ==========
@app.get("/files")
async def list_files():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM files ORDER BY upload_time DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()

    return JSONResponse(status_code=200, content={
        "code": 200,
        "data": [{
            "id": r[0],
            "original_name": r[2],
            "size": r[3],
            "upload_time": r[4],
            "expire_time": r[5]
        } for r in rows]
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)