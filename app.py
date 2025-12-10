import streamlit as st
import folium
from folium.plugins import BeautifyIcon, DivIcon
from streamlit_folium import st_folium
import math
import urllib.request
import re
import datetime

# --- Streamlit ページ設定 ---
st.set_page_config(page_title="AeroSpotter", layout="wide", page_icon="✈️")

st.title("✈️ AeroSpotter")
st.caption("風を読んで、最適な飛行機撮影スポットを見つけるツール")

# --- ユーザー設定 (サイドバー) ---
target_airport = st.sidebar.selectbox(
    "空港を選択してください",
    ("RJTT", "RJAA"),
    format_func=lambda x: "羽田空港 (RJTT)" if x == "RJTT" else "成田空港 (RJAA)"
)

# --- 1. 共通計算エンジン ---
aircraft_specs = { "B737": 34, "B777": 38, "A350": 38 }

def get_metar(code):
    try:
        # キャッシュ無効化などの工夫は割愛しシンプルに取得
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{code}.TXT"
        with urllib.request.urlopen(url) as response:
            return response.read().decode('utf-8').split('\n')[1]
    except: return None

def parse_metar(text):
    w_match = re.search(r'([0-9]{3})([0-9]{2,3})KT', text)
    wdir = int(w_match.group(1)) if w_match else 0
    wspd = int(w_match.group(2)) if w_match else 0
    if "CAVOK" in text: vis = 9999; clg = 9999
    else:
        v_match = re.search(r'\s([0-9]{4})\s', text); vis = int(v_match.group(1)) if v_match else 9999
        cld = re.findall(r'(BKN|OVC)([0-9]{3})', text)
        clg = min([int(c[1])*100 for c in cld]) if cld else 9999
    return wdir, wspd, vis, clg

def calc_wind(wdir, wspd, rwy_hdg):
    rad = math.radians(wdir - rwy_hdg)
    return wspd * math.cos(rad), wspd * math.sin(rad)

def get_dist_point(start, hdg, dist_km):
    R = 6378.1; brng = math.radians(hdg); d = dist_km
    lat1 = math.radians(start[0]); lon1 = math.radians(start[1])
    lat2 = math.asin(math.sin(lat1)*math.cos(d/R) + math.cos(lat1)*math.sin(d/R)*math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1), math.cos(d/R)-math.sin(lat1)*math.sin(lat2))
    return [math.degrees(lat2), math.degrees(lon2)]

def get_judgment(cw):
    res = []
    for n, l in aircraft_specs.items():
        res.append(f"{'✅' if abs(cw)<=l else '❌'} {n}")
    return "<br>".join(res)

