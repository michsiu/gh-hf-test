import os
import json
import sqlite3
import requests
import re
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

JSON_URL_WHISK = "https://raw.githubusercontent.com/michsiu/liblib/main/WhiskTasks/WhiskTasks.json"
JSON_URL_LIBLIB = "https://raw.githubusercontent.com/michsiu/liblib/main/LibLibTasks/LibLibTasksImgIdDict.json"
DB_PATH = "/tmp/gallery.db"

DATA_SOURCES = {
    "whisk": JSON_URL_WHISK,
    "liblib": JSON_URL_LIBLIB
}

app = FastAPI()

def init_gallery():
    if os.path.exists(DB_PATH):
        return
    print("下载 JSON 数据...")
    headers = {}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            hash_id TEXT,
            source TEXT,
            created_at TEXT,
            image_url TEXT,
            prompt TEXT,
            model TEXT,
            seed INTEGER,
            img_html TEXT,
            PRIMARY KEY (source, hash_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON images(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON images(model)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON images(created_at DESC)")

    for source, url in DATA_SOURCES.items():
        print(f"下载 {source}: {url}")
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"  {source} 下载失败: {resp.status_code}")
            continue
        data = resp.json()
        count = 0
        for hash_id, item in data.items():
            img_url = item.get("imageUrl") or item.get("imgUrl") or ""
            prompt = ""
            model = ""
            seed = 0
            img_html = item.get("imgList") or item.get("imgHtml") or ""
            created_at = item.get("createdAt") or ""

            if "genInfo" in item:
                gi = item["genInfo"]
                if isinstance(gi, dict):
                    prompt = gi.get("prompt", "")
                    # Whisks 格式: modelInput.modelNameType
                    mi = gi.get("modelInput")
                    if isinstance(mi, dict) and mi.get("modelNameType"):
                        model = mi["modelNameType"]
                    # LibLib 格式: metainformation
                    elif "metainformation" in gi:
                        meta = gi.get("metainformation", "")
                        m = re.search(r'Model:\s*([^,\n]+)', meta)
                        if m:
                            model = m.group(1).strip()
                    seed = gi.get("seed", 0)
            elif "imagePanels" in item:
                panel = item.get("imagePanels", [{}])[0]
                prompt = panel.get("prompt", "")
                gen_images = panel.get("generatedImages", [{}])[0]
                model = item.get("genInfo", {}).get("modelInput", {}).get("modelNameType", "")
                seed = gen_images.get("seed", 0)

            conn.execute("INSERT OR REPLACE INTO images VALUES (?,?,?,?,?,?,?,?)",
                (hash_id, source, created_at, img_url, prompt, model, seed, img_html))
            count += 1
        print(f"  {source} 导入完成: {count} 条")

    conn.commit()
    conn.close()
    print("全部导入完成")

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
.header{padding:24px 20px 8px;text-align:center}
.header h1{font-size:1.8em}
.header p{color:#94a3b8;margin-top:5px;font-size:.9em}
.toolbar{display:flex;flex-direction:column;align-items:center;gap:12px;padding:0 20px 16px}
.search-row{display:flex;gap:10px;align-items:center}
.search-row input{padding:10px 15px;border-radius:10px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;width:280px;font-size:.95em;outline:none;transition:border .2s}
.search-row input:focus{border-color:#6366f1}
.search-row button{padding:10px 20px;border-radius:10px;border:none;background:#6366f1;color:#fff;cursor:pointer;font-size:.95em;font-weight:500;transition:background .2s}
.search-row button:hover{background:#818cf8}
.filter-row{display:flex;gap:8px;flex-wrap:wrap;justify-content:center}
.filter-group{display:flex;align-items:center;gap:6px;background:#1e293b;border-radius:20px;padding:4px 4px 4px 14px}
.filter-group .filter-label{font-size:.7em;color:#64748b;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
.filter-group .filter-tags{display:flex;gap:4px;flex-wrap:wrap}
.filter-tag{padding:5px 12px;border-radius:14px;border:none;cursor:pointer;font-size:.78em;background:transparent;color:#94a3b8;transition:all .2s;white-space:nowrap}
.filter-tag:hover{background:rgba(99,102,241,.2);color:#c7d2fe}
.filter-tag.active{background:#6366f1;color:#fff}
.clear-btn{background:transparent;border:1px solid #334155;color:#64748b;padding:4px 10px;border-radius:12px;cursor:pointer;font-size:.7em;transition:all .2s}
.clear-btn:hover{border-color:#ef4444;color:#ef4444}
.grid{columns:4 260px;gap:12px;padding:0 12px 12px}
.card{break-inside:avoid;margin-bottom:12px;background:#1e293b;border-radius:12px;overflow:hidden;transition:transform .2s;position:relative}
.card:hover{transform:scale(1.02)}
.card img{width:100%;display:block;border-radius:12px 12px 0 0}
.card .info{padding:12px;cursor:pointer}
.card .prompt{font-size:.8em;color:#cbd5e1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:8px;line-height:1.45}
.card .meta{font-size:.7em;color:#64748b;display:flex;justify-content:space-between}
.card .source-badge{position:absolute;top:8px;left:8px;background:rgba(99,102,241,.85);color:#fff;font-size:.65em;padding:3px 7px;border-radius:5px;z-index:10;backdrop-filter:blur(4px)}
.loading{text-align:center;padding:20px;color:#64748b}
.lightbox{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.92);z-index:1000;display:none;justify-content:center;align-items:center;flex-direction:column}
.lightbox.active{display:flex}
.lightbox img{max-height:85vh;max-width:95vw;border-radius:10px}
.lightbox .lb-id{color:#fff;margin-top:15px;font-size:14px;background:rgba(255,255,255,0.1);padding:8px 16px;border-radius:8px}
.lightbox .lb-prompt{color:#ccc;font-size:13px;max-width:80vw;margin-top:10px;text-align:center;line-height:1.4;cursor:pointer;padding:8px 12px;border-radius:8px;transition:background .2s}
.lightbox .lb-prompt:hover{background:rgba(255,255,255,0.1)}
.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#6366f1;color:#fff;padding:12px 24px;border-radius:8px;font-size:14px;z-index:9999;opacity:0;transition:opacity .3s}
.toast.show{opacity:1}
@media(max-width:768px){.grid{columns:2 1fr}.search-row input{width:200px}}
</style>
</head>
<body>
<div class="header"><h1>🖼️ AI Gallery</h1><p id="count"></p></div>
<div class="toolbar">
    <div class="search-row">
        <input type="text" id="s" placeholder="搜索 prompt...">
        <button onclick="search()">搜索</button>
    </div>
    <div class="filter-row">
        <div class="filter-group">
            <span class="filter-label">数据源</span>
            <div class="filter-tags" id="source-tags"></div>
        </div>
        <div class="filter-group">
            <span class="filter-label">模型</span>
            <div class="filter-tags" id="model-tags"></div>
        </div>
    </div>
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
let page=0,loading=false,all=[],searchQuery='',lbIdx=-1,activeSources=[],activeModels=[];
let touchStartY=0;

function showToast(){let t=document.getElementById('toast');t.classList.add('show');clearTimeout(t._timeout);t._timeout=setTimeout(function(){t.classList.remove('show')},2000)}
function copyPrompt(){let d=all[lbIdx];if(d&&d.prompt){navigator.clipboard.writeText(d.prompt).then(function(){showToast()})}}
function showLightbox(idx){lbIdx=idx;let d=all[idx];document.getElementById('lb-img').src=d.image_url;document.getElementById('lb-id').innerText=(d.source||'')+' | ID: '+d.hash_id;document.getElementById('lb-prompt').innerText=d.prompt||'';document.getElementById('lb').classList.add('active')}
document.getElementById('lb-img').addEventListener('touchstart',function(e){touchStartY=e.touches[0].clientY;e.stopPropagation()});
document.getElementById('lb-img').addEventListener('touchend',function(e){let d=e.changedTouches[0].clientY-touchStartY;if(d>50&&lbIdx>0)showLightbox(lbIdx-1);if(d<-50&&lbIdx<all.length-1)showLightbox(lbIdx+1);e.stopPropagation()});

function render(items,append){
    let g=document.getElementById('g');
    if(!append){g.innerHTML='';lbIdx=-1;}
    items.forEach(function(d,i){
        let c=document.createElement('div');c.className='card';
        c.innerHTML='<div class="source-badge">'+d.source+'</div><img src="'+d.image_url+'" loading="lazy" onerror="this.style.display=\\'none\\'"><div class="info"><div class="prompt">'+(d.prompt||'')+'</div><div class="meta"><span>'+(d.model||'')+'</span><span>Seed:'+(d.seed||'')+'</span></div></div>';
        c.querySelector('.prompt').addEventListener('click',function(e){e.stopPropagation();navigator.clipboard.writeText(d.prompt).then(function(){showToast()})});
        c.querySelector('img').addEventListener('click',function(){showLightbox(append?all.length-items.length+i:i)});
        g.appendChild(c);
    });
}

function buildParams(){
    let p=[];
    if(searchQuery) p.push('search='+encodeURIComponent(searchQuery));
    if(activeSources.length>0) p.push('sources='+activeSources.join(','));
    if(activeModels.length>0) p.push('models='+activeModels.join(','));
    return p.length>0?'&'+p.join('&'):'';
}

async function load(reset){
    if(loading)return;loading=true;
    if(reset){page=0;all=[];document.getElementById('g').innerHTML='';}
    let url='/api/images?page='+page+buildParams();
    let res=await fetch(url,{credentials:'include'});
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

function toggleSource(src){let i=activeSources.indexOf(src);if(i>=0)activeSources.splice(i,1);else activeSources.push(src);renderTags('source');load(true)}
function toggleModel(m){let i=activeModels.indexOf(m);if(i>=0)activeModels.splice(i,1);else activeModels.push(m);renderTags('model');load(true)}

function renderTags(type){
    let container=document.getElementById(type+'-tags');
    let activeArr=type==='source'?activeSources:activeModels;
    container.querySelectorAll('.filter-tag').forEach(function(t){t.classList.toggle('active',activeArr.length===0||activeArr.includes(t.dataset.value))});
    if(activeArr.length===0){let all=container.querySelector('.filter-tag');if(all)all.classList.add('active')}
}

function loadFilters(){
    fetch('/api/filters',{credentials:'include'}).then(r=>r.json()).then(function(data){
        ['source','model'].forEach(function(type){
            let container=document.getElementById(type+'-tags');
            container.innerHTML='';
            let values=type==='source'?data.sources:data.models;
            let allBtn=document.createElement('button');allBtn.className='filter-tag active';allBtn.dataset.value='';allBtn.innerText='全部';
            allBtn.onclick=function(){if(type==='source'){activeSources=[]}else{activeModels=[]}renderTags(type);load(true)};
            container.appendChild(allBtn);
            values.forEach(function(v){
                let btn=document.createElement('button');btn.className='filter-tag active';btn.dataset.value=v;btn.innerText=v;
                btn.onclick=function(){if(type==='source')toggleSource(v);else toggleModel(v)};
                container.appendChild(btn);
            });
        });
    });
}

loadFilters();
load(true);
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML)

@app.get("/api/images")
async def get_images(page: int = Query(0), search: str = Query(""), limit: int = Query(20),
                     sources: str = Query(""), models: str = Query("")):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    source_list = [s.strip() for s in sources.split(",") if s.strip()] if sources else []
    model_list = [m.strip() for m in models.split(",") if m.strip()] if models else []

    where_parts = []
    params = []

    if search:
        words = search.strip().split()
        word_clauses = []
        for w in words:
            if re.search(r'[a-zA-Z]', w):
                word_clauses.append("prompt REGEXP ?")
                params.append(r'\b' + re.escape(w) + r'\b')
            else:
                word_clauses.append("prompt LIKE ?")
                params.append(f"%{w}%")
        where_parts.append("(" + " AND ".join(word_clauses) + ")")

    if source_list:
        placeholders = ",".join(["?" for _ in source_list])
        where_parts.append(f"source IN ({placeholders})")
        params.extend(source_list)

    if model_list:
        placeholders = ",".join(["?" for _ in model_list])
        where_parts.append(f"model IN ({placeholders})")
        params.extend(model_list)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    total = conn.execute(f"SELECT COUNT(*) as t FROM images WHERE {where_clause}", params).fetchone()["t"]
    rows = conn.execute(
        f"SELECT * FROM images WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, page * limit]
    ).fetchall()
    conn.close()

    return {"total": total, "page": page, "has_more": (page + 1) * limit < total, "images": [dict(r) for r in rows]}

@app.get("/api/filters")
async def get_filters():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT DISTINCT source FROM images ORDER BY source")
    sources = [r[0] for r in cursor.fetchall()]
    cursor = conn.execute("SELECT DISTINCT model FROM images WHERE model != '' ORDER BY model")
    models = [r[0] for r in cursor.fetchall()]
    conn.close()
    return {"sources": sources, "models": models}