import os
import sqlite3
import requests
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

JSON_URL = "https://raw.githubusercontent.com/michsiu/liblib/main/WhiskTasks/WhiskTasks.json"
DB_PATH = "/tmp/gallery.db"

app = FastAPI()


# ================= 数据库 =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            image_url TEXT,
            prompt TEXT
        )
    """)
    conn.commit()
    conn.close()


def load_data():
    if os.path.exists(DB_PATH):
        return

    resp = requests.get(JSON_URL)
    if resp.status_code != 200:
        return

    data = resp.json()
    conn = sqlite3.connect(DB_PATH)

    for k, v in data.items():
        panel = v.get("imagePanels", [{}])[0]
        conn.execute(
            "INSERT OR REPLACE INTO images VALUES (?,?,?,?)",
            (
                k,
                v.get("createdAt", ""),
                v.get("imageUrl", ""),
                panel.get("prompt", "")
            )
        )

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()
    load_data()


# ================= API =================
@app.get("/api/images")
def get_images(page: int = 0, limit: int = 20, search: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if search:
        rows = conn.execute("""
            SELECT * FROM images
            WHERE prompt LIKE ?
            LIMIT ? OFFSET ?
        """, (f"%{search}%", limit, page * limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM images
            LIMIT ? OFFSET ?
        """, (limit, page * limit)).fetchall()

    conn.close()
    return {"images": [dict(r) for r in rows]}


# ================= 前端 =================
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {background:#111;color:#fff;font-family:sans-serif;}
.grid {display:grid;grid-template-columns:repeat(auto-fill,200px);gap:10px;}
.img-content {position:relative;}
.img-content img {width:100%;border-radius:10px;cursor:pointer;}
.image-info {display:none;position:absolute;bottom:0;background:rgba(0,0,0,0.7);width:100%;}
.img-content.show-info .image-info {display:block;}
#overlay {
    position:fixed;top:0;left:0;width:100%;height:100%;
    background:rgba(0,0,0,0.9);
    display:none;align-items:center;justify-content:center;
}
#overlay img {max-width:90%;max-height:90%;}
</style>
</head>

<body>

<input id="search" placeholder="搜索">
<button onclick="doSearch()">搜索</button>

<div id="grid" class="grid"></div>

<div id="overlay">
    <img id="overlayImage">
</div>

<script>

let page=0;
let keyword="";
let loading=false;

let images=[], imageInfos=[];

const overlay=document.getElementById("overlay");
const overlayImage=document.getElementById("overlayImage");

overlay.onclick=()=>overlay.style.display="none";

function escapeHTML(str){
    return str.replace(/[&<>"']/g, m => ({
        "&":"&amp;","<":"&lt;",">":"&gt;",
        '"':"&quot;","'":"&#39;"
    }[m]));
}

function buildCard(item){
    return `
    <div class="img-content">
        <img data-src="${item.image_url}">
        <div class="image-info">${escapeHTML(item.prompt||"")}</div>
    </div>
    `;
}

async function load(){
    if(loading) return;
    loading=true;

    let res=await fetch(`/api/images?page=${page}&search=${keyword}`);
    let data=await res.json();

    let grid=document.getElementById("grid");

    data.images.forEach(item=>{
        let div=document.createElement("div");
        div.innerHTML=buildCard(item);
        grid.appendChild(div);
    });

    images=document.querySelectorAll(".img-content img");
    imageInfos=document.querySelectorAll(".image-info");

    images.forEach((img,i)=>{
        img.src=img.dataset.src;

        img.onclick=()=>{
            overlay.style.display="flex";
            overlayImage.src=img.src;
        };

        img.parentElement.onclick=(e)=>{
            if(e.target===img){
                img.parentElement.classList.toggle("show-info");
            }
        };
    });

    page++;
    loading=false;
}

function doSearch(){
    keyword=document.getElementById("search").value;
    page=0;
    document.getElementById("grid").innerHTML="";
    load();
}

load();

</script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML