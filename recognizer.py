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
    # Create a copy so we can insert points securely
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
    newpoints = []
    for p in points:
        qx = p.x + origin.x - c.x
        qy = p.y + origin.y - c.y
        newpoints.append(Point(qx, qy))
    return newpoints

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
    
    # Preserve aspect ratio or squash?
    # Simple unistroke squashes to square. Let's squash.
    newpoints = []
    for p in points:
        qx = p.x * (size / bw)
        qy = p.y * (size / bh)
        newpoints.append(Point(qx, qy))
    return newpoints

def path_distance(pts1, pts2):
    d = 0.0
    # ensure same length
    min_len = min(len(pts1), len(pts2))
    for i in range(min_len):
        d += math.hypot(pts2[i].x - pts1[i].x, pts2[i].y - pts1[i].y)
    return d / min_len if min_len > 0 else 0

def normalize(points):
    pts = [Point(x, y) for (x, y) in points]
    if path_length(pts) == 0:
        return [(p.x, p.y) for p in pts]
    pts = resample(pts, NUM_POINTS)
    pts = scale_to(pts, SQUARE_SIZE)
    pts = translate_to(pts, Point(0, 0))
    return [(p.x, p.y) for p in pts]

def recognize(points, templates, threshold=150.0):
    if len(points) < 5:
        return None, float('inf')
        
    pts = normalize(points)
    pts1 = [Point(x, y) for (x, y) in pts]
    
    best_dist = float('inf')
    best_template = None
    
    for t_id, t_data in templates.items():
        t_pts_coords = t_data.get("points", [])
        if not t_pts_coords:
            continue
            
        pts2 = [Point(x, y) for (x, y) in t_pts_coords]
        d = path_distance(pts1, pts2)
        if d < best_dist:
            best_dist = d
            best_template = t_data
            
    if best_dist < threshold:
        return best_template, best_dist
    return None, best_dist