# --- 2. 空港データベース ---
airports_db = {
    "RJAA": {
        "name": "成田国際空港",
        "center": [35.770, 140.385],
        "runways": {
            "RWY 34L": {"coords": [[35.743484, 140.390611], [35.773845, 140.368696]], "hdg": 335, "thr": [35.743484, 140.390611]},
            "RWY 16R": {"coords": [[35.773845, 140.368696], [35.743484, 140.390611]], "hdg": 155, "thr": [35.773845, 140.368696]},
            "RWY 34R": {"coords": [[35.786313, 140.391765], [35.804654, 140.378529]], "hdg": 335, "thr": [35.786313, 140.391765]},
            "RWY 16L": {"coords": [[35.804654, 140.378529], [35.786313, 140.391765]], "hdg": 155, "thr": [35.804654, 140.378529]},
        },
        "spots": [
            {"name": "十余三東雲の丘", "loc": [35.802184, 140.375859], "target": ["RWY 16L"], "desc": "16L着陸機、34R離陸機"},
            {"name": "三里塚さくらの丘", "loc": [35.741795, 140.384791], "target": ["RWY 34L"], "desc": "34Lエンド南側"},
            {"name": "ひこうきの丘", "loc": [35.738273, 140.391372], "target": ["RWY 34L"], "desc": "34L着陸大迫力"}
        ]
    },
    "RJTT": {
        "name": "羽田空港",
        "center": [35.545, 139.790],
        "runways": {
            "RWY 34L": {"coords": [[35.536939, 139.785442], [35.555724, 139.772081]], "hdg": 337, "thr": [35.536939, 139.785442]},
            "RWY 34R": {"coords": [[35.542632, 139.803064], [35.564966, 139.787195]], "hdg": 337, "thr": [35.542632, 139.803064]},
            "RWY 16L": {"coords": [[35.564966, 139.787195], [35.542632, 139.803064]], "hdg": 157, "thr": [35.564966, 139.787195]},
            "RWY 16R": {"coords": [[35.555724, 139.772081], [35.536939, 139.785442]], "hdg": 157, "thr": [35.555724, 139.772081]},
            "RWY 22":  {"coords": [[35.567152, 139.776839], [35.549336, 139.761563]], "hdg": 220, "thr": [35.567152, 139.776839]},
            "RWY 23":  {"coords": [[35.540330, 139.821781], [35.524289, 139.803781]], "hdg": 230, "thr": [35.540330, 139.821781]},
        },
        "spots": [
            {"name": "第1ターミナル", "loc": [35.548805, 139.783696], "target": ["RWY 34L", "RWY 16R"], "desc": "JAL側。富士山"},
            {"name": "第2ターミナル", "loc": [35.551180, 139.788979], "target": ["RWY 34R", "RWY 16L", "RWY 22"], "desc": "ANA側。海"},
            {"name": "第3ターミナル", "loc": [35.545342, 139.769760], "target": ["RWY 22", "RWY 16L", "RWY 34L"], "desc": "国際線"},
            {"name": "京浜島つばさ公園", "loc": [35.565182, 139.765535], "target": ["RWY 22"], "desc": "B滑走路南風"},
            {"name": "城南島海浜公園", "loc": [35.577888, 139.784126], "target": ["RWY 22", "RWY 34R"], "desc": "22着陸・34R離陸"},
            {"name": "浮島町公園", "loc": [35.522033, 139.789022], "target": ["RWY 34L", "RWY 05"], "desc": "34Lアプローチ直下"}
        ]
    }
}

# --- 3. メイン処理 ---
data = airports_db.get(target_airport)
metar = get_metar(target_airport)

