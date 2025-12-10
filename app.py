import folium
from folium.plugins import BeautifyIcon
from folium import DivIcon
import math
import urllib.request
import re

# --- 1. 計算ロジック ---
aircraft_specs = { "B737-800": 34, "B777-300ER": 38, "A350-900": 38 } # 羽田なので大型機メイン

def get_metar(airport_code):
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{airport_code}.TXT"
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode('utf-8').split('\n')[1]
    except: return None

def parse_metar_full(text):
    wind_match = re.search(r'([0-9]{3})([0-9]{2,3})KT', text)
    wind_dir = int(wind_match.group(1)) if wind_match else 0
    wind_spd = int(wind_match.group(2)) if wind_match else 0
    if "CAVOK" in text:
        vis = 9999; ceiling = 9999
    else:
        vis_match = re.search(r'\s([0-9]{4})\s', text)
        vis = int(vis_match.group(1)) if vis_match else 9999
        clouds = re.findall(r'(BKN|OVC)([0-9]{3})', text)
        if clouds:
            heights = [int(c[1]) * 100 for c in clouds]
            ceiling = min(heights)
        else:
            ceiling = 9999
    return wind_dir, wind_spd, vis, ceiling

def calculate_wind_components(wind_dir, wind_speed, rwy_heading):
    rad = math.radians(wind_dir - rwy_heading)
    hw = wind_speed * math.cos(rad)
    cw = wind_speed * math.sin(rad)
    return hw, cw

def get_point_at_distance(start_coord, heading_deg, distance_km):
    R = 6378.1
    brng = math.radians(heading_deg)
    d = distance_km
    lat1 = math.radians(start_coord[0])
    lon1 = math.radians(start_coord[1])
    lat2 = math.asin(math.sin(lat1)*math.cos(d/R) + math.cos(lat1)*math.sin(d/R)*math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng)*math.sin(d/R)*math.cos(lat1), math.cos(d/R)-math.sin(lat1)*math.sin(lat2))
    return [math.degrees(lat2), math.degrees(lon2)]

def get_aircraft_judgment(cw):
    judgments = []
    cw_abs = abs(cw)
    for name, limit in aircraft_specs.items():
        icon = "✅" if cw_abs <= limit else "❌"
        judgments.append(f"{icon} {name}")
    return "<br>".join(judgments)

# --- 2. 羽田空港データ (座標修正済み) ---
# いただいた正確な座標を変数に格納
coord_34L = [35.536939, 139.785442] # A滑走路 南端
coord_16R = [35.555724, 139.772081] # A滑走路 北端
coord_34R = [35.542632, 139.803064] # C滑走路 南端
coord_16L = [35.564966, 139.787195] # C滑走路 北端
coord_22  = [35.567152, 139.776839] # B滑走路 北東端
coord_04  = [35.549336, 139.761563] # B滑走路 南西端
coord_23  = [35.540330, 139.821781] # D滑走路 北東端
coord_05  = [35.524289, 139.803781] # D滑走路 南西端

runways_geom = {
    # 北風運用 (34L/R)
    "RWY 34L (A:北風)": {"coords": [coord_34L, coord_16R], "heading": 337, "threshold": coord_34L},
    "RWY 34R (C:北風)": {"coords": [coord_34R, coord_16L], "heading": 337, "threshold": coord_34R},
    # 南風運用 (22/23) - 着陸
    "RWY 22 (B:南風)":  {"coords": [coord_22, coord_04], "heading": 220, "threshold": coord_22},
    "RWY 23 (D:南風)":  {"coords": [coord_23, coord_05], "heading": 230, "threshold": coord_23},
    # 南風運用 (16L/R) - 都心ルート用（今回はデータ定義のみ）
    "RWY 16L (C:都心)": {"coords": [coord_16L, coord_34R], "heading": 157, "threshold": coord_16L},
    "RWY 16R (A:都心)": {"coords": [coord_16R, coord_34L], "heading": 157, "threshold": coord_16R},
}

spots = [
    {"name": "第1ターミナル展望デッキ", "loc": [35.548, 139.785], "target": ["RWY 34L", "RWY 16R"], "desc": "A滑走路の目の前。JAL機と富士山が見える。"},
    {"name": "第2ターミナル展望デッキ", "loc": [35.553, 139.790], "target": ["RWY 34R", "RWY 16L", "RWY 22"], "desc": "C滑走路と海が見える。ANA機メイン。"},
    {"name": "第3ターミナル展望デッキ", "loc": [35.544, 139.766], "target": ["RWY 22", "RWY 16L", "RWY 34L"], "desc": "国際線。A滑走路やB滑走路の着陸が見える。"},
    {"name": "京浜島つばさ公園", "loc": [35.568, 139.793], "target": ["RWY 22"], "desc": "B滑走路(RWY22)への着陸機が目の前を通過する南風時の聖地。"},
    {"name": "城南島海浜公園", "loc": [35.578, 139.793], "target": ["RWY 22", "RWY 34R"], "desc": "RWY22着陸や、RWY34R離陸機が頭上を旋回する。"},
    {"name": "浮島町公園", "loc": [35.528, 139.794], "target": ["RWY 34L", "RWY 05"], "desc": "34Lへの着陸機が目の前を通る。川崎側の有名スポット。"}
]

