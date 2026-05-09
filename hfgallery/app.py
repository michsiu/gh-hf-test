import os
import json
import sqlite3
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

# 配置
JSON_URL = "https://raw.githubusercontent.com/michsiu/liblib/main/WhiskTasks/WhiskTasks.json"
DB_PATH = "/tmp/gallery.db"

app = FastAPI()

def init_gallery():
    if os.path.exists(DB_PATH): return
    headers = {}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token: headers["Authorization"] = f"token {token}"
    resp = requests.get(JSON_URL, headers=headers)
    if resp.status_code != 200: return
    data = resp.json()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            hash_id TEXT PRIMARY KEY, created_at TEXT, image_url TEXT,
            prompt TEXT, model TEXT, seed INTEGER, img_html TEXT
        )
    """)
    for hash_id, item in data.items():
        panel = item.get("imagePanels", [{}])[0]
        gen_images = panel.get("generatedImages", [{}])[0]
        conn.execute("INSERT OR REPLACE INTO images VALUES (?,?,?,?,?,?,?)",
             (hash_id, item.get("createdAt", ""), item.get("imageUrl", ""),
             panel.get("prompt", ""), item.get("genInfo", {}).get("modelInput", {}).get("modelNameType", ""),
             gen_images.get("seed", 0), item.get("imgList", "")))
    conn.commit()
    conn.close()

init_gallery()

# 完整保留你的原始 HTML/CSS/JS 功能，仅修复 Bug
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Gallery</title>
    <style>
        body { background-color: #0f172a; color: white; margin: 0; font-family: sans-serif; overflow-x: hidden; }
        .grid-container { width: 95%; margin: 0 auto; padding-top: 20px; }
        .grid-item { position: relative; margin-bottom: 10px; overflow: hidden; border-radius: 10px; }
        .img-content { width: 100%; height: auto; border-radius: 10px; box-shadow: 0px 5px 10px rgba(0, 0, 0, 0.3); cursor: pointer; display: block; }
        
        /* 保持你的原始动画样式 */
        img[data-src]{ opacity: 0; transform: translateY(20px); transition: opacity 0.6s, transform 0.8s; }
        img.loaded { animation: gentleDrop 1.2s both; }
        @keyframes gentleDrop { 0% { opacity: 0; transform: translateY(-20px) scale(0.5); } 100% { opacity: 1; transform: none; } }
        
        .image-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            backdrop-filter: blur(10px); background: rgba(0,0,0,0.8);
            display: none; z-index: 1000; justify-content: center; align-items: center; flex-direction: column;
        }
        .image-overlay.active { display: flex; }
        #overlay-image { max-height: 85vh; max-width: 95vw; border-radius: 10px; transition: 0.5s; cursor: pointer; }
        
        #overlay-id { 
            color: white; margin-top: 10px; background: rgba(110, 114, 114, 0.5); 
            padding: 10px; border-radius: 10px; border: 1px solid rgba(198, 202, 202, 0.5); 
            transition: 0.5s; font-size: 14px;
        }
        .show-text #overlay-id { transform: translateY(-50px); opacity: 0; }
        
        #overlay-info {
            position: absolute; bottom: 10%; width: 80%; background: rgba(0,0,0,0.8);
            padding: 20px; border-radius: 10px; display: none; color: white;
            max-height: 40vh; overflow-y: auto; border: 1px solid #444;
        }
        .show-text #overlay-info { display: block; animation: slideUp 0.5s forwards; }
        @keyframes slideUp { from { transform: translateY(100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

        /* 你的功能性 Class */
        .colorChange { color: #3b82f6 !important; }
        .overlayFadeInOut { animation: fadeInOut 0.75s; }
        @keyframes fadeInOut { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .nextPhotoChange { animation: nextPhoto 0.75s; }
        @keyframes nextPhoto { 0% { transform: translateX(0); opacity: 1; } 50% { transform: translateX(100%); opacity: 0; } 51% { transform: translateX(-100%); opacity: 0; } 100% { transform: translateX(0); opacity: 1; } }
        .prevPhotoChange { animation: prevPhoto 0.75s; }
        @keyframes prevPhoto { 0% { transform: translateX(0); opacity: 1; } 50% { transform: translateX(-100%); opacity: 0; } 51% { transform: translateX(100%); opacity: 0; } 100% { transform: translateX(0); opacity: 1; } }
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
        <div id="overlay-info">
            <div id="overlay-info-content"></div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/macy@2"></script>
    <script>
        var macy;
        // 修复点 2: 预定义这些变量，它们将在渲染后被赋值
        var images, imageIds, imageInfos; 
        var infosvgSrc = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z'/%3E%3C/svg%3E";

        const overlay = document.getElementById('image-overlay');
        const overlayImage = document.getElementById('overlay-image');
        const overlayImageId = document.getElementById('overlay-id');
        const overlayInfosvg = document.getElementById('overlay-infosvg');
        const overlayInfo = document.getElementById('overlay-info');
        const overlayInfoContent = document.getElementById('overlay-info-content');

        function rebuildMacy() {
            if (macy) macy.recalculate(true);
            else macy = Macy({ container: '#grid-container', trueOrder: false, margin: 10, columns: 4, breakAt: { 1200: 3, 768: 2, 480: 1 } });
        }

        async function loadData() {
            const res = await fetch('/api/images?limit=10000');
            const data = await res.json();
            document.getElementById('count').innerText = '共 ' + data.total + ' 张';
            renderCards(data.images);
        }

        function renderCards(items) {
            const grid = document.getElementById('grid-container');
            grid.innerHTML = items.map(item => `<div class="grid-item">${item.img_html}</div>`).join('');
            
            // 修复点 3: 渲染完成后必须更新这些全局 NodeList 引用
            images = grid.querySelectorAll('.img-content');
            imageIds = grid.querySelectorAll('.image-id');
            imageInfos = grid.querySelectorAll('.image-info');

            rebuildMacy();
            initGalleryLogic();
        }

        function initGalleryLogic() {
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

        // 你的原始交互功能修复
        overlayInfosvg.src = infosvgSrc;
        overlayInfosvg.onclick = function(e) {
            e.stopPropagation(); // 修复点 4: 确保 e/event 存在
            overlay.classList.toggle('show-text');
        };

        // 图片切换逻辑 (保持你的算法)
        overlayImage.onclick = function(e) {
            e.stopPropagation();
            const currentSrc = overlayImage.src;
            let idx = Array.from(images).findIndex(img => img.src === currentSrc);
            let nextIdx = (idx + 1) % images.length;
            
            overlayImage.classList.add('nextPhotoChange');
            overlayImageId.classList.add('colorChange');
            
            setTimeout(() => {
                overlayImage.src = images[nextIdx].src;
                overlayImageId.innerHTML = imageIds[nextIdx].innerHTML;
                overlayInfoContent.innerHTML = imageInfos[nextIdx].innerHTML;
                overlayImage.classList.remove('nextPhotoChange');
                overlayImageId.classList.remove('colorChange');
            }, 400);
        };

        overlay.onclick = function() {
            this.classList.remove('active');
            this.classList.remove('show-text');
        };

        loadData();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index(): return HTML(content=HTML)

@app.get("/api/images")
async def get_images(page: int = Query(0), search: str = Query(""), limit: int = Query(20)):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # ... 保持你的 API 逻辑不变 ...
    if search:
        total = conn.execute("SELECT COUNT(*) as t FROM images WHERE prompt LIKE ?", (f"%{search}%",)).fetchone()["t"]
        rows = conn.execute("SELECT * FROM images WHERE prompt LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (f"%{search}%", limit, page * limit)).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) as t FROM images").fetchone()["t"]
        rows = conn.execute("SELECT * FROM images ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, page * limit)).fetchall()
    conn.close()
    return {"total": total, "images": [dict(r) for r in rows]}
