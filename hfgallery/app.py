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
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Gallery</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,sans-serif}.header{padding:20px;text-align:center}.header h1{font-size:1.8em}.header p{color:#94a3b8;margin-top:5px}.grid{columns:4 260px;gap:16px;padding:16px}.card{break-inside:avoid;margin-bottom:16px;background:#1e293b;border-radius:12px;overflow:hidden;transition:transform .2s}.card:hover{transform:scale(1.02)}.card img{width:100%;display:block}.card .info{padding:12px}.card .prompt{font-size:.8em;color:#cbd5e1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:8px}.card .meta{font-size:.7em;color:#64748b;display:flex;justify-content:space-between}.search-box{display:flex;justify-content:center;padding:0 20px 20px;gap:10px}.search-box input{padding:10px 15px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;width:300px;font-size:1em}.search-box button{padding:10px 20px;border-radius:8px;border:none;background:#6366f1;color:#fff;cursor:pointer}.loading{text-align:center;padding:20px;color:#64748b}</style></head>
<body><div class="header"><h1>🖼️ AI Gallery</h1><p id="count">加载中...</p></div>
<div class="search-box"><input type="text" id="s" placeholder="搜索 prompt..."><button onclick="l(1)">搜索</button></div>
<div class="grid" id="g"></div><div class="loading" id="ld">加载中...</div>
<script>
let p=0,b=!1;
async function l(r){if(b)return;b=!0;if(r){p=0;g.innerHTML=''}let s=document.getElementById('s').value;let res=await fetch(`/api/images?page=${p}&search=${encodeURIComponent(s)}`);let d=await res.json();if(r)document.getElementById('count').innerText=`共 ${d.total} 张`;for(let i of d.images){let c=document.createElement('div');c.className='card';c.innerHTML=`<img src="${i.image_url}" loading="lazy" onerror="this.style.display='none'"><div class="info"><div class="prompt">${i.prompt||''}</div><div class="meta"><span>${i.model||''}</span><span>Seed:${i.seed||''}</span></div></div>`;g.appendChild(c)}p++;b=!1;if(!d.has_more){ld.style.display='none';window.removeEventListener('scroll',os)}}
function os(){if(window.innerHeight+window.scrollY>=document.body.offsetHeight-500)l(0)}
window.addEventListener('scroll',os);l(1);
</script></body></html>"""

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