# --- 3. マップ生成 ---
target_airport = "RJTT"
metar_text = get_metar(target_airport)

if metar_text:
    wind_dir, wind_spd, vis, ceiling = parse_metar_full(metar_text)

    photo_status = "◎ 良好"; photo_color = "green"; photo_msg = "視界クリア。"
    if vis < 5000 or ceiling < 1500:
        photo_status = "❌ 悪条件"; photo_color = "red"; photo_msg = "視界不良/雲低。"
        if ceiling < 1500: photo_msg = f"雲底 {ceiling}ft"
    elif vis < 8000 or ceiling < 3000:
        photo_status = "△ 微妙"; photo_color = "orange"

    # 羽田全体が見えるようにズームと中心位置を調整
    m = folium.Map(location=[35.545, 139.790], zoom_start=12, tiles="CartoDB dark_matter")
    arrow_rotation = (wind_dir + 180) % 360

    wind_info = f"""
    <div style="position: fixed; bottom: 30px; right: 10px; z-index: 1000; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 12px; font-family: sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.3); width: 220px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div style="font-weight: bold; font-size: 1.1em;">AeroSpotter</div>
            <div style="background: #333; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em;">RJTT</div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-around; background: #f0f0f0; border-radius: 8px; padding: 10px;">
            <div style="position: relative; width: 50px; height: 50px; border: 2px solid #ccc; border-radius: 50%; background: white;">
                <div style="position: absolute; top: -5px; left: 50%; transform: translateX(-50%); font-size: 10px; font-weight: bold; color: #555;">N</div>
                <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate({arrow_rotation}deg); font-size: 24px; color: #00bfff;">⬆</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 1.5em; font-weight: bold;">{wind_dir}°</div>
                <div style="font-size: 1.1em;">{wind_spd} kt</div>
            </div>
        </div>
        <div style="margin-top: 10px; font-size: 0.9em; color: #555;">
            <div>Vis: <b>{vis}m</b> / Clg: <b>{"-" if ceiling==9999 else f"{ceiling}ft"}</b></div>
        </div>
        <hr style="margin: 8px 0;">
        <div style="text-align: center;">
            <b style="color:{photo_color}; font-size: 1.2em;">判定: {photo_status}</b>
            <div style="font-size: 0.8em; color: #666; margin-top: 4px;">{photo_msg}</div>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(wind_info))

    active_runways = []

    # 簡易的な北風/南風判定（※実際は時間帯や運用モードで複雑ですが、まずは風向ベースで）
    is_north_ops = True
    if 90 <= wind_dir <= 270:
        is_north_ops = False

    for name, data in runways_geom.items():
        hw, cw = calculate_wind_components(wind_dir, wind_spd, data["heading"])

        # 運用フィルター（都心ルートRWY16系は一旦除外してシンプルに）
        is_active = False
        if is_north_ops and ("RWY 34" in name):
            is_active = True
        elif not is_north_ops and ("RWY 22" in name or "RWY 23" in name):
            is_active = True

        color = "gray"; weight = 3; opacity = 0.5; status = "Standby"

        if is_active:
            if hw < -5:
                 color = "#ff3333"; status = "❌使用不可(追い風)"
            else:
                color = "#00ff00"; weight = 8; opacity = 0.9; status = "✅運用中(Active)"
                active_runways.append(name[:6])

                # 進入ライン
                approach_heading = data["heading"] + 180
                far_point = get_point_at_distance(data["threshold"], approach_heading, 10.0)
                folium.PolyLine(locations=[data["threshold"], far_point], color="cyan", weight=2, dash_array='10, 10', opacity=0.7).add_to(m)

                p_3km = get_point_at_distance(data["threshold"], approach_heading, 3.0)
                folium.Marker(location=p_3km, icon=DivIcon(html=f'<div style="font-size: 9pt; color: cyan; white-space: nowrap;">▼300m</div>')).add_to(m)

                start_icon_pt = get_point_at_distance(data["threshold"], approach_heading, 0.5)
                icon_rotation = data["heading"] - 90
                folium.Marker(location=start_icon_pt, popup=f"App: {name}", icon=BeautifyIcon(icon="plane", icon_shape="marker", border_color="#00ff00", text_color="#00ff00", rotation=icon_rotation, inner_icon_style="font-size:24px;")).add_to(m)

        popup_html = f"<b>{name}</b><br>{status}<br>Head: {hw:.1f}kt / Cross: {abs(cw):.1f}kt<br><hr>{get_aircraft_judgment(cw)}"
        folium.PolyLine(locations=data["coords"], color=color, weight=weight, opacity=opacity, popup=folium.Popup(popup html, max_width=250)).add_to(m)

    for spot in spots:
        icon_color = "blue"; popup_text = spot['name']; is_best_spot = False
        for t in spot["target"]:
            for active in active_runways:
                if t in active: is_best_spot = True
        if is_best_spot:
            icon_color = "red"; popup_text += f"<br><b>★チャンス！</b><br>{spot['desc']}"
        else:
            popup_text += f"<br>{spot['desc']}"
        folium.Marker(location=spot["loc"], popup=folium.Popup(popup_text, max_width=200), icon=folium.Icon(color=icon_color, icon="camera")).add_to(m)

    output_file = "haneda_map_v3.html"
    m.save(output_file)
    display(m)

else:
    print("データ取得エラー")