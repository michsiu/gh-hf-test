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
    .search-box { display: flex; justify-content: center; padding: 0 20px 20px; gap: 10px; }
    .search-box input { padding: 10px 15px; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: #e2e8f0; width: 300px; font-size: 1em; }
    .search-box button { padding: 10px 20px; border-radius: 8px; border: none; background: #6366f1; color: #fff; cursor: pointer; }
    .grid-container { margin: 0 auto; padding: 10px; }
    .grid-item { position: relative; margin-bottom: 10px; border-radius: 10px; overflow: hidden; }
    .grid-item .img-content { width: 100%; height: auto; border-radius: 10px; box-shadow: 0px 5px 10px rgba(0,0,0,0.3); cursor: pointer; display: block; }
    .grid-item .image-id, .grid-item .image-info, .grid-item .hidden-info { display: none; }

    .image-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; display: none; justify-content: center; align-items: center; flex-direction: column; }
    .image-overlay.active { display: flex; }
    #overlayimage-container { max-width: 95vw; display: flex; flex-direction: column; align-items: center; }
    #overlay-image { max-height: 85vh; max-width: 95vw; border-radius: 10px; }
    #overlay-id { color: #fff; margin-top: 15px; font-size: 14px; background: rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 8px; cursor: pointer; }
    #overlay-info { color: #fff; font-size: 14px; max-width: 80vw; margin-top: 10px; text-align: center; }
</style>
</head>
<body>
<div class="header"><h1>🖼️ AI Gallery</h1><p id="count">加载中...</p></div>
<div class="search-box">
    <input type="text" id="s" placeholder="搜索 prompt...">
    <button onclick="searchImages()">搜索</button>
</div>
<div class="grid-container" id="grid"></div>

<div class="image-overlay" id="overlay">
    <div id="overlayimage-container">
        <img id="overlay-image">
    </div>
    <div id="overlay-id"></div>
    <div id="overlay-info"></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/macy@2"></script>
<script>
var macyInstance;
var allImages = __INIT_DATA__;
var currentPage = 1;
var currentOverlayIndex = -1;
var searchQuery = '';

function initMacy() {
    if (macyInstance) macyInstance.remove();
    macyInstance = Macy({
        container: '#grid',
        trueOrder: false,
        waitForImages: false,
        margin: 10,
        columns: 4,
        breakAt: { 1200: 3, 768: 2, 480: 1 }
    });
}

function renderCards(items) {
    var grid = document.getElementById('grid');
    items.forEach(function(item) {
        var div = document.createElement('div');
        div.className = 'grid-item';
        div.innerHTML = item.img_html;
        grid.appendChild(div);
    });
    // 绑定点击事件
    var imgs = document.querySelectorAll('.grid-item .img-content');
    imgs.forEach(function(img, idx) {
        img.addEventListener('click', function() {
            openOverlay(idx);
        });
    });
    initMacy();
    macyInstance.recalculate(true);
}

function openOverlay(idx) {
    currentOverlayIndex = idx;
    var allImgs = document.querySelectorAll('.grid-item .img-content');
    var img = allImgs[idx];
    document.getElementById('overlay-image').src = img.src;
    document.getElementById('overlay-id').innerText = 'ID: ' + (allImages[idx] ? allImages[idx].hash_id : '');
    document.getElementById('overlay-info').innerText = allImages[idx] ? allImages[idx].prompt || '' : '';
    document.getElementById('overlay').classList.add('active');
}

document.getElementById('overlay').addEventListener('click', function(e) {
    if (e.target === this) {
        this.classList.remove('active');
    }
});

// 滑动切换
var touchStartY = 0;
document.getElementById('overlay-image').addEventListener('touchstart', function(e) {
    touchStartY = e.touches[0].clientY;
    e.stopPropagation();
});
document.getElementById('overlay-image').addEventListener('touchend', function(e) {
    var deltaY = e.changedTouches[0].clientY - touchStartY;
    var allImgs = document.querySelectorAll('.grid-item .img-content');
    if (deltaY > 50 && currentOverlayIndex > 0) {
        openOverlay(currentOverlayIndex - 1);
    } else if (deltaY < -50 && currentOverlayIndex < allImgs.length - 1) {
        openOverlay(currentOverlayIndex + 1);
    }
    e.stopPropagation();
});

// 搜索
async function searchImages() {
    searchQuery = document.getElementById('s').value;
    currentPage = 0;
    document.getElementById('grid').innerHTML = '';
    allImages = [];
    await loadMore();
}

// 无限滚动
var loading = false;
async function loadMore() {
    if (loading) return;
    loading = true;
    var url = '/api/images?page=' + currentPage + '&search=' + encodeURIComponent(searchQuery);
    var res = await fetch(url, { credentials: 'include' });
    var d = await res.json();
    allImages = allImages.concat(d.images);
    renderCards(d.images);
    currentPage++;
    loading = false;
    document.getElementById('count').innerText = '共 ' + d.total + ' 张';
    if (!d.has_more) window.removeEventListener('scroll', onScroll);
}
function onScroll() {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) loadMore();
}
window.addEventListener('scroll', onScroll);

// 初始加载
// 等 Macy 加载完再初始化
function waitForMacy(callback) {
    if (typeof Macy !== 'undefined') {
        callback();
    } else {
        setTimeout(function() { waitForMacy(callback); }, 100);
    }
}
waitForMacy(function() {
    renderCards(INIT_DATA);
    loadMore();
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT hash_id, prompt, img_html FROM images ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    
    init_data = json.dumps([dict(r) for r in rows], ensure_ascii=False)
    html = HTML.replace("__INIT_DATA__", init_data)
    return HTMLResponse(content=html)
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