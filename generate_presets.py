import os
import json
import math

NUM_POINTS = 64
SQUARE_SIZE = 250.0

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

def path_length(points):
    d = 0.0
    for i in range(1, len(points)):
        d += math.hypot(points[i].x - points[i-1].x, points[i].y - points[i-1].y)
    return d

def resample(points, n):
    I_len = path_length(points) / (n - 1)
    D = 0.0
    newpoints = [points[0]]
    i = 1
    pts = points[:]
    while i < len(pts):
        d = math.hypot(pts[i].x - pts[i-1].x, pts[i].y - pts[i-1].y)
        if (D + d) >= I_len:
            qx = pts[i-1].x + ((I_len - D) / d) * (pts[i].x - pts[i-1].x)
            qy = pts[i-1].y + ((I_len - D) / d) * (pts[i].y - pts[i-1].y)
            q = Point(qx, qy)
            newpoints.append(q)
            pts.insert(i, q)
            D = 0.0
        else:
            D += d
        i += 1
    if len(newpoints) == n - 1:
        newpoints.append(pts[-1])
    return newpoints

def centroid(points):
    cx, cy = 0.0, 0.0
    for p in points:
        cx += p.x
        cy += p.y
    return Point(cx / len(points), cy / len(points))

def translate_to(points, origin):
    c = centroid(points)
    return [Point(p.x + origin.x - c.x, p.y + origin.y - c.y) for p in points]

def scale_to(points, size):
    minx, maxx, miny, maxy = float('inf'), float('-inf'), float('inf'), float('-inf')
    for p in points:
        minx = min(minx, p.x)
        maxx = max(maxx, p.x)
        miny = min(miny, p.y)
        maxy = max(maxy, p.y)
    bw = maxx - minx
    bh = maxy - miny
    if bw == 0: bw = 1
    if bh == 0: bh = 1
    return [Point(p.x * (size / bw), p.y * (size / bh)) for p in points]

def normalize(points):
    pts = [Point(x, y) for (x, y) in points]
    if path_length(pts) == 0:
        return [(p.x, p.y) for p in pts]
    pts = resample(pts, NUM_POINTS)
    pts = scale_to(pts, SQUARE_SIZE)
    pts = translate_to(pts, Point(0, 0))
    return [(p.x, p.y) for p in pts]

PRESETS_DIR = "Hazir_Profiller"
if not os.path.exists(PRESETS_DIR):
    os.makedirs(PRESETS_DIR)

# 1. ESKİ ŞEKİLLERİ OLUŞTURMA (Velo Varsayılan Çizimler)
v_raw_play = [[150 + i*6, 100 + i*8] for i in range(15)] + [[240 + i*6, 220 - i*8] for i in range(15)]
v_raw_next = [[150 + i*6, 100 + i*6] for i in range(15)] + [[240 - i*6, 190 + i*6] for i in range(15)]
v_raw_prev = [[240 - i*6, 100 + i*6] for i in range(15)] + [[150 + i*6, 190 + i*6] for i in range(15)]
v_raw_mute = [[100 + i*5, 200 - i*10] for i in range(10)] + [[150 + i*5, 100 + i*10] for i in range(10)] + [[200 + i*5, 200 - i*10] for i in range(10)] + [[250 + i*5, 100 + i*10] for i in range(10)]

# 2. EDGE ŞEKİLLERİ (Kenar Kavisleri / Edge Swipes)
e_raw_play = [[160 + (i/19.0)*160, 10 + 60 * (2*(i/19.0) - 1)**2] for i in range(20)]
e_raw_mute = [[160 + (i/19.0)*160, 260 - 60 * (2*(i/19.0) - 1)**2] for i in range(20)]
e_raw_next = [[470 - 60 * (2*(i/19.0) - 1)**2, 50 + (i/19.0)*170] for i in range(20)]
e_raw_prev = [[10 + 60 * (2*(i/19.0) - 1)**2, 50 + (i/19.0)*170] for i in range(20)]

