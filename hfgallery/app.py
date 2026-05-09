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

HTML = r"""<meta charset="utf-8">
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Gallery</title>
    <style>
        .grid-item .img-content {
            width: 100%;
            /* 图片宽度为父元素宽度的 100% */
            height: auto;
            /* 让高度自适应以保持宽高比 */
            border-radius: 10px;
            /* 设置圆角半径为10px */
            box-shadow: 0px 5px 10px rgba(0, 0, 0, 0.3);
            /* 底部投影 */

            cursor: pointer;
            /* 鼠标指针样式为手型 */
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
           0% { 
               opacity: 0;
               transform: translateY(-20px) scale(0.5);
           }
          50% {
              opacity: 0.8;
              transform: translateY(5px) scale(1.01);
          }
          100% {
              opacity: 1;
              transform: none;
              }
          }



        .grid-item .hidden-info {
            display: none;
        }

        .grid-item .bottomInfo {
            color: white;
            font-family: siyuanmid;
            font-size: 12px;
            background-color: rgba(0, 0, 0, 0.35);
            width: 94%;
            max-height: 40%;
            overflow: hidden;
            position: absolute;
            bottom: 0;
            text-align: center;
            padding: 0 3% 0 3%;
            border-radius: 0 0 10px 10px;
        }

        .grid-item .topRightInfo {
            color: white;
            font-family: siyuanxlight;
            font-size: 12px;
            background-color: rgba(0, 0, 0, 0.35);
            border-radius: 10px;
            position: absolute;
            right: 3px;
            top: 3px;
            padding: 0 3px 0 3px;
            margin: 0;
        }



        @keyframes fadeIn {
            from {
                opacity: 0;
            }

            to {
                opacity: 1;
            }
        }

        @keyframes fadeOut {
            from {
                opacity: 1;
            }

            to {
                opacity: 0;
            }
        }

        @keyframes zoomIn {
            from {
                transform: scale(0.5);
            }

            to {
                transform: scale(1);
            }
        }

        @keyframes zoomOut {
            from {
                transform: scale(1);
                opacity: 1;
            }

            to {
                transform: scale(0.5) translateY(-300px);
                opacity: 0;
            }
        }

        .image-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            -webkit-backdrop-filter: blur(10px);
            background-color: rgba(0, 0, 0, 0.7);
            /* 半透明背景 */
            z-index: 1000;
            /* 确保覆盖在其他内容之上 */
            display: none;
            justify-content: center;
            align-items: center;
            flex-direction: column;

        }

        .image-overlay.active {
            display: flex;
        }

        .image-overlay.fadeIn {
            animation: fadeIn 0.5s ease forwards;
        }

        .image-overlay.fadeOut {
            animation: fadeOut 0.5s ease forwards;
        }

        /* 应该是这个无意之中解决了infosvg查看信息后的缩放与滑动翻页的动画冲突，这样即使在查看信息的状态下滑动翻页依旧不会有动画冲突，原理未知 */
        .image-overlay #overlayimage-container.active {
            display: flex;
            position: absolute;
            max-height: auto;
            max-width: auto;
            justify-content: center;
            align-items: center;
            transition: transform 0.5s ease;
        }

        .image-overlay #overlayimage-container #overlay-image {
            /* 与容器的限高保持一致，也只能通过这种方式给图片限高；同时解决了信息图标总是偏移的问题,但还是无法解决动画宽度偏移的问题 */
            max-height: 95vh;
            /* 宽度撑满容器 */
            /* 宽度原本想设置成撑满容器的100%,但是在手机上过窄图片转为宽图片会发生图片位移,所以还是改成95vw */
            max-width: 95vw;
            border-radius: 10px;
            transition: transform 0.5s ease;
            /* transform: scale(1); */
        }

        .image-overlay #overlayimage-container #overlay-image.zoomOut {
            animation: zoomOut 0.5s ease forwards;
            /* 应用缩小效果 */
        }

        .image-overlay #overlayimage-container #overlay-image.zoomIn {
            animation: zoomIn 0.5s ease forwards, fadeIn 0.3s ease forwards;
        }

        .image-overlay #overlayimage-container #overlay-infosvg {
            width: 7%;
            position: absolute;
            top: 7px;
            left: 7px;
            cursor: pointer;
            z-index: 1;
        }

        .image-overlay #overlayimage-container #overlay-infosvg.fadeIn {
            animation: fadeIn 0.5s ease forwards;
        }

        .image-overlay #overlayimage-container #overlay-infosvg.fadeOut {
            animation: fadeOut 0.5s ease forwards;
        }

        @keyframes overlayFadeInOut {
            0% {
                opacity: 1
            }

            50% {
                opacity: 0
            }

            100% {
                opacity: 1
            }
        }

        .image-overlay #overlayimage-container #overlay-infosvg.overlayFadeInOut {
            animation: overlayFadeInOut 0.75s ease forwards;
        }



        @keyframes nextPhotoChange {
            0% {
                opacity: 1;
                transform: scale(1);
            }

            50% {
                opacity: 0;
                transform: scale(0.3) translateY(-300px);
            }

            100% {
                opacity: 1;
                transform: scale(1) translateY(0px);
            }
        }

        @keyframes prevPhotoChange {
            0% {
                opacity: 1;
                transform: scale(1);
            }

            50% {
                opacity: 0;
                transform: scale(0.3) translateY(300px);
            }

            100% {
                opacity: 1;
                transform: scale(1) translateY(0px);
            }
        }


        .nextPhotoChange {
            animation: nextPhotoChange 0.75s ease-in-out forwards;
        }

        .prevPhotoChange {
            animation: prevPhotoChange 0.75s ease-in-out forwards;
        }

        @keyframes colorChange {
            0% {
                background-color: rgb(110, 114, 114, 0.5);
            }

            /* 初始颜色 */
            50% {
                background-color: rgba(184, 188, 188, 0.8);
            }

            /* 中间颜色 */
            100% {
                background-color: rgb(110, 114, 114, 0.5);
            }

            /* 回到初始颜色 */
        }

        .colorChange {
            animation: colorChange 0.5s forwards;
        }


        #overlay-id {
            position: absolute;
            max-width: 80%;
            bottom: 30px;
            z-index: 1;
            cursor: pointer;

            margin-top: 10px;
            margin-bottom: 10px;
            padding: 10px;

            color: #fff;
            font-size: 15px;
            font-family: siyuanmid;

            border-radius: 10px;
            border: 1px solid rgba(198, 202, 202, 0.5);
            background: rgb(110, 114, 114, 0.5);

            transition: 0.5s;

        }


        .fadeIn {
            animation: fadeIn 0.5s ease forwards;
        }

        .fadeOut {
            animation: fadeOut 0.5s ease forwards;
        }





        /* overlay图标点击显示图片信息*/

        /* 显示图片信息文字部分处理 */
        #overlay-info p {
            margin-top: 0;
        }

        #overlay-info {
            color: #fff;
            font-size: 15px;
            font-family: siyuanmid;
            line-height: 1.4;
            border-radius: 10px;
            border: 1px;
            -webkit-backdrop-filter: blur(10px);
            background: rgb(110, 114, 114, 0.5);
            z-index: 2000;

            display: flex;
            align-items: center;
            text-align: left;
            flex-direction: column;

            word-wrap: break-word;
            word-break: break-all;
            overflow: auto;

            padding: 10px;
            position: absolute;

            /* top的数值是100%-（图片容器缩放的一半加上平移的距离）再加上一点点，对应的height是100%-top */
            top: 72%;
            /* 固定宽高度，实现抽卡样式,，但是无法适配不同的设备，可能要用script计算才能实现 */
            height: 35%;
            width: 80%;

            transform: translateY(100px) scale(0);
            transition: 0.5s ease;
        }

        /* @keyframes bottomSlideIn{
        0%{transform:  translateY(100px) scale(0);}
        100%{transform: translateY(0) scale(1);}
    }
    .bottomSlideIn{
        animation: bottomSlideIn 0.5s ease
    }

    @keyframes bottomSlideOut{
        0%{transform: translateY(0) scale(1);}
        100%{transform:  translateY(100px) scale(0);}
        
    }
    .bottomSlideOut{
        animation: bottomSlideOut 0.5s ease
    } */

        .show-text#overlay-info {

            transform: translateY(0) scale(1);
            transition: 0.5s ease;
            /* opacity:1;
        transform: translateY(0) scale(1); */
            /* 和原始状态的transition同理修改 */

        }

        /* 显示图片信息图片部分处理 */
        /* 这个才是解决缩放冲突的关键，container缩放而不是图片缩放，这样就不会和infosvg触发的图片缩放冲突了 */
        #overlayimage-container.show-text {
            transform: translateY(-15%) scale(0.7);
            transition: transform 0.5s ease;
        }


        .show-fulltext#overlay-info {
            /* 固定宽高度 */
            padding: 2.5vw;
            /* 100-padding x 2 - 和屏幕边缘的距离, padding是包括在宽高度里面，同时要和屏幕边缘保持距离 */
            width: 92vw;
            /* 就是要溢出屏幕，形成抽卡样式 */
            height: 110vh;
            top: 2vh;
            transform: translateY(0);
            transition: 0.5s ease;
        }

        @keyframes overlaySlideChange {
            0% {
                opacity: 1;
                transform: translateY(0);
            }

            50% {
                opacity: 0;
                transform: translateY(50px);
            }

            100% {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .overlaySlideChange {
            animation: overlaySlideChange 0.75s forwards;
        }


        .grid-item #infosvg {
            width: 10%;
            position: absolute;
            top: 3px;
            left: 3px;
            z-index: 1;
            cursor: pointer;
        }


        /* 单个图标点击显示图片信息 */
        .info-overlay p {
            margin-top: 0;
        }

        .info-overlay {
            line-height: 1.4;
            -webkit-backdrop-filter: blur(10px);
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 2000;
            color: #fff;
            font-size: 15px;
            font-family: siyuanmid;

            position: fixed;
            top: 0;
            left: 0;

            display: none;
            justify-content: center;
            align-items: center;
            text-align: left;
            flex-direction: column;
            overflow: auto;
            word-wrap: break-word;
            word-break: break-all;
            animation: fadeIn 0.5s ease forwards;

            height: 100%;
            width: 95vw;
            padding: 2.5vw;
        }

        .info-overlay.active {
            display: flex;
        }

        .info-overlay.fadeOut {
            animation: fadeOut 0.5s ease forwards;
        }
    </style>
</head>

<body>

<div class="header" style="text-align:center;padding:20px">
    <h1 style="font-size:1.8em;margin:0;color:#e2e8f0">🖼️ AI Gallery</h1>
    <p id="count" style="color:#94a3b8">加载中...</p>
</div>
<div class="search-box" style="display:flex;justify-content:center;padding:0 20px 20px;gap:10px">
    <input type="text" id="s" placeholder="搜索 prompt..." style="padding:10px 15px;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;width:300px;font-size:1em">
    <button onclick="searchImages()" style="padding:10px 20px;border-radius:8px;border:none;background:#6366f1;color:#fff;cursor:pointer">搜索</button>
</div>

    <div class="grid-container">

 
 




    </div>



    <div class="image-overlay" id="image-overlay">
        <div id=overlayimage-container>
            <img id="overlay-image">
            <img id="overlay-infosvg" src="">
        </div>
        <div id='overlay-id'></div>
        <div id="overlay-info">
            <div id="overlay-info-content">

            </div>

        </div>


    </div>
    <div class="info-overlay">
        <div id="info-overlay-content">

        </div>

    </div>


    <script src="https://cdn.jsdelivr.net/npm/macy@2"></script>
    <script>
        var macy;
var allData = [];
var searchQuery = '';

function rebuildMacy(){
    if(macy) macy.recalculate(true);
    else macy = Macy({container:'#grid-container',trueOrder:false,waitForImages:false,margin:5,columns:4,breakAt:{1200:3,768:2,480:1}});
}

async function loadAll(){
    var res = await fetch('/api/images?page=0&limit=10000', {credentials:'include'});
    var d = await res.json();
    document.getElementById('count').innerText = '共 '+d.total+' 张';
    allData = d.images;
    renderCards(d.images, false);
}

async function searchImages(){
    searchQuery = document.getElementById('s').value;
    document.getElementById('grid-container').innerHTML = '';
    var url = '/api/images?page=0&limit=10000&search='+encodeURIComponent(searchQuery);
    var res = await fetch(url, {credentials:'include'});
    var d = await res.json();
    document.getElementById('count').innerText = '共 '+d.total+' 张';
    allData = d.images;
    renderCards(d.images, false);
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
    setTimeout(function(){ macy.recalculate(true); 

var images = grid.querySelectorAll('.grid-item .img-content');
var infosvgs = grid.querySelectorAll('#infosvg');
const observer = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // 当元素进入视口时，替换图片地址
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.onload = () => {
                        setTimeout(()=>{
                        img.classList.add('loaded');
                        },100);
                        // 图片加载完成后，重新计算 Macy.js 布局
                       macy.recalculate(true);
                   observer.unobserve(entry.target);
                    };

                };
            });
        } );   

        images.forEach(img => {

                observer.observe(img)
     
            


            img.addEventListener('click', function () {
                overlayImage.src = this.src;
                overlayImage.alt = this.alt;
                overlay.classList.add('active');
                overlay.classList.add('fadeIn');
                overlayImageContainer.classList.add('active');

                // keyframe还是只能配合动画类的方式来使用，不然很容易动画冲突，且移除不会产生回滚效果，前提是最终的动画结果和元素初始状态一致
                overlayImage.classList.add('zoomIn');
                setTimeout(function () {
                    overlayImage.classList.remove('zoomIn');
                }, 500);

                overlayImageId.classList.add('fadeIn');
                setTimeout(function () {
                    overlayImageId.classList.remove('fadeIn');
                }, 500);

                overlayInfosvg.classList.add('fadeIn');
                setTimeout(function () {
                    overlayInfosvg.classList.remove('fadeIn');
                }, 500);

                // 准备好image-overlay所需的id和info
                overlayImageId.innerHTML = this.parentNode.querySelector('.image-id').innerHTML;
                overlayInfoContent.innerHTML = this.parentNode.querySelector('.image-info').innerHTML;
                console.log(overlayImageId.innerHTML + ": " + overlayInfoContent.innerHTML)
            });
        });



        //infosvg启动infoOverlay
        infosvgs.forEach(infosvg => {
            infosvg.src = infosvgSrc;
        });



},500);
}





        const overlay = document.getElementById('image-overlay');
        const overlayImage = document.getElementById('overlay-image');
        const overlayInfo = document.getElementById('overlay-info');
        const overlayInfoContent = document.getElementById('overlay-info-content');
        const overlayImageId = document.getElementById('overlay-id');
        const overlayInfosvg = document.getElementById('overlay-infosvg');
        const overlayImageContainer = document.getElementById('overlayimage-container');

        const infoOverlay = document.querySelector('.info-overlay');
        const infoOverlayContent = document.getElementById('info-overlay-content');

        infosvgSrc =
            "data:image/jpeg;base64,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"
        overlayInfosvg.src = infosvgSrc;


        document.addEventListener('click', function (event) {
            if (event.target.id === 'infosvg') {
                infoOverlay.classList.add('active');
                infoOverlayContent.innerHTML = event.target.parentNode.querySelector('.image-info').innerHTML;
                infoOverlayContent.scrollTop = 0;
                console.log(infoOverlayContent.innerHTML);
            }
        });


        infoOverlay.addEventListener('click', function () {
            infoOverlay.classList.add('fadeOut');
            setTimeout(function () {
                infoOverlay.classList.remove('fadeOut');
                infoOverlay.classList.remove('active');
            }, 500);

        });

        // 只需要给infoOveylay添加停止冒泡的监听事件就可以
        // 当事件在子元素 infoOverlayContent 上触发时，它会自动冒泡到父元素。所以，只需要阻止 infoOverlay 上的 touchmove 事件的默认行为和冒泡，就可以同时影响到子元素。
        // if (event.target === this) {}也是一种有效的阻止事件冒泡的方法:点击infoOverlayContent时，事件确实冒泡到了infoOverlay，但处理函数检查了event.target还想不是infoOverlay本身,于是停止执行
        // inforOverlay加上会影响结束后的跟手状态,所以去掉
        // infoOverlay.addEventListener('touchmove', function (event) {
        //     if (event.target !== infooverlayContent) {
        //         event.stopPropagation();
        //         event.preventDefault();
        //     }
        // });


        overlayInfosvg.addEventListener('click', function () {
            // 阻止事件冒泡到 overlay 元素，不然的话，就要放到img的监听事件里面才不会出现点击overlayinfosvg就导致整个overlay退出，overlayImage的监听事件同理
            event.stopPropagation();
            overlayImageContainer.classList.toggle('show-text');
            overlayInfo.classList.toggle('show-text');
            // onverlayInfo 开启和关闭show-text比较特别，进入的时候可以和进入动画以及container一起进入，但是退出的时候需要先执行退出动画再退出
            if (overlayImageContainer.classList.contains('show-text')) {
                // 开启onverlayInfo show-text并给其添加进入动画
                // overlayInfo.classList.toggle('show-text');
                // overlayInfo.classList.add('bottomSlideIn');
                setTimeout(function () {
                    // overlayInfo.classList.remove('bottomSlideIn');
                }, 500);
                // imageId元素处理
                overlayImageId.classList.add('fadeOut')
            } else {
                closeOverlayInfoShowText()
            }
        });

        function closeOverlayInfoShowText() {
            // 关闭onverlayInfo show-text但是先添加退出动画
            // overlayInfo.classList.add('bottomSlideOut');
            overlayImageContainer.classList.remove('show-text');
            overlayInfo.classList.remove('show-text');
            //注意这里是remove而不是toggle show-fulltext，因为存在没有show-Fulltext到那时有show-text的情况，就是半屏下滑
            overlayInfo.classList.remove('show-fulltext');
            // imageId元素处理
            overlayImageId.classList.remove('fadeOut')
            overlayImageId.classList.add('fadeIn');
            setTimeout(function () {
                // overlayInfo.classList.remove('bottomSlideOut');
                // 关闭onverlayInfo的 showtext

                // imageId元素处理
                overlayImageId.classList.remove('fadeIn');
            }, 500);
        }

        // overlayInfo放大信息页 
        overlayInfo.addEventListener('touchmove', function (e) {
            // 只是阻止touchmove的冒泡，没有阻止click的冒泡，不影响点击的时候就是点击整个overlay
            // 阻止冒泡事件同时也阻止了overlayInfo滚动事件的触发,导致即使内容超过了容器的高度,但是依旧无法滚动,但是不设置又会导致上滑的时候最底层的页面的滚动,暂时没有好的解决办法,只能先这样了
            e.preventDefault(); // 阻止默认滚动行为
            e.stopPropagation(); // 阻止事件冒泡        
        });

        overlayInfo.addEventListener('touchstart', function (e) {
            touchStartY = e.touches[0].clientY;
        });

        overlayInfo.addEventListener('touchend', function (e) {
            touchEndY = e.changedTouches[0].clientY;
            const deltaY = touchEndY - touchStartY;
            // 下滑退出showText
            // 直接共用动画
            if (deltaY > 50) {
                closeOverlayInfoShowText()
            } else if (deltaY < -50) {
                // 上滑放大showText
                // 如果是用toggle而不是add和remove呢，是否又增加了一个新操作状态，就是想要实现的恢复原有半image和半text的状态
                // 但是overlay点击退出的时候似乎又会冲突，所以，overlay点击退出的时候应该是remove就不能再是toggle了，和showText一样
                // 但是有showText没有show-Fulltext的时候又有冲突了，这个时候下滑showText是退出了，但是show-Fulltext反而是增加,所以这里也只能是remove
                // 此外，全屏恢复到半屏的时候，动画转换有些生硬，因为过渡动画只应用到了transform和opacaity而不是全部的转换
                overlayInfo.classList.toggle('show-fulltext');
                // 上滑会导致元素内的文字的滚动,所以加一个回到顶部的操作
                // overlayInfo.scrollTo({top:0,behavior:'smooth'});
            }
        });

        overlay.addEventListener('click', closeOverlay);

        // overlayImage.addEventListener('click', closeOverlay); //放外面，避免重复执行，但是需要使用事件冒泡才能实现放在img监听事件里面一样的效果，即点击该区域不会引发整个overlay的退出，所以，这里没必要添加了
        // overlayImageId.addEventListener('click', closeOverlay);


        let copiedItems = [];


        // 通用复制函数
        document.body.addEventListener('click', function (event) {
            if (event.target.classList.contains('copy')) {
                //阻止冒泡事件失败，原因未知
                event.stopPropagation();
                console.log(event.target);
                 if(!copiedItems.includes(event.target.innerHTML)){
                    copiedItems.push(event.target.innerHTML);
                    navigator.clipboard.writeText(copiedItems);
                    console.log(copiedItems)

                    event.target.classList.add('colorChange')
                    setTimeout(() => {
                        event.target.classList.remove('colorChange')
                    }, 500);
                }
            }
        });

        overlayImageId.addEventListener('click', function () {
            if (!copiedItems.includes(overlayImageId.innerHTML)) {
                copiedItems.push(overlayImageId.innerHTML);
                console.log(copiedItems)
            }
        });

        function closeOverlay() {
            // 如果应用了show-text及其fulltext的缩放动画，则需先关闭这些动画再延迟执行关闭动画，否则立即执行关闭动画
            if (overlayImageContainer.classList.contains('show-text')) {
                closeOverlayInfoShowText()
                setTimeout(function () {
                    applyCloseAnimation();
                }, 500); // 假设缩放动画持续 0.5 秒
            } else {
                applyCloseAnimation();
            }
        }
        // 执行关闭动画
        function applyCloseAnimation() {
            navigator.clipboard.writeText(copiedItems)
            overlayImage.classList.add('zoomOut');
            overlay.classList.add('fadeOut');

            // 在关闭动画完成后重置类
            setTimeout(function () {
                overlayImage.classList.remove('zoomOut');
                overlay.classList.remove('fadeOut');
                overlay.classList.add('fadeIn');
                overlay.classList.remove('active');
                overlayImageId.classList.remove('fadeOut');
                overlayImageContainer.classList.remove('active');
            }, 600); // 假设动画持续 0.5 秒
        }


        //照片切换
        overlayImage.addEventListener('touchmove', function (e) {
            // 阻止默认滚动行为
            e.preventDefault();
            // 阻止事件冒泡
            e.stopPropagation();
        });

        let touchStartY = 0;
        let touchEndY = 0;

        overlayImage.addEventListener('touchstart', function (e) {
            touchStartY = e.touches[0].clientY;
        });

        overlayImage.addEventListener('touchend', function (e) {
            touchEndY = e.changedTouches[0].clientY;
            const deltaY = touchEndY - touchStartY;

            if (deltaY > 50) {
                slidePrevImage();
                // 向下滑动，显示上一张图片
                const prevImage = getPrevImage(overlayImage.src);
                const prevId = getPrevId(overlayImageId.innerHTML);
                const prevInfo = getPrevInfo(overlayInfoContent.innerHTML);

                if (prevImage) {
                    //当前图片淡出后再切换图片,所以时间设置动画时间的一半
                    setTimeout(function () {
                        overlayImage.src = prevImage.src;
                        overlayImage.alt = prevImage.alt;
                        overlayImageId.innerHTML = prevId.innerHTML
                        overlayInfoContent.innerHTML = prevInfo.innerHTML
                    }, 325);
                }
            } else if (deltaY < -50) {
                slideNextImage();
                // 向上滑动，显示下一张图片
                const nextImage = getNextImage(overlayImage.src);
                const nextId = getNextId(overlayImageId.innerHTML);
                const nextInfo = getNextInfo(overlayInfoContent.innerHTML);
                if (nextImage) {
                    //注意延迟时间,当前图片淡出后再切换图片
                    setTimeout(function () {
                        overlayImage.src = nextImage.src;
                        overlayImage.alt = nextImage.alt;
                        overlayImageId.innerHTML = nextId.innerHTML
                        overlayInfoContent.innerHTML = nextInfo.innerHTML
                    }, 325);
                }
            }

        });

        function getPrevId(currentId) {
            const currentIdIndex = Array.from(imageIds).findIndex(info => info.innerHTML === currentId);

            if (currentIdIndex > 0) {
                return imageIds[currentIdIndex - 1];
            } else {
                return null;
            }
        }

        function getNextId(currentId) {
            const currentIdIndex = Array.from(imageIds).findIndex(info => info.innerHTML === currentId);

            if (currentIdIndex < imageIds.length - 1) {
                return imageIds[currentIdIndex + 1];
            } else {
                return null;
            }
        }

        function getPrevInfo(currentTxt) {
            const currentInfoIndex = Array.from(imageInfos).findIndex(info => info.innerHTML === currentTxt);

            if (currentInfoIndex > 0) {
                return imageInfos[currentInfoIndex - 1];
            } else {
                return null;
            }
        }

        function getNextInfo(currentTxt) {
            const currentInfoIndex = Array.from(imageInfos).findIndex(info => info.innerHTML === currentTxt);

            if (currentInfoIndex < imageInfos.length - 1) {
                return imageInfos[currentInfoIndex + 1];
            } else {
                return null;
            }
        }


        function getPrevImage(currentSrc) {
            const currentImageIndex = Array.from(images).findIndex(img => img.src === currentSrc);
            if (currentImageIndex > 0) {
                return images[currentImageIndex - 1];
            } else {
                return null;
            }
        }

        function getNextImage(currentSrc) {
            const currentImageIndex = Array.from(images).findIndex(img => img.src === currentSrc);
            if (currentImageIndex < images.length - 1) {
                return images[currentImageIndex + 1];
            } else {
                return null;
            }
        }

        function slideNextImage() {
            overlayImage.classList.add('nextPhotoChange');
            overlayInfosvg.classList.add('overlayFadeInOut');
            overlayImageId.classList.add('colorChange');
            if (overlayImageContainer.classList.contains('show-text')) {
                overlayInfo.classList.add('overlaySlideChange');
                setTimeout(function () {
                    overlayInfo.classList.remove('overlaySlideChange');
                }, 750);
            }
            setTimeout(function () {
                overlayImage.classList.remove('nextPhotoChange');
                overlayInfosvg.classList.remove('overlayFadeInOut');
                overlayImageId.classList.remove('colorChange');
            }, 750);
        }

        function slidePrevImage() {
            overlayImage.classList.add('prevPhotoChange');
            overlayInfosvg.classList.add('overlayFadeInOut');
            overlayImageId.classList.add('colorChange');
            if (overlayImageContainer.classList.contains('show-text')) {
                overlayInfo.classList.add('overlaySlideChange');
                setTimeout(function () {
                    overlayInfo.classList.remove('overlaySlideChange');
                }, 750);
            }
            setTimeout(function () {
                overlayImage.classList.remove('prevPhotoChange');
                overlayInfosvg.classList.remove('overlayFadeInOut');
                overlayImageId.classList.remove('colorChange');
            }, 750);
        }
loadAll()
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