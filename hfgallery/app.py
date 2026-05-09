import os
import json
import sqlite3
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

JSON_URL = "https://raw.githubusercontent.com/michsiu/liblib/main/WhiskTasks/WhiskTasks.json"
DB_PATH = "/tmp/gallery.db"

app = FastAPI()

def init_gallery():
    if os.path.exists(DB_PATH):
        return
    print("下载 JSON 数据...")
    
    headers = {}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    
    resp = requests.get(JSON_URL, headers=headers)
    print(f"状态码: {resp.status_code}")
    if resp.status_code != 200:
        print(f"错误: {resp.text[:500]}")
        return
    
    data = resp.json()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            hash_id TEXT PRIMARY KEY,
            created_at TEXT,
            image_url TEXT,
            prompt TEXT,
            model TEXT,
            seed INTEGER,
            img_html TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON images(created_at DESC)")
    for hash_id, item in data.items():
        panel = item.get("imagePanels", [{}])[0]
        gen_images = panel.get("generatedImages", [{}])[0]
        conn.execute(
            "INSERT OR REPLACE INTO images VALUES (?,?,?,?,?,?,?)",
            (hash_id, item.get("createdAt", ""), item.get("imageUrl", ""),
             panel.get("prompt", ""),
             item.get("genInfo", {}).get("modelInput", {}).get("modelNameType", ""),
             gen_images.get("seed", 0), item.get("imgList", ""))
        )
    conn.commit()
    conn.close()
    print(f"导入完成: {len(data)} 条")

init_gallery()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Gallery</title>
<style>
    body { background: #0f172a; color: #e2e8f0; font-family: -apple-system, sans-serif; margin: 0; }
    .header { padding: 20px; text-align: center; }
    .header h1 { font-size: 1.8em; margin: 0; }
    .header p { color: #94a3b8; margin-top: 5px; }
    .grid-container { columns: 4 260px; gap: 10px; padding: 10px; }
    .grid-item { position: relative; break-inside: avoid; margin-bottom: 10px; border-radius: 10px; overflow: hidden; cursor: pointer; }
    .img-content { width: 100%; height: auto; border-radius: 10px; box-shadow: 0px 5px 10px rgba(0,0,0,0.3); cursor: pointer; display: block; }
    .image-id, .image-info { display: none; }

    /* overlay */
    .image-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; display: none; justify-content: center; align-items: center; flex-direction: column; }
    .image-overlay.active { display: flex; }
    #overlayimage-container { display: flex; flex-direction: column; align-items: center; max-width: 95vw; }
    #overlay-image { max-height: 85vh; max-width: 95vw; border-radius: 10px; transition: transform 0.3s; }
    #overlay-id { color: #fff; margin-top: 15px; font-size: 14px; background: rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 8px; cursor: pointer; }
</style>
</head>
<body>
<div class="header">
    <h1>🖼️ AI Gallery</h1>
    <p id="count">加载中...</p>
</div>
<div class="grid-container" id="grid"></div>

<div class="image-overlay" id="overlay">
    <div id="overlayimage-container">
        <img id="overlay-image">
    </div>
    <div id="overlay-id"></div>
</div>

<script>
const INIT_DATA = __INIT_DATA__;

function renderCard(item) {
    let div = document.createElement('div');
    div.className = 'grid-item';
    div.innerHTML = item.img_html;
    // 绑定点击
    let img = div.querySelector('.img-content');
    if (img) {
        img.addEventListener('click', function() {
            openOverlay(this.src, item.hash_id);
        });
    }
    return div;
}

function openOverlay(src, id) {
    document.getElementById('overlay-image').src = src;
    document.getElementById('overlay-id').innerText = id;
    document.getElementById('overlay').classList.add('active');
}

document.getElementById('overlay').addEventListener('click', function(e) {
    if (e.target === this || e.target.id === 'overlay-image') {
        this.classList.remove('active');
    }
});

// 初始渲染
let grid = document.getElementById('grid');
INIT_DATA.forEach(item => grid.appendChild(renderCard(item)));
document.getElementById('count').innerText = '共 ' + INIT_DATA.length + ' 张';

// 无限滚动
let page = 1, loading = false;
async function loadMore() {
    if (loading) return;
    loading = true;
    let res = await fetch('/api/images?page=' + page, { credentials: 'include' });
    let d = await res.json();
    d.images.forEach(item => grid.appendChild(renderCard(item)));
    page++;
    loading = false;
    if (!d.has_more) window.removeEventListener('scroll', onScroll);
}
function onScroll() {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) loadMore();
}
window.addEventListener('scroll', onScroll);
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML)

@app.get("/api/images")
async def get_images(page: int = Query(0), search: str = Query(""), limit: int = Query(20)):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if search:
        total = conn.execute("SELECT COUNT(*) as t FROM images WHERE prompt LIKE ?", (f"%{search}%",)).fetchone()["t"]
        rows = conn.execute("SELECT * FROM images WHERE prompt LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (f"%{search}%", limit, page * limit)).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) as t FROM images").fetchone()["t"]
        rows = conn.execute("SELECT * FROM images ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, page * limit)).fetchall()
    conn.close()
    return {"total": total, "page": page, "has_more": (page + 1) * limit < total, "images": [dict(r) for r in rows]}