# 3. KÖŞE (CORNER) KAVİSLERİ (Fotoğraftaki İsteğe Özel)
# Köşe eğimlerini yarıçap r=100 çeyrek çember olarak alıyorum (Tuval köşeleri)
c_raw_tr_next = []  # Top-Right (Sonraki) - Üst kenardan (~380,0) başlayıp sağ kenara (~480,100) kavis
for i in range(20):
    t = i / 19.0
    x = 480 - 100 * math.cos(t * math.pi/2)
    y = 100 * math.sin(t * math.pi/2)
    c_raw_tr_next.append([x, y])

c_raw_tl_prev = []  # Top-Left (Önceki) - Üst kenardan (~100,0) sol kenara (~0,100) kavis
for i in range(20):
    t = i / 19.0
    x = 100 - 100 * math.sin(t * math.pi/2)
    y = 100 - 100 * math.cos(t * math.pi/2)
    c_raw_tl_prev.append([x, y])

c_raw_bl_play = []  # Bottom-Left (Oynat/Duraklat) - Sol kenardan (~0,170) alt kenara (~100,270)
for i in range(20):
    t = i / 19.0
    x = 100 - 100 * math.cos(t * math.pi/2)
    y = 270 - 100 * math.sin(t * math.pi/2)
    c_raw_bl_play.append([x, y])

c_raw_br_mute = []  # Bottom-Right (Sesi Kapat) - Sağ kenardan (~480,170) alt kenara (~380,270)
for i in range(20):
    t = i / 19.0
    x = 380 + 100 * math.sin(t * math.pi/2)
    y = 270 - 100 * math.cos(t * math.pi/2)
    c_raw_br_mute.append([x, y])

gestures_db = {
    "profiles": {
        "Velo Varsayılan Çizimler": {
            "g1": {"name": "Oynat / Duraklat", "action": "media_play_pause", "raw_points": v_raw_play, "points": normalize(v_raw_play)},
            "g2": {"name": "Sonraki Şarkı", "action": "media_next", "raw_points": v_raw_next, "points": normalize(v_raw_next)},
            "g3": {"name": "Önceki Şarkı", "action": "media_previous", "raw_points": v_raw_prev, "points": normalize(v_raw_prev)},
            "g4": {"name": "Sesi Kapat / Aç", "action": "media_volume_mute", "raw_points": v_raw_mute, "points": normalize(v_raw_mute)}
        },
        "Edge Kavisli Gestures (Kenarlar)": {
            "g11": {"name": "Oynat / Duraklat", "action": "media_play_pause", "raw_points": e_raw_play, "points": normalize(e_raw_play)},
            "g12": {"name": "Sonraki Şarkı", "action": "media_next", "raw_points": e_raw_next, "points": normalize(e_raw_next)},
            "g13": {"name": "Önceki Şarkı", "action": "media_previous", "raw_points": e_raw_prev, "points": normalize(e_raw_prev)},
            "g14": {"name": "Sesi Kapat / Aç", "action": "media_volume_mute", "raw_points": e_raw_mute, "points": normalize(e_raw_mute)}
        },
        "Köşe Kavisleri (Corners)": {
            "g21": {"name": "Oynat / Duraklat", "action": "media_play_pause", "raw_points": c_raw_bl_play, "points": normalize(c_raw_bl_play)},
            "g22": {"name": "Sonraki Şarkı", "action": "media_next", "raw_points": c_raw_tr_next, "points": normalize(c_raw_tr_next)},
            "g23": {"name": "Önceki Şarkı", "action": "media_previous", "raw_points": c_raw_tl_prev, "points": normalize(c_raw_tl_prev)},
            "g24": {"name": "Sesi Kapat / Aç", "action": "media_volume_mute", "raw_points": c_raw_br_mute, "points": normalize(c_raw_br_mute)}
        }
    },
    "active_profile": "Köşe Kavisleri (Corners)"
}

file_path = os.path.join(PRESETS_DIR, "Velo_Varsayilan_Gestures.json")
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(gestures_db, f, indent=4)

print(f"Tum profiller olusturuldu.")