if data and metar:
    wdir, wspd, vis, clg = parse_metar(metar)
    
    # 撮影条件
    p_stat, p_col, p_msg = "◎ 良好", "green", "視界クリア"
    if vis<5000 or clg<1500: p_stat, p_col, p_msg = "❌ 悪条件", "red", "視界不良/雲低"
    elif vis<8000 or clg<3000: p_stat, p_col, p_msg = "△ 微妙", "orange", "霞/雲あり"

    # サイドバーに気象情報を表示
    st.sidebar.markdown("### 気象情報 (METAR)")
    st.sidebar.markdown(f"**風向風速:** {wdir}° / {wspd}kt")
    st.sidebar.markdown(f"**視程:** {vis}m")
    st.sidebar.markdown(f"**雲底:** {'なし' if clg==9999 else f'{clg}ft'}")
    st.sidebar.markdown(f"**撮影判定:** :{p_col}[{p_stat}]")
    st.sidebar.caption(p_msg)

    m = folium.Map(location=data["center"], zoom_start=12, tiles="CartoDB dark_matter")
    
    # 情報パネル (地図内オーバーレイ)
    arot = (wdir+180)%360
    utc = datetime.datetime.utcnow(); jst = utc + datetime.timedelta(hours=9)
    
    info_html = f"""
    <div style="position:fixed; bottom:20px; right:10px; z-index:1000; background:rgba(255,255,255,0.9); padding:10px; border-radius:8px; font-family:sans-serif; width:150px; font-size:12px;">
        <div style="text-align:center; margin-bottom:5px;"><b>{target_airport} Wind</b></div>
        <div style="display:flex; align-items:center; justify-content:center;">
            <div style="position:relative; width:30px; height:30px; border:2px solid #ccc; border-radius:50%; margin-right:10px;">
                <div style="position:absolute; top:-4px; left:50%; transform:translateX(-50%); font-size:8px;">N</div>
                <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%) rotate({arot}deg); color:#00bfff; font-size:16px;">⬆</div>
            </div>
            <div>{wdir}°<br>{wspd}kt</div>
        </div>
    </div>"""
    m.get_root().html.add_child(folium.Element(info_html))

    # --- 運用判定ロジック分岐 ---
    active_rwys = []
    
    # A. 成田のロジック (風のみ)
    if target_airport == "RJAA":
        for name, rwy in data["runways"].items():
            hw, cw = calc_wind(wdir, wspd, rwy["hdg"])
            if hw >= 0: # 向かい風ならOK
                active_rwys.append(name[:7]) # "RWY 34L"

    # B. 羽田のロジック (風 + 時間)
    elif target_airport == "RJTT":
        hour = jst.hour
        is_north = not (90 <= wdir <= 270) # 簡易的な北風判定
        is_city = (15 <= hour < 19) # 都心ルート時間帯
        
        mode_text = "北風運用" if is_north else ("南風(都心)" if is_city else "南風(基本)")
        st.sidebar.info(f"現在のモード: **{mode_text}**")

        if is_north:
            active_rwys = ["RWY 34L", "RWY 34R"]
        else: # 南風
            if is_city: active_rwys = ["RWY 16L", "RWY 16R"]
            else:       active_rwys = ["RWY 22", "RWY 23"]

    # --- 描画ループ ---
    for name, rwy in data["runways"].items():
        hw, cw = calc_wind(wdir, wspd, rwy["hdg"])
        
        # 判定: active_rwysに含まれているか？
        is_active = False
        for a in active_rwys:
            if a in name: is_active = True
        
        # 追い風チェック
        if is_active and hw < -5: is_active = False 

        col, wgt, op = "gray", 3, 0.5
        status = "Standby"
        
        if is_active:
            col, wgt, op = "#00ff00", 8, 0.9
            status = "Active"
            
            # 進入ライン & アイコン
            app_hdg = rwy["hdg"] + 180
            fp = get_dist_point(rwy["thr"], app_hdg, 10.0)
            folium.PolyLine([rwy["thr"], fp], color="cyan", weight=2, dash_array='10,10', opacity=0.7).add_to(m)
            
            p3 = get_dist_point(rwy["thr"], app_hdg, 3.0)
            folium.Marker(p3, icon=DivIcon(html='<div style="font-size:9pt; color:cyan;">▼300m</div>')).add_to(m)
            
            ip = get_dist_point(rwy["thr"], app_hdg, 0.5)
            rot = rwy["hdg"] - 90
            folium.Marker(ip, icon=BeautifyIcon(icon="plane", icon_shape="marker", border_color="#00ff00", text_color="#00ff00", rotation=rot)).add_to(m)

        pop = f"<b>{name}</b><br>{status}<br>Head:{hw:.1f}kt / Cross:{abs(cw):.1f}kt<br><hr>{get_judgment(cw)}"
        folium.PolyLine(rwy["coords"], color=col, weight=wgt, opacity=op, popup=folium.Popup(pop, max_width=250)).add_to(m)

    # --- スポット描画 ---
    for s in data["spots"]:
        icol, txt = "blue", s["name"]
        hit = False
        for t in s["target"]:
            for a in active_rwys:
                if t in a: hit = True
        if hit:
            icol = "red"; txt += f"<br><b>★チャンス！</b><br>{s['desc']}"
        else:
            txt += f"<br>{s['desc']}"
        folium.Marker(s["loc"], popup=folium.Popup(txt, max_width=200), icon=folium.Icon(color=icol, icon="camera")).add_to(m)

    # Streamlitで地図を表示
    st_folium(m, width=None, height=500)

else:
    st.error("気象データの取得に失敗しました。時間をおいて再読み込みしてください。")