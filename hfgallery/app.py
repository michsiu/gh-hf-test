import os
import json
import sqlite3
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

# 配置：改回当前目录防止权限问题
JSON_URL = "https://raw.githubusercontent.com/michsiu/liblib/main/WhiskTasks/WhiskTasks.json"
DB_PATH = "gallery.db"

app = FastAPI()

def init_gallery():
    if os.path.exists(DB_PATH):
        return
    headers = {}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    resp = requests.get(JSON_URL, headers=headers)
    if resp.status_code != 200:
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
        conn.execute("INSERT OR REPLACE INTO images VALUES (?,?,?,?,?,?,?)",
             (hash_id, item.get("createdAt", ""), item.get("imageUrl", ""),
             panel.get("prompt", ""),
             item.get("genInfo", {}).get("modelInput", {}).get("modelNameType", ""),
             gen_images.get("seed", 0), item.get("imgList", "")))
    conn.commit()
    conn.close()

init_gallery()

# 这里 100% 还原你的原始 HTML 代码，仅在标注处修复核心 Bug
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Gallery</title>
    <style>
        body { background-color: #0f172a; color: white; margin: 0; font-family: sans-serif; }
        /* 你的原始样式全部保留 */
        .grid-container { width: 95%; margin: 0 auto; }
        .grid-item { position: relative; margin-bottom: 10px; }
        .img-content { width: 100%; height: auto; border-radius: 10px; box-shadow: 0px 5px 10px rgba(0, 0, 0, 0.3); cursor: pointer; }
        img[data-src]{ opacity: 0; transform: translateY(20px); transition: opacity 0.6s, transform 0.8s; }
        img.loaded { animation: gentleDrop 1.2s both; }
        @keyframes gentleDrop { 0% { opacity: 0; transform: translateY(-20px) scale(0.5); } 100% { opacity: 1; transform: none; } }
        .image-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; backdrop-filter: blur(10px); background: rgba(0,0,0,0.8); display: none; z-index: 1000; justify-content: center; align-items: center; flex-direction: column; }
        .image-overlay.active { display: flex; }
        #overlay-image { max-height: 85vh; max-width: 95vw; border-radius: 10px; transition: 0.5s; }
        #overlay-id { color: white; margin-top: 10px; background: rgba(110, 114, 114, 0.5); padding: 10px; border-radius: 10px; border: 1px solid rgba(198, 202, 202, 0.5); transition: 0.5s; }
        .show-text #overlay-id { transform: translateY(-50px); opacity: 0; }
        #overlay-info { position: absolute; bottom: 10%; width: 80%; background: rgba(0,0,0,0.8); padding: 20px; border-radius: 10px; display: none; color: white; max-height: 40vh; overflow-y: auto; border: 1px solid #444; }
        .show-text #overlay-info { display: block; animation: slideUp 0.5s forwards; }
        @keyframes slideUp { from { transform: translateY(100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        .colorChange { color: #3b82f6 !important; }
        .nextPhotoChange { animation: nextPhoto 0.75s; }
        @keyframes nextPhoto { 0% { transform: translateX(0); opacity: 1; } 50% { transform: translateX(100%); opacity: 0; } 51% { transform: translateX(-100%); opacity: 0; } 100% { transform: translateX(0); opacity: 1; } }
    </style>
</head>
<body>
    <div class="header" style="text-align:center;padding:20px">
        <h1>🖼️ AI Gallery</h1>
        <p id="count">加载中...</p>
    </div>
    
    <div id="grid-container" class="grid-container"></div>

    <div class="image-overlay" id="image-overlay">
        <div id="overlayimage-container" style="position:relative;">
            <img id="overlay-image">
            <img id="overlay-infosvg" style="position:absolute; top:10px; left:10px; width:30px; cursor:pointer;">
        </div>
        <div id="overlay-id"></div>
        <div id="overlay-info"><div id="overlay-info-content"></div></div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/macy@2"></script>
    <script>
        var macy;
        // 核心修复 2: 预声明变量
        var images, imageIds, imageInfos;
        var infosvgSrc = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z'/%3E%3C/svg%3E";

        const overlay = document.getElementById('image-overlay');
        const overlayImage = document.getElementById('overlay-image');
        const overlayImageId = document.getElementById('overlay-id');
        const overlayInfosvg = document.getElementById('overlay-infosvg');
        const overlayInfoContent = document.getElementById('overlay-info-content');

        function renderCards(items) {
            const grid = document.getElementById('grid-container');
            grid.innerHTML = items.map(item => `<div class="grid-item">${item.img_html}</div>`).join('');
            
            // 核心修复 3: 渲染后重新绑定节点引用，否则你的切换功能会报 undefined
            images = document.querySelectorAll('.img-content');
            imageIds = document.querySelectorAll('.image-id');
            imageInfos = document.querySelectorAll('.image-info');

            if (!macy) {
                macy = Macy({ container: '#grid-container', trueOrder: false, margin: 10, columns: 4, breakAt: { 1200: 3, 768: 2, 480: 1 } });
            } else {
                macy.recalculate(true);
            }
            initLogic();
        }

        function initLogic() {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.onload = () => { img.classList.add('loaded'); macy.recalculate(true); };
                        observer.unobserve(img);
                    }
                });
            });

            images.forEach((img, idx) => {
                observer.observe(img);
                img.onclick = function() {
                    overlayImage.src = this.src;
                    overlayImageId.innerHTML = imageIds[idx].innerHTML;
                    overlayInfoContent.innerHTML = imageInfos[idx].innerHTML;
                    overlay.classList.add('active');
                };
            });
        }

        overlayInfosvg.src = infosvgSrc;
        // 核心修复 4: 显式传入 event 对象，修复原代码 stopPropagation 报错
        overlayInfosvg.onclick = function(event) {
            event.stopPropagation();
            overlay.classList.toggle('show-text');
        };

        // 核心修复 5: 左右切换图片逻辑的变量一致性
        overlayImage.onclick = function(event) {
            event.stopPropagation();
            let currentSrc = overlayImage.src;
            let idx = Array.from(images).findIndex(img => img.src === currentSrc);
            let nextIdx = (idx + 1) % images.length;
            
            overlayImage.classList.add('nextPhotoChange');
            setTimeout(() => {
                overlayImage.src = images[nextIdx].src;
                overlayImageId.innerHTML = imageIds[nextIdx].innerHTML;
                overlayInfoContent.innerHTML = imageInfos[nextIdx].innerHTML;
                overlayImage.classList.remove('nextPhotoChange');
            }, 400);
        };

        overlay.onclick = function() {
            this.classList.remove('active');
            this.classList.remove('show-text');
        };

        fetch('/api/images?limit=1000').then(res => res.json()).then(data => {
            document.getElementById('count').innerText = '共 ' + data.total + ' 张';
            renderCards(data.images);
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML)

@app.get("/api/images")
async def get_images(page: int = Query(0), search: str = Query(""), limit: int = Query(20)):
    # 核心修复 6: 确保数据库连接在函数内部打开关闭，防止多线程死锁
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if search:
            total = conn.execute("SELECT COUNT(*) as t FROM images WHERE prompt LIKE ?", (f"%{search}%",)).fetchone()["t"]
            rows = conn.execute("SELECT * FROM images WHERE prompt LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (f"%{search}%", limit, page * limit)).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) as t FROM images").fetchone()["t"]
            rows = conn.execute("SELECT * FROM images ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, page * limit)).fetchall()
        return {"total": total, "images": [dict(r) for r in rows]}
    finally:
        conn.close()
