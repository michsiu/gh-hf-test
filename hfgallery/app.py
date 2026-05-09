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
        conn.execute("INSERT OR REPLACE INTO images VALUES (?,?,?,?,?,?,?)",
            (hash_id, item.get("createdAt", ""), item.get("imageUrl", ""),
             panel.get("prompt", ""),
             item.get("genInfo", {}).get("modelInput", {}).get("modelNameType", ""),
             gen_images.get("seed", 0), item.get("imgList", "")))
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
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,sans-serif;margin:0}
.header{padding:20px;text-align:center}
.header h1{font-size:1.8em;margin:0}
.header p{color:#94a3b8;margin-top:5px}
.search-box{display:flex;justify-content:center;padding:0 20px 20px;gap:10px}
.search-box input{padding:10px 15px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;width:300px;font-size:1em}
.search-box button{padding:10px 20px;border-radius:8px;border:none;background:#6366f1;color:#fff;cursor:pointer}
.grid-container{margin:0 auto;padding:0 10px}
.grid-item{position:relative;border-radius:10px;overflow:hidden}
.grid-item .img-content{width:100%;height:auto;border-radius:10px;box-shadow:0px 5px 10px rgba(0,0,0,0.3);cursor:pointer;display:block}
.grid-item #infosvg{width:10%;position:absolute;top:3px;left:3px;z-index:1;cursor:pointer}
.grid-item .image-id,.grid-item .image-info,.grid-item .hidden-info{display:none}
.loading{text-align:center;padding:20px;color:#64748b}

.image-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:1000;display:none;justify-content:center;align-items:center;flex-direction:column}
.image-overlay.active{display:flex}
#overlayimage-container{max-width:95vw;transition:transform .3s}
#overlay-image{max-height:85vh;max-width:95vw;border-radius:10px;transition:transform .3s,opacity .3s}
#overlay-image.zoomIn{animation:zoomIn .3s ease forwards}
#overlay-image.nextSlide{animation:nextSlide .4s ease forwards}
#overlay-image.prevSlide{animation:prevSlide .4s ease forwards}
#overlay-id{color:#fff;margin-top:15px;font-size:14px;background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:8px;cursor:pointer}
#overlay-infosvg{width:30px;position:absolute;top:10px;left:10px;cursor:pointer;z-index:1001}
#overlay-info-box{color:#fff;font-size:14px;max-width:80vw;margin-top:10px;text-align:center;line-height:1.5;display:none}
#overlay-info-box.show{display:block}

.info-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:2000;display:none;justify-content:center;align-items:center;flex-direction:column;overflow:auto;padding:20px}
.info-overlay.active{display:flex}
.info-overlay .info-content{color:#fff;font-size:15px;max-width:600px;text-align:left;line-height:1.6;background:rgba(255,255,255,0.1);padding:20px;border-radius:12px}

@keyframes zoomIn{from{transform:scale(.5);opacity:0}to{transform:scale(1);opacity:1}}
@keyframes nextSlide{0%{transform:translateY(0);opacity:1}50%{transform:translateY(-50px);opacity:0}51%{transform:translateY(50px)}100%{transform:translateY(0);opacity:1}}
@keyframes prevSlide{0%{transform:translateY(0);opacity:1}50%{transform:translateY(50px);opacity:0}51%{transform:translateY(-50px)}100%{transform:translateY(0);opacity:1}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes fadeOut{from{opacity:1}to{opacity:0}}
</style>
</head>
<body>
<div class="header"><h1>🖼️ AI Gallery</h1><p id="count">加载中...</p></div>
<div class="search-box">
    <input type="text" id="s" placeholder="搜索 prompt...">
    <button onclick="searchImages()">搜索</button>
</div>
<div class="grid-container" id="grid"></div>
<div class="loading" id="ld">加载中...</div>

<div class="image-overlay" id="overlay">
    <div id="overlayimage-container">
        <img id="overlay-image">
    </div>
    <div id="overlay-id"></div>
    <div id="overlay-info-box"></div>
</div>
<div class="info-overlay" id="info-overlay" onclick="this.classList.remove('active')">
    <div class="info-content" id="info-content" onclick="event.stopPropagation()"></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/macy@2"></script>
<script>
var macy;
var allImages = [];
var currentPage = 0;
var searchQuery = '';
var currentOverlayIdx = -1;
var infosvgSrc = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='white'%3E%3Ccircle cx='12' cy='12' r='10' stroke='white' stroke-width='2' fill='none'/%3E%3Ctext x='12' y='17' text-anchor='middle' font-size='14' fill='white'%3Ei%3C/text%3E%3C/svg%3E";

function initMacy(){
    if(macy) macy.recalculate(true);
    else macy = Macy({container:'#grid',trueOrder:false,waitForImages:false,margin:8,columns:4,breakAt:{1200:3,768:2,480:1}});
}

function renderCards(items,append){
    var grid = document.getElementById('grid');
    if(!append) grid.innerHTML = '';
    items.forEach(function(item){
        var div = document.createElement('div');
        div.className = 'grid-item';
        div.innerHTML = item.img_html;
        // 给 grid-item 里的 img 加 loading lazy
        var img = div.querySelector('.img-content');
        if(img) img.loading = 'lazy';
        // 加信息按钮
        var infoBtn = div.querySelector('#infosvg');
        if(!infoBtn){
            infoBtn = document.createElement('img');
            infoBtn.id = 'infosvg';
            infoBtn.src = infosvgSrc;
            div.appendChild(infoBtn);
        }
        grid.appendChild(div);
    });
    initMacy();
    setTimeout(function(){ macy.recalculate(true); }, 300);
    bindEvents();
}

function bindEvents(){
    var items = document.querySelectorAll('.grid-item');
    items.forEach(function(item,idx){
        // 图片点击
        var img = item.querySelector('.img-content');
        if(img && !img._bound){
            img._bound = true;
            img.addEventListener('click',function(){
                currentOverlayIdx = idx;
                showOverlay(allImages[idx]);
            });
        }
        // 信息按钮点击
        var infoBtn = item.querySelector('#infosvg');
        if(infoBtn && !infoBtn._bound){
            infoBtn._bound = true;
            infoBtn.addEventListener('click',function(e){
                e.stopPropagation();
                showInfoOverlay(allImages[idx]);
            });
        }
    });
}

function showOverlay(data){
    var ov = document.getElementById('overlay');
    document.getElementById('overlay-image').src = data.image_url;
    document.getElementById('overlay-id').innerText = data.hash_id;
    document.getElementById('overlay-info-box').innerText = data.prompt||'';
    document.getElementById('overlay-image').classList.add('zoomIn');
    setTimeout(function(){ document.getElementById('overlay-image').classList.remove('zoomIn'); },300);
    ov.classList.add('active');
}

function showInfoOverlay(data){
    var io = document.getElementById('info-overlay');
    document.getElementById('info-content').innerHTML = '<b>Prompt:</b><br>'+data.prompt+'<br><br><b>Model:</b> '+data.model+'<br><b>Seed:</b> '+data.seed+'<br><b>ID:</b> '+data.hash_id;
    io.classList.add('active');
}

document.getElementById('overlay').addEventListener('click',function(e){
    if(e.target === this) this.classList.remove('active');
});

var touchY = 0;
document.getElementById('overlay-image').addEventListener('touchstart',function(e){
    touchY = e.touches[0].clientY; e.stopPropagation();
});
document.getElementById('overlay-image').addEventListener('touchend',function(e){
    var d = e.changedTouches[0].clientY - touchY;
    if(d > 50 && currentOverlayIdx < allImages.length-1){
        document.getElementById('overlay-image').classList.add('nextSlide');
        setTimeout(function(){
            currentOverlayIdx++;
            showOverlay(allImages[currentOverlayIdx]);
            document.getElementById('overlay-image').classList.remove('nextSlide');
        },200);
    } else if(d < -50 && currentOverlayIdx > 0){
        document.getElementById('overlay-image').classList.add('prevSlide');
        setTimeout(function(){
            currentOverlayIdx--;
            showOverlay(allImages[currentOverlayIdx]);
            document.getElementById('overlay-image').classList.remove('prevSlide');
        },200);
    }
    e.stopPropagation();
});

async function searchImages(){
    searchQuery = document.getElementById('s').value;
    currentPage = 0;
    allImages = [];
    document.getElementById('grid').innerHTML = '';
    await loadMore(true);
}

var loading = false;
async function loadMore(reset){
    if(loading) return;
    loading = true;
    if(reset) currentPage = 0;
    var url = '/api/images?page='+currentPage+'&search='+encodeURIComponent(searchQuery);
    var res = await fetch(url,{credentials:'include'});
    var d = await res.json();
    document.getElementById('count').innerText = '共 '+d.total+' 张';
    allImages = reset ? d.images : allImages.concat(d.images);
    renderCards(d.images, !reset);
    currentPage++;
    loading = false;
    if(!d.has_more){
        document.getElementById('ld').style.display = 'none';
        window.removeEventListener('scroll',onScroll);
    }
}

function onScroll(){
    if(window.innerHeight+window.scrollY >= document.body.offsetHeight-500) loadMore(false);
}
window.addEventListener('scroll',onScroll);

loadMore(true);
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