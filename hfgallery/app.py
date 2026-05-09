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

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Gallery</title>
    <style>
        .grid-item .img-content {
            width: 100%;
            height: auto;
            border-radius: 10px;
            box-shadow: 0px 5px 10px rgba(0, 0, 0, 0.3);
            cursor: pointer;
        }
        img[data-src]{
            opacity: 0;
            transform: translateY(20px);
            transition: 
                opacity 0.6s ease-out,
                transform 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        img.loaded {
            animation: gentleDrop 1.2s both;
        }
       @keyframes gentleDrop {
           0% { opacity: 0; transform: translateY(-20px) scale(0.5); }
           50% { opacity: 0.8; transform: translateY(5px) scale(1.01); }
           100% { opacity: 1; transform: none; }
       }
        .grid-item .hidden-info { display: none; }
        .grid-item .bottomInfo {
            color: white; font-family: siyuanmid; font-size: 12px;
            background-color: rgba(0, 0, 0, 0.35); width: 94%; max-height: 40%;
            overflow: hidden; position: absolute; bottom: 0; text-align: center;
            padding: 0 3% 0 3%; border-radius: 0 0 10px 10px;
        }
        .grid-item .topRightInfo {
            color: white; font-family: siyuanxlight; font-size: 12px;
            background-color: rgba(0, 0, 0, 0.35); border-radius: 10px;
            position: absolute; right: 3px; top: 3px; padding: 0 3px 0 3px; margin: 0;
        }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
        @keyframes zoomIn { from { transform: scale(0.5); } to { transform: scale(1); } }
        @keyframes zoomOut { from { transform: scale(1); opacity: 1; } to { transform: scale(0.5) translateY(-300px); opacity: 0; } }
        .image-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            -webkit-backdrop-filter: blur(10px); background-color: rgba(0, 0, 0, 0.7);
            z-index: 1000; display: none; justify-content: center; align-items: center; flex-direction: column;
        }
        .image-overlay.active { display: flex; }
        .image-overlay.fadeIn { animation: fadeIn 0.5s ease forwards; }
        .image-overlay.fadeOut { animation: fadeOut 0.5s ease forwards; }
        .image-overlay #overlayimage-container.active {
            display: flex; position: absolute; max-height: auto; max-width: auto;
            justify-content: center; align-items: center; transition: transform 0.5s ease;
        }
        .image-overlay #overlayimage-container #overlay-image {
            max-height: 95vh; max-width: 95vw; border-radius: 10px; transition: transform 0.5s ease;
        }
        .image-overlay #overlayimage-container #overlay-image.zoomOut { animation: zoomOut 0.5s ease forwards; }
        .image-overlay #overlayimage-container #overlay-image.zoomIn { animation: zoomIn 0.5s ease forwards, fadeIn 0.3s ease forwards; }
        .image-overlay #overlayimage-container #overlay-infosvg {
            width: 7%; position: absolute; top: 7px; left: 7px; cursor: pointer; z-index: 1;
        }
        .image-overlay #overlayimage-container #overlay-infosvg.fadeIn { animation: fadeIn 0.5s ease forwards; }
        .image-overlay #overlayimage-container #overlay-infosvg.fadeOut { animation: fadeOut 0.5s ease forwards; }
        @keyframes overlayFadeInOut { 0% { opacity: 1 } 50% { opacity: 0 } 100% { opacity: 1 } }
        .image-overlay #overlayimage-container #overlay-infosvg.overlayFadeInOut { animation: overlayFadeInOut 0.75s ease forwards; }
        @keyframes nextPhotoChange {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0; transform: scale(0.3) translateY(-300px); }
            100% { opacity: 1; transform: scale(1) translateY(0px); }
        }
        @keyframes prevPhotoChange {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0; transform: scale(0.3) translateY(300px); }
            100% { opacity: 1; transform: scale(1) translateY(0px); }
        }
        .nextPhotoChange { animation: nextPhotoChange 0.75s ease-in-out forwards; }
        .prevPhotoChange { animation: prevPhotoChange 0.75s ease-in-out forwards; }
        @keyframes colorChange {
            0% { background-color: rgb(110, 114, 114, 0.5); }
            50% { background-color: rgba(184, 188, 188, 0.8); }
            100% { background-color: rgb(110, 114, 114, 0.5); }
        }
        .colorChange { animation: colorChange 0.5s forwards; }
        #overlay-id {
            position: absolute; max-width: 80%; bottom: 30px; z-index: 1; cursor: pointer;
            margin-top: 10px; margin-bottom: 10px; padding: 10px; color: #fff; font-size: 15px;
            font-family: siyuanmid; border-radius: 10px;
            border: 1px solid rgba(198, 202, 202, 0.5); background: rgb(110, 114, 114, 0.5); transition: 0.5s;
        }
        .fadeIn { animation: fadeIn 0.5s ease forwards; }
        .fadeOut { animation: fadeOut 0.5s ease forwards; }
        #overlay-info p { margin-top: 0; }
        #overlay-info {
            color: #fff; font-size: 15px; font-family: siyuanmid; line-height: 1.4;
            border-radius: 10px; border: 1px; -webkit-backdrop-filter: blur(10px);
            background: rgb(110, 114, 114, 0.5); z-index: 2000;
            display: flex; align-items: center; text-align: left; flex-direction: column;
            word-wrap: break-word; word-break: break-all; overflow: auto;
            padding: 10px; position: absolute; top: 72%; height: 35%; width: 80%;
            transform: translateY(100px) scale(0); transition: 0.5s ease;
        }
        .show-text#overlay-info { transform: translateY(0) scale(1); transition: 0.5s ease; }
        #overlayimage-container.show-text { transform: translateY(-15%) scale(0.7); transition: transform 0.5s ease; }
        .show-fulltext#overlay-info {
            padding: 2.5vw; width: 92vw; height: 110vh; top: 2vh; transform: translateY(0); transition: 0.5s ease;
        }
        @keyframes overlaySlideChange {
            0% { opacity: 1; transform: translateY(0); }
            50% { opacity: 0; transform: translateY(50px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        .overlaySlideChange { animation: overlaySlideChange 0.75s forwards; }
        .grid-item #infosvg { width: 10%; position: absolute; top: 3px; left: 3px; z-index: 1; cursor: pointer; }
        .info-overlay p { margin-top: 0; }
        .info-overlay {
            line-height: 1.4; -webkit-backdrop-filter: blur(10px); background-color: rgba(0, 0, 0, 0.7);
            z-index: 2000; color: #fff; font-size: 15px; font-family: siyuanmid;
            position: fixed; top: 0; left: 0; display: none; justify-content: center;
            align-items: center; text-align: left; flex-direction: column; overflow: auto;
            word-wrap: break-word; word-break: break-all; animation: fadeIn 0.5s ease forwards;
            height: 100%; width: 95vw; padding: 2.5vw;
        }
        .info-overlay.active { display: flex; }
        .info-overlay.fadeOut { animation: fadeOut 0.5s ease forwards; }
        .search-box{display:flex;justify-content:center;padding:20px;gap:10px}
        .search-box input{padding:10px 15px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;width:300px;font-size:1em}
        .search-box button{padding:10px 20px;border-radius:8px;border:none;background:#6366f1;color:#fff;cursor:pointer}
        .header{text-align:center;padding:20px}
    </style>
</head>
<body>
    <div class="header"><h1>🖼️ AI Gallery</h1><p id="count">加载中...</p></div>
    <div class="search-box">
        <input type="text" id="s" placeholder="搜索 prompt...">
        <button onclick="searchImages()">搜索</button>
    </div>
    <div class="grid-container" id="grid-container"></div>

    <div class="image-overlay" id="image-overlay">
        <div id=overlayimage-container>
            <img id="overlay-image">
            <img id="overlay-infosvg" src="">
        </div>
        <div id='overlay-id'></div>
        <div id="overlay-info">
            <div id="overlay-info-content"></div>
        </div>
    </div>
    <div class="info-overlay">
        <div id="info-overlay-content"></div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/macy@2"></script>
    <script>
var macy;
var allData = [];
var currentPage = 0;
var searchQuery = '';
var infosvgSrc = "data:image/jpeg;base64,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";
var overlay, overlayImage, overlayInfo, overlayInfoContent, overlayImageId, overlayInfosvg, overlayImageContainer;
var infoOverlay, infoOverlayContent;
var copiedItems = [];
var touchStartY = 0, touchEndY = 0;

function initAll(){
    overlay = document.getElementById('image-overlay');
    overlayImage = document.getElementById('overlay-image');
    overlayInfo = document.getElementById('overlay-info');
    overlayInfoContent = document.getElementById('overlay-info-content');
    overlayImageId = document.getElementById('overlay-id');
    overlayInfosvg = document.getElementById('overlay-infosvg');
    overlayImageContainer = document.getElementById('overlayimage-container');
    infoOverlay = document.querySelector('.info-overlay');
    infoOverlayContent = document.getElementById('info-overlay-content');
    overlayInfosvg.src = infosvgSrc;
    bindOverlayEvents();
}

function bindOverlayEvents(){
    overlay.addEventListener('click', closeOverlay);
    overlayInfosvg.addEventListener('click', function(event){
        event.stopPropagation();
        overlayImageContainer.classList.toggle('show-text');
        overlayInfo.classList.toggle('show-text');
        if(overlayImageContainer.classList.contains('show-text')){
            overlayImageId.classList.add('fadeOut');
        }else{
            closeOverlayInfoShowText();
        }
    });
    overlayImage.addEventListener('touchstart', function(e){
        touchStartY = e.touches[0].clientY;
    });
    overlayImage.addEventListener('touchend', function(e){
        touchEndY = e.changedTouches[0].clientY;
        var deltaY = touchEndY - touchStartY;
        if(deltaY > 50){ slidePrevImage(); }
        else if(deltaY < -50){ slideNextImage(); }
    });
    overlayImage.addEventListener('touchmove', function(e){ e.preventDefault(); e.stopPropagation(); });
    overlayInfo.addEventListener('touchmove', function(e){ e.preventDefault(); e.stopPropagation(); });
    overlayInfo.addEventListener('touchstart', function(e){ touchStartY = e.touches[0].clientY; });
    overlayInfo.addEventListener('touchend', function(e){
        touchEndY = e.changedTouches[0].clientY;
        var deltaY = touchEndY - touchStartY;
        if(deltaY > 50){ closeOverlayInfoShowText(); }
        else if(deltaY < -50){ overlayInfo.classList.toggle('show-fulltext'); }
    });
    infoOverlay.addEventListener('click', function(){
        infoOverlay.classList.add('fadeOut');
        setTimeout(function(){ infoOverlay.classList.remove('fadeOut'); infoOverlay.classList.remove('active'); },500);
    });
    document.body.addEventListener('click', function(event){
        if(event.target.classList.contains('copy')){
            event.stopPropagation();
            if(!copiedItems.includes(event.target.innerHTML)){
                copiedItems.push(event.target.innerHTML);
                navigator.clipboard.writeText(copiedItems.join('\\n'));
                event.target.classList.add('colorChange');
                setTimeout(function(){ event.target.classList.remove('colorChange'); },500);
            }
        }
    });
    overlayImageId.addEventListener('click', function(){
        if(!copiedItems.includes(overlayImageId.innerHTML)) copiedItems.push(overlayImageId.innerHTML);
    });
}

function closeOverlayInfoShowText(){
    overlayImageContainer.classList.remove('show-text');
    overlayInfo.classList.remove('show-text');
    overlayInfo.classList.remove('show-fulltext');
    overlayImageId.classList.remove('fadeOut');
    overlayImageId.classList.add('fadeIn');
    setTimeout(function(){ overlayImageId.classList.remove('fadeIn'); },500);
}

function closeOverlay(){
    if(overlayImageContainer.classList.contains('show-text')){
        closeOverlayInfoShowText();
        setTimeout(function(){ applyCloseAnimation(); },500);
    }else{ applyCloseAnimation(); }
}

function applyCloseAnimation(){
    navigator.clipboard.writeText(copiedItems.join('\\n'));
    overlayImage.classList.add('zoomOut');
    overlay.classList.add('fadeOut');
    setTimeout(function(){
        overlayImage.classList.remove('zoomOut');
        overlay.classList.remove('fadeOut');
        overlay.classList.remove('active');
        overlayImageId.classList.remove('fadeOut');
        overlayImageContainer.classList.remove('active');
    },600);
}

function slideNextImage(){
    overlayImage.classList.add('nextPhotoChange');
    overlayInfosvg.classList.add('overlayFadeInOut');
    overlayImageId.classList.add('colorChange');
    if(overlayImageContainer.classList.contains('show-text')){
        overlayInfo.classList.add('overlaySlideChange');
        setTimeout(function(){ overlayInfo.classList.remove('overlaySlideChange'); },750);
    }
    setTimeout(function(){
        overlayImage.classList.remove('nextPhotoChange');
        overlayInfosvg.classList.remove('overlayFadeInOut');
        overlayImageId.classList.remove('colorChange');
    },750);
}

function slidePrevImage(){
    overlayImage.classList.add('prevPhotoChange');
    overlayInfosvg.classList.add('overlayFadeInOut');
    overlayImageId.classList.add('colorChange');
    if(overlayImageContainer.classList.contains('show-text')){
        overlayInfo.classList.add('overlaySlideChange');
        setTimeout(function(){ overlayInfo.classList.remove('overlaySlideChange'); },750);
    }
    setTimeout(function(){
        overlayImage.classList.remove('prevPhotoChange');
        overlayInfosvg.classList.remove('overlayFadeInOut');
        overlayImageId.classList.remove('colorChange');
    },750);
}

function getPrevImage(currentSrc){
    var imgs = document.querySelectorAll('.grid-item .img-content');
    for(var i=0;i<imgs.length;i++){ if(imgs[i].src===currentSrc && i>0) return imgs[i-1]; }
    return null;
}
function getNextImage(currentSrc){
    var imgs = document.querySelectorAll('.grid-item .img-content');
    for(var i=0;i<imgs.length;i++){ if(imgs[i].src===currentSrc && i<imgs.length-1) return imgs[i+1]; }
    return null;
}
function getPrevId(currentId){
    var ids = document.querySelectorAll('.image-id');
    for(var i=0;i<ids.length;i++){ if(ids[i].innerHTML===currentId && i>0) return ids[i-1]; }
    return null;
}
function getNextId(currentId){
    var ids = document.querySelectorAll('.image-id');
    for(var i=0;i<ids.length;i++){ if(ids[i].innerHTML===currentId && i<ids.length-1) return ids[i+1]; }
    return null;
}
function getPrevInfo(currentTxt){
    var infos = document.querySelectorAll('.image-info');
    for(var i=0;i<infos.length;i++){ if(infos[i].innerHTML===currentTxt && i>0) return infos[i-1]; }
    return null;
}
function getNextInfo(currentTxt){
    var infos = document.querySelectorAll('.image-info');
    for(var i=0;i<infos.length;i++){ if(infos[i].innerHTML===currentTxt && i<infos.length-1) return infos[i+1]; }
    return null;
}

// ========== Macy + 数据加载 ==========
function rebuildMacy(){
    if(macy) macy.recalculate(true);
    else macy = Macy({container:'#grid-container',trueOrder:false,waitForImages:false,margin:5,columns:4,breakAt:{1200:3,768:2,480:1}});
}

function renderCards(items, append){
    var grid = document.getElementById('grid-container');
    if(!append) grid.innerHTML = '';
    items.forEach(function(item){
        var div = document.createElement('div');
        div.className = 'grid-item';
        div.innerHTML = item.img_html;
        grid.appendChild(div);
    });
    rebuildMacy();
    setTimeout(function(){ macy.recalculate(true); },500);

    // 重新绑定图片点击
    var imgs = grid.querySelectorAll('.grid-item .img-content');
    imgs.forEach(function(img){
        if(!img._bound){
            img._bound = true;
            img.addEventListener('click', function(){
                overlayImage.src = this.src;
                overlayImage.alt = this.alt;
                overlay.classList.add('active');
                overlay.classList.add('fadeIn');
                overlayImageContainer.classList.add('active');
                overlayImage.classList.add('zoomIn');
                setTimeout(function(){ overlayImage.classList.remove('zoomIn'); },500);
                overlayImageId.classList.add('fadeIn');
                setTimeout(function(){ overlayImageId.classList.remove('fadeIn'); },500);
                overlayInfosvg.classList.add('fadeIn');
                setTimeout(function(){ overlayInfosvg.classList.remove('fadeIn'); },500);
                var infoEl = this.parentNode.querySelector('.image-info');
                var idEl = this.parentNode.querySelector('.image-id');
                overlayImageId.innerHTML = idEl ? idEl.innerHTML : '';
                overlayInfoContent.innerHTML = infoEl ? infoEl.innerHTML : '';
            });
        }
    });

    // 绑定 info 按钮
    var infosvgs = grid.querySelectorAll('.grid-item #infosvg');
    infosvgs.forEach(function(svg){
        svg.src = infosvgSrc;
        if(!svg._bound){
            svg._bound = true;
            svg.addEventListener('click', function(e){
                e.stopPropagation();
                var infoEl = this.parentNode.querySelector('.image-info');
                infoOverlayContent.innerHTML = infoEl ? infoEl.innerHTML : '';
                infoOverlay.classList.add('active');
                infoOverlayContent.scrollTop = 0;
            });
        }
    });

    // Observer lazy load
    var observer = new IntersectionObserver(function(entries, obs){
        entries.forEach(function(entry){
            if(entry.isIntersecting){
                var img = entry.target;
                if(img.dataset.src){
                    img.src = img.dataset.src;
                    img.onload = function(){
                        setTimeout(function(){ img.classList.add('loaded'); },100);
                        macy.recalculate(true);
                    };
                }
                obs.unobserve(img);
            }
        });
    });
    imgs.forEach(function(img){ observer.observe(img); });
}

async function loadMore(reset){
    if(window._loading) return;
    window._loading = true;
    if(reset){ currentPage = 0; allData = []; }
    var url = '/api/images?page='+currentPage+'&search='+encodeURIComponent(searchQuery);
    var res = await fetch(url,{credentials:'include'});
    var d = await res.json();
    document.getElementById('count').innerText = '共 '+d.total+' 张';
    allData = reset ? d.images : allData.concat(d.images);
    renderCards(d.images, !reset);
    currentPage++;
    window._loading = false;
    if(!d.has_more){ window.removeEventListener('scroll',onScroll); }
}
function onScroll(){
    if(window.innerHeight+window.scrollY >= document.body.offsetHeight-500) loadMore(false);
}
window.addEventListener('scroll',onScroll);

async function searchImages(){
    searchQuery = document.getElementById('s').value;
    document.getElementById('grid-container').innerHTML = '';
    allData = [];
    await loadMore(true);
}

// 初始化
initAll();
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