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
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,sans-serif}
.header{padding:20px;text-align:center}
.header h1{font-size:1.8em}
.header p{color:#94a3b8;margin-top:5px}
.search-box{display:flex;justify-content:center;padding:0 20px 20px;gap:10px}
.search-box input{padding:10px 15px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;width:300px;font-size:1em}
.search-box button{padding:10px 20px;border-radius:8px;border:none;background:#6366f1;color:#fff;cursor:pointer}
.grid{columns:4 260px;gap:12px;padding:0 12px 12px}
.card{break-inside:avoid;margin-bottom:12px;background:#1e293b;border-radius:12px;overflow:hidden;transition:transform .2s}
.card:hover{transform:scale(1.02)}
.card img{width:100%;display:block;border-radius:12px 12px 0 0}
.card .info{padding:12px;cursor:pointer}
.card .prompt{font-size:.8em;color:#cbd5e1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:8px}
.card .meta{font-size:.7em;color:#64748b;display:flex;justify-content:space-between}
.loading{text-align:center;padding:20px;color:#64748b}

.lightbox{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:1000;display:none;justify-content:center;align-items:center;flex-direction:column}
.lightbox.active{display:flex}
.lightbox img{max-height:85vh;max-width:95vw;border-radius:10px}
.lightbox .lb-id{color:#fff;margin-top:15px;font-size:14px;background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:8px}
.lightbox .lb-prompt{color:#ccc;font-size:13px;max-width:80vw;margin-top:10px;text-align:center;line-height:1.4;cursor:pointer;padding:8px 12px;border-radius:8px;transition:background .2s}
.lightbox .lb-prompt:hover{background:rgba(255,255,255,0.1)}

.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#6366f1;color:#fff;padding:12px 24px;border-radius:8px;font-size:14px;z-index:9999;opacity:0;transition:opacity .3s,.3s}
.toast.show{opacity:1}
</style>
</head>
<body>
<div class="header"><h1>🖼️ AI Gallery</h1><p id="count"></p></div>
<div class="search-box">
    <input type="text" id="s" placeholder="搜索 prompt...">
    <button onclick="search()">搜索</button>
</div>
<div class="grid" id="g"></div>
<div class="loading" id="ld">加载中...</div>

<div class="lightbox" id="lb" onclick="this.classList.remove('active')">
    <img id="lb-img" onclick="event.stopPropagation()">
    <div class="lb-id" id="lb-id"></div>
    <div class="lb-prompt" id="lb-prompt" onclick="event.stopPropagation();copyPrompt()"></div>
</div>

<div class="toast" id="toast">提示词已复制</div>

<script>
let page=0,loading=false,all=[],searchQuery='',lbIdx=-1;
let touchStartY=0;

function showToast(){
    let t=document.getElementById('toast');
    t.classList.add('show');
    clearTimeout(t._timeout);
    t._timeout=setTimeout(function(){t.classList.remove('show')},2000);
}

function copyPrompt(){
    let d=all[lbIdx];
    if(d&&d.prompt){
        navigator.clipboard.writeText(d.prompt).then(function(){
            showToast();
        });
    }
}

function showLightbox(idx){
    lbIdx=idx;
    let d=all[idx];
    document.getElementById('lb-img').src=d.image_url;
    document.getElementById('lb-id').innerText='ID: '+d.hash_id;
    document.getElementById('lb-prompt').innerText=d.prompt||'';
    document.getElementById('lb').classList.add('active');
}

document.getElementById('lb-img').addEventListener('touchstart',function(e){
    touchStartY=e.touches[0].clientY;
    e.stopPropagation();
});
document.getElementById('lb-img').addEventListener('touchend',function(e){
    let d=e.changedTouches[0].clientY-touchStartY;
    if(d>50&&lbIdx>0)showLightbox(lbIdx-1);
    if(d<-50&&lbIdx<all.length-1)showLightbox(lbIdx+1);
    e.stopPropagation();
});

function render(items,append){
    let g=document.getElementById('g');
    if(!append){g.innerHTML='';lbIdx=-1;}
    items.forEach(function(d,i){
        let c=document.createElement('div');
        c.className='card';
        c.innerHTML='<img src="'+d.image_url+'" loading="lazy" onerror="this.style.display=\\'none\\'"><div class="info"><div class="prompt">'+(d.prompt||'')+'</div><div class="meta"><span>'+(d.model||'')+'</span><span>Seed:'+(d.seed||'')+'</span></div></div>';
        c.querySelector('.prompt').addEventListener('click',function(e){
            e.stopPropagation();
            navigator.clipboard.writeText(d.prompt).then(function(){showToast()});
        });
        c.querySelector('img').addEventListener('click',function(){showLightbox(append?all.length-items.length+i:i)});
        g.appendChild(c);
    });
}

async function load(reset){
    if(loading)return;loading=true;
    if(reset){page=0;all=[];document.getElementById('g').innerHTML='';}
    let s=document.getElementById('s').value;
    let res=await fetch('/api/images?page='+page+'&search='+encodeURIComponent(s),{credentials:'include'});
    let d=await res.json();
    if(reset)document.getElementById('count').innerText='共 '+d.total+' 张';
    all=reset?d.images:all.concat(d.images);
    render(d.images,!reset);
    page++;loading=false;
    if(!d.has_more){document.getElementById('ld').style.display='none';window.removeEventListener('scroll',os)}
}
function os(){if(window.innerHeight+window.scrollY>=document.body.offsetHeight-500)load(false)}
window.addEventListener('scroll',os);

function search(){searchQuery=document.getElementById('s').value;load(true)}

load(true);
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
        rows = conn.execute("SELECT hash_id, image_url, prompt, model, seed FROM images WHERE prompt LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (f"%{search}%", limit, page * limit)).fetchall()
    else:
        total = conn.execute("SELECT COUNT(*) as t FROM images").fetchone()["t"]
        rows = conn.execute("SELECT hash_id, image_url, prompt, model, seed FROM images ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, page * limit)).fetchall()
    conn.close()
    return {"total": total, "page": page, "has_more": (page + 1) * limit < total, "images": [dict(r) for r in rows]}