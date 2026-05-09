# ================== 后端 ==================
import os
import sqlite3
import requests
import asyncio
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

JSON_URL = "https://raw.githubusercontent.com/michsiu/liblib/main/WhiskTasks/WhiskTasks.json"
DB_PATH = "/tmp/gallery.db"

app = FastAPI()


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_gallery():
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            hash_id TEXT PRIMARY KEY,
            created_at TEXT,
            image_url TEXT,
            prompt TEXT,
            model TEXT,
            seed INTEGER
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON images(created_at DESC)")

    conn.commit()
    conn.close()


async def load_data():
    try:
        resp = requests.get(JSON_URL)
        if resp.status_code != 200:
            print("加载失败")
            return

        data = resp.json()
        conn = get_conn()

        for hash_id, item in data.items():
            panel = item.get("imagePanels", [{}])[0]
            gen = panel.get("generatedImages", [{}])[0]

            conn.execute("""
                INSERT OR REPLACE INTO images VALUES (?,?,?,?,?,?)
            """, (
                hash_id,
                item.get("createdAt", ""),
                item.get("imageUrl", ""),
                panel.get("prompt", ""),
                item.get("genInfo", {}).get("modelInput", {}).get("modelNameType", ""),
                gen.get("seed", 0),
            ))

        conn.commit()
        conn.close()
        print("✅ 数据加载完成")

    except Exception as e:
        print("❌ 错误:", e)


@app.on_event("startup")
async def startup():
    init_gallery()
    asyncio.create_task(load_data())


@app.get("/api/images")
async def get_images(page: int = 0, search: str = "", limit: int = 20):
    limit = min(limit, 50)
    conn = get_conn()

    if search:
        rows = conn.execute("""
            SELECT * FROM images
            WHERE prompt LIKE ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (f"%{search}%", limit, page * limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM images
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, page * limit)).fetchall()

    conn.close()

    return {
        "images": [dict(r) for r in rows],
        "has_more": len(rows) == limit
    }


# ================== 前端 ==================
HTML = r"""
<meta charset="utf-8">
<html>
<body style="background:#0f172a;color:white">

<h2 style="text-align:center">AI Gallery</h2>

<div style="text-align:center">
<input id="s">
<button onclick="searchImages()">搜索</button>
</div>

<div id="grid-container"></div>
<div id="loadMore" style="height:50px"></div>

<script>

let page = 0;
let loading = false;
let keyword = "";

function escapeHTML(str){
    return str.replace(/[&<>"']/g, m => ({
        "&":"&amp;","<":"&lt;",">":"&gt;",
        '"':"&quot;","'":"&#39;"
    }[m]));
}

async function load(){
    if(loading) return;
    loading = true;

    let url = `/api/images?page=${page}&search=${encodeURIComponent(keyword)}`;
    let res = await fetch(url);
    let data = await res.json();

    let grid = document.getElementById('grid-container');

    data.images.forEach(item=>{
        let div = document.createElement('div');
        div.style.margin = "10px";

        div.innerHTML = `
            <img data-src="${item.image_url}" class="lazy" style="width:200px;border-radius:10px">
            <div>${escapeHTML(item.prompt || "")}</div>
        `;

        grid.appendChild(div);
    });

    lazyLoad();

    if(data.has_more){
        page++;
    }

    loading = false;
}

function searchImages(){
    keyword = document.getElementById("s").value;
    page = 0;
    document.getElementById("grid-container").innerHTML = "";
    load();
}

function lazyLoad(){
    const imgs = document.querySelectorAll("img.lazy");

    const obs = new IntersectionObserver(entries=>{
        entries.forEach(e=>{
            if(e.isIntersecting){
                let img = e.target;
                img.src = img.dataset.src;
                obs.unobserve(img);
            }
        });
    });

    imgs.forEach(i=>obs.observe(i));
}

const observer = new IntersectionObserver(entries=>{
    if(entries[0].isIntersecting){
        load();
    }
});

observer.observe(document.getElementById("loadMore"));

load();

</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=HTML)