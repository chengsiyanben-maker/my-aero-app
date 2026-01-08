import streamlit as st
import folium
from folium.plugins import BeautifyIcon
from folium import DivIcon
from streamlit_folium import st_folium
import math
import urllib.request
import re
import datetime

# --- Streamlit ページ設定 ---
st.set_page_config(page_title="AeroSpotter Pro", layout="wide", page_icon="✈️")

st.title("✈️ AeroSpotter Pro")
st.caption("視程による進入方式（ILS/Visual）自動切替・運用情報詳細表示対応版")

# --- ユーザー設定 ---
target_airport = st.sidebar.selectbox(
    "空港を選択してください",
    ("RJTT", "RJAA"),
    format_func=lambda x: "羽田空港 (RJTT)" if x == "RJTT" else "成田空港 (RJAA)"
)

# --- 1. 計算エンジン ---
aircraft_specs = { "B737": 34, "B777": 38, "A350": 38 }

def get_metar(code):
    try:
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

# --- 太陽位置 ---
def get_sun_azimuth(lat, lon, date_jst):
    date_utc = date_jst - datetime.timedelta(hours=9)
    day_of_year = date_utc.timetuple().tm_yday
    B = 360/365 * (day_of_year - 81) * math.pi / 180
    eot = 9.87 * math.sin(2*B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)
    time_offset = (lon - 135) * 4 
    solar_time_minutes = (date_jst.hour * 60 + date_jst.minute) + eot + time_offset
    hour_angle = (solar_time_minutes / 4 - 180) 
    declination = 23.45 * math.sin(360/365 * (day_of_year - 81) * math.pi / 180) * math.pi / 180
    lat_rad = math.radians(lat)
    dec_rad = declination
    ha_rad = math.radians(hour_angle)
    elevation = math.asin(math.sin(lat_rad)*math.sin(dec_rad) + math.cos(lat_rad)*math.cos(dec_rad)*math.cos(ha_rad))
    azimuth_cos = (math.sin(dec_rad) - math.sin(lat_rad)*math.sin(elevation)) / (math.cos(lat_rad)*math.cos(elevation))
    azimuth_cos = max(-1, min(1, azimuth_cos))
    azimuth_rad = math.acos(azimuth_cos)
    azimuth_deg = math.degrees(azimuth_rad)
    if hour_angle > 0: azimuth_deg = 360 - azimuth_deg
    return azimuth_deg

# --- 2. 空港データベース ---
airports_db = {
    "RJAA": {
        "name": "成田国際空港",
        "center": [35.770, 140.385],
        "runways": {
            "RWY 34L": {"coords": [[35.743484, 140.390611], [35.773845, 140.368696]], "hdg": 335, "thr": [35.743484, 140.390611], "dep_end": [35.773845, 140.368696], "desc_app": "九十九里・千葉市方面から"},
            "RWY 16R": {"coords": [[35.773845, 140.368696], [35.743484, 140.390611]], "hdg": 155, "thr": [35.773845, 140.368696], "dep_end": [35.743484, 140.390611], "desc_app": "霞ヶ浦・茨城方面から"},
            "RWY 34R": {"coords": [[35.786313, 140.391765], [35.804654, 140.378529]], "hdg": 335, "thr": [35.786313, 140.391765], "dep_end": [35.804654, 140.378529], "desc_app": "九十九里・八街方面から"},
            "RWY 16L": {"coords": [[35.804654, 140.378529], [35.786313, 140.391765]], "hdg": 155, "thr": [35.804654, 140.378529], "dep_end": [35.786313, 140.391765], "desc_app": "霞ヶ浦・香取方面から"},
        },
        "custom_routes": {
            "RWY 34L_APP": [[35.60, 140.50], [35.68, 140.45], [35.743484, 140.390611]],
            "RWY 34R_APP": [[35.62, 140.52], [35.70, 140.47], [35.786313, 140.391765]],
            "RWY 16R_APP": [[35.92, 140.28], [35.85, 140.33], [35.773845, 140.368696]],
            "RWY 16L_APP": [[35.95, 140.31], [35.88, 140.35], [35.804654, 140.378529]],
            "RWY 34L_DEP": [[35.773845, 140.368696], [35.82, 140.33], [35.85, 140.25]],
            "RWY 34R_DEP": [[35.804654, 140.378529], [35.85, 140.34], [35.90, 140.30]],
            "RWY 16R_DEP": [[35.743484, 140.390611], [35.70, 140.42], [35.65, 140.50]],
            "RWY 16L_DEP": [[35.786313, 140.391765], [35.74, 140.43], [35.68, 140.52]],
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
            "RWY 34L": {"coords": [[35.536939, 139.785442], [35.555724, 139.772081]], "hdg": 337, "thr": [35.536939, 139.785442], "dep_end": [35.555724, 139.772081], "desc_app": "木更津・東京湾方面から"},
            "RWY 34R": {"coords": [[35.542632, 139.803064], [35.564966, 139.787195]], "hdg": 337, "thr": [35.542632, 139.803064], "dep_end": [35.564966, 139.787195], "desc_app": "北米，ハワイ，北日本（主に新千歳）からの到着便，長距離国際線（北米，ヨーロッパ），北日本（主に新千歳）などへの出発便"},
            "RWY 16L": {"coords": [[35.564966, 139.787195], [35.542632, 139.803064]], "hdg": 157, "thr": [35.564966, 139.787195], "dep_end": [35.542632, 139.803064], "desc_app": "埼玉・都心上空(荒川沿い)から"},
            "RWY 16R": {"coords": [[35.555724, 139.772081], [35.536939, 139.785442]], "hdg": 157, "thr": [35.555724, 139.772081], "dep_end": [35.536939, 139.785442], "desc_app": "埼玉・都心上空(新宿/渋谷)から"},
            "RWY 22":  {"coords": [[35.567152, 139.776839], [35.549336, 139.761563]], "hdg": 220, "thr": [35.567152, 139.776839], "dep_end": [35.549336, 139.761563], "desc_app": "千葉市・東京湾方面から"},
            "RWY 23":  {"coords": [[35.540330, 139.821781], [35.524289, 139.803781]], "hdg": 230, "thr": [35.540330, 139.821781], "dep_end": [35.524289, 139.803781], "desc_app": "木更津・東京湾方面から"},
            "RWY 05":  {"coords": [[35.524289, 139.803781], [35.540330, 139.821781]], "hdg": 50,  "thr": [35.524289, 139.803781], "dep_end": [35.540330, 139.821781], "desc_app": "多摩川河口方面から(離陸専用)"}, 
            "RWY 04":  {"coords": [[35.549336, 139.761563], [35.567152, 139.776839]], "hdg": 40,  "thr": [35.549336, 139.761563], "dep_end": [35.567152, 139.776839], "desc_app": "多摩川方面から(使用頻度低)"}, 
        },
        "custom_routes": {
            # 南風都心ルート (RNAV)
            "RWY 16L_APP": [[35.80, 139.65], [35.73, 139.67], [35.69, 139.70], [35.65, 139.71], [35.62, 139.73], [35.564966, 139.787195]],
            "RWY 16R_APP": [[35.80, 139.64], [35.73, 139.66], [35.69, 139.69], [35.65, 139.70], [35.62, 139.72], [35.555724, 139.772081]],
            # 北風 (東京湾)
            "RWY 34L_APP": [[35.45, 140.00], [35.50, 139.90], [35.536939, 139.785442]],
            "RWY 34R_APP": [[35.40, 139.95], [35.48, 139.85], [35.542632, 139.803064]],
            # 南風 (LDA W等) -> 視程が良い時のみ
            "RWY 22_APP": [[35.60, 140.05], [35.60, 139.90], [35.567152, 139.776839]],
            "RWY 23_APP": [[35.50, 139.95], [35.540330, 139.821781]],

            "RWY 05_DEP": [[35.540330, 139.821781], [35.545, 139.835], [35.540, 139.86], [35.52, 139.89]],
            "RWY 34R_DEP": [[35.564966, 139.787195], [35.58, 139.80], [35.58, 139.85], [35.55, 139.90]],
            "RWY 22_DEP": [[35.549336, 139.761563], [35.53, 139.76], [35.50, 139.80]],
            "RWY 16R_DEP": [[35.536939, 139.785442], [35.50, 139.80], [35.45, 139.82]],
            "RWY 16L_DEP": [[35.542632, 139.803064], [35.50, 139.82], [35.45, 139.85]],
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
    
    # 視程ステータス定義 (5000mを閾値とする)
    VIS_THRESHOLD = 5000
    is_good_vis = (vis >= VIS_THRESHOLD)
    
    p_stat, p_col, p_msg = "◎ 良好", "green", "視界クリア"
    if vis<VIS_THRESHOLD or clg<1500: p_stat, p_col, p_msg = "❌ 悪条件", "red", "視界不良/雲低 (ILS運用推奨)"
    elif vis<8000 or clg<3000: p_stat, p_col, p_msg = "△ 微妙", "orange", "霞/雲あり"

    st.sidebar.markdown("### 気象情報 (METAR)")
    st.sidebar.markdown(f"**風向風速:** {wdir}° / {wspd}kt")
    st.sidebar.markdown(f"**視程:** {vis}m")
    st.sidebar.markdown(f"**撮影判定:** :{p_col}[{p_stat}]")
    if not is_good_vis:
        st.sidebar.warning(f"視程が{VIS_THRESHOLD}m未満のため、ILS（直線）進入を表示します。")

    m = folium.Map(location=data["center"], zoom_start=11, tiles="CartoDB dark_matter")
    
    # 太陽
    utc = datetime.datetime.utcnow()
    jst = utc + datetime.timedelta(hours=9)
    sun_azimuth = get_sun_azimuth(data["center"][0], data["center"][1], jst)
    sun_dist_km = 6.0
    sun_loc = get_dist_point(data["center"], sun_azimuth, sun_dist_km)
    
    folium.PolyLine([data["center"], sun_loc], color="yellow", weight=1, dash_array='5,5', opacity=0.5).add_to(m)
    folium.Marker(sun_loc, icon=BeautifyIcon(icon="sun", text_color="orange", border_color="orange", background_color="transparent", inner_icon_style="font-size:30px;"), tooltip="太陽").add_to(m)

    # 運用ロジック
    active_landing = []
    active_takeoff = []
    
    if target_airport == "RJAA":
        for name, rwy in data["runways"].items():
            hw, cw = calc_wind(wdir, wspd, rwy["hdg"])
            if hw >= 0:
                base_name = name[:7]
                active_landing.append(base_name)
                active_takeoff.append(base_name)

    elif target_airport == "RJTT":
        hour = jst.hour
        is_north = not (90 <= wdir <= 270)
        # ★ 都心ルート判定に視程条件を追加 (視界不良時は都心ルートなし)
        is_city = (15 <= hour < 19) and is_good_vis
        
        mode_text = "北風運用" if is_north else ("南風(都心)" if is_city else "南風(基本)")
        st.sidebar.info(f"運用モード: **{mode_text}**")

        if is_north:
            active_landing = ["RWY 34L", "RWY 34R"]
            active_takeoff = ["RWY 05", "RWY 34R"]
        else:
            if is_city:
                active_landing = ["RWY 16L", "RWY 16R"]
                active_takeoff = ["RWY 16L", "RWY 16R"]
            else:
                active_landing = ["RWY 22", "RWY 23"]
                active_takeoff = ["RWY 16L", "RWY 16R"]

    # 描画ループ
    custom_routes = data.get("custom_routes", {})
    
    for name, rwy in data["runways"].items():
        hw, cw = calc_wind(wdir, wspd, rwy["hdg"])
        is_land = any(a in name for a in active_landing)
        is_dep  = any(a in name for a in active_takeoff)
        if is_land and hw < -5: is_land = False

        col, wgt, op = "gray", 3, 0.5
        
        if is_land or is_dep:
            col, wgt, op = "#00ff00", 6, 0.9
            base_rwy_name = name[:7].strip()
            
            # 方角情報の取得
            desc_app_text = rwy.get("desc_app", "")

            # 1. 着陸ルート (Landing)
            if is_land:
                # ツールチップテキスト作成
                tooltip_text = f"{name} Approach"
                if desc_app_text:
                    tooltip_text += f" ({desc_app_text})"

                app_key = f"{base_rwy_name}_APP"
                use_custom_curve = is_good_vis and (app_key in custom_routes)
                
                if use_custom_curve:
                    # カーブ描画
                    coords = custom_routes[app_key]
                    folium.PolyLine(coords, color="cyan", weight=3, dash_array='10,10', opacity=0.8, tooltip=tooltip_text).add_to(m)
                    
                    icon_loc = coords[0]
                    rot = rwy["hdg"] - 90
                    folium.Marker(icon_loc, icon=BeautifyIcon(icon="plane", icon_shape="marker", border_color="cyan", text_color="cyan", rotation=rot), tooltip=desc_app_text).add_to(m)
                else:
                    # 直線描画 (ILS想定)
                    app_hdg = rwy["hdg"] + 180
                    fp = get_dist_point(rwy["thr"], app_hdg, 12.0) # ILSは長めに12km
                    folium.PolyLine([rwy["thr"], fp], color="cyan", weight=3, dash_array='5,5', opacity=0.8, tooltip=f"{tooltip_text} [ILS]").add_to(m)
                    
                    ip = get_dist_point(rwy["thr"], app_hdg, 0.5)
                    rot = rwy["hdg"] - 90
                    folium.Marker(ip, icon=BeautifyIcon(icon="plane", icon_shape="marker", border_color="cyan", text_color="cyan", rotation=rot), tooltip=desc_app_text).add_to(m)

            # 2. 離陸ルート (Takeoff) - 離陸は視程に関わらずSID(カスタム)優先
            if is_dep:
                dep_key = f"{base_rwy_name}_DEP"
                if dep_key in custom_routes:
                    coords = custom_routes[dep_key]
                    folium.PolyLine(coords, color="orange", weight=3, opacity=0.8, tooltip=f"{name} Departure").add_to(m)
                    icon_loc = coords[-1]
                    rot = rwy["hdg"] - 90
                    folium.Marker(icon_loc, icon=BeautifyIcon(icon="plane", icon_shape="marker", border_color="orange", text_color="orange", rotation=rot)).add_to(m)
                else:
                    # 定義なければ直線
                    dep_pt = get_dist_point(rwy["dep_end"], rwy["hdg"], 10.0)
                    folium.PolyLine([rwy["dep_end"], dep_pt], color="orange", weight=3, opacity=0.8, tooltip=f"{name} Departure").add_to(m)
                    dp_icon = get_dist_point(rwy["dep_end"], rwy["hdg"], 0.5)
                    rot = rwy["hdg"] - 90
                    folium.Marker(dp_icon, icon=BeautifyIcon(icon="plane", icon_shape="marker", border_color="orange", text_color="orange", rotation=rot)).add_to(m)

        # ポップアップ情報の追加
        desc_info = ""
        if "desc_app" in rwy:
            # ラベルを「進入」から「情報」へ変更し、離発着両方の内容に対応
            desc_info = f"<br>情報: {rwy['desc_app']}"
            
        pop = f"<b>{name}</b><br>{'Active' if is_land or is_dep else 'Standby'}{desc_info}<br>Head:{hw:.1f}kt / Cross:{abs(cw):.1f}kt<br><hr>{get_judgment(cw)}"
        folium.PolyLine(rwy["coords"], color=col, weight=wgt, opacity=op, popup=folium.Popup(pop, max_width=250)).add_to(m)

    for s in data["spots"]:
        icol, txt = "blue", s["name"]
        hit = False
        for t in s["target"]:
            for a in active_landing:
                if t in a: hit = True
        if hit:
            icol = "red"; txt += f"<br><b>★チャンス！</b><br>{s['desc']}"
        else:
            txt += f"<br>{s['desc']}"
        folium.Marker(s["loc"], popup=folium.Popup(txt, max_width=200), icon=folium.Icon(color=icol, icon="camera")).add_to(m)

    arot = (wdir+180)%360
    info_html = f\"""
    <div style="position:fixed; bottom:20px; right:10px; z-index:1000; background:rgba(255,255,255,0.9); padding:10px; border-radius:8px; font-family:sans-serif; width:150px; font-size:12px;">
        <div style="text-align:center; margin-bottom:5px;"><b>{target_airport} Wind</b></div>
        <div style="display:flex; align-items:center; justify-content:center;">
            <div style="position:relative; width:30px; height:30px; border:2px solid #ccc; border-radius:50%; margin-right:10px;">
                <div style="position:absolute; top:-4px; left:50%; transform:translateX(-50%); font-size:8px;">N</div>
                <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%) rotate({arot}deg); color:#00bfff; font-size:16px;">⬆</div>
            </div>
            <div>{wdir}°<br>{wspd}kt</div>
        </div>
        <div style="margin-top:5px; border-top:1px solid #ddd; padding-top:5px;">
             <span style="color:cyan;">---</span> 着陸ルート<br>
             <span style="color:orange;">──</span> 離陸ルート<br>
             <span style="color:orange;">☀</span> 太陽の方向
        </div>
    </div>\"""
    m.get_root().html.add_child(folium.Element(info_html))

    st_folium(m, width=None, height=500)

else:
    st.error("気象データの取得に失敗しました。")
