#!/usr/bin/env python3
# coding: utf-8
import os, re, unicodedata, requests
from collections import defaultdict

# ------------------- 配置 -------------------
input_file = "output/working.m3u"
custom_multicast_url = "https://raw.githubusercontent.com/sumingyd/Telecom-Shandong-IPTV-List/refs/heads/main/Telecom-Shandong-Multicast.m3u"
custom_http_url = "https://raw.githubusercontent.com/sumingyd/Telecom-Shandong-IPTV-List/refs/heads/main/Telecom-Shandong.m3u"
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)
os.makedirs("custom_m3u", exist_ok=True)
BASE_LOGO_RAW = "https://raw.githubusercontent.com/fanmingming/live/main/tv/"
new_gateway = "192.168.31.2"
new_port = "4022"
custom_multicast_file = os.path.join("custom_m3u", "Telecom-Shandong-Multicast-local.m3u")

# ------------------- 工具函数 -------------------
def remove_control_chars(s): return ''.join(ch for ch in s if not unicodedata.category(ch).startswith('C'))
def remove_symbols_and_emoji(s): return ''.join(ch for ch in s if not unicodedata.category(ch).startswith('S'))
def normalize_spaces(s): return re.sub(r'\s+', ' ', s).strip()
def strip_tvg_fields(s): return re.sub(r'tvg-[a-zA-Z0-9_-]+="[^"]*"|group-title="[^"]*"', '', s)

def sanitize_title(extinf):
    s = strip_tvg_fields(extinf)
    if ',' in s:
        name = s.split(',', 1)[1].strip()
    else:
        m = re.search(r'tvg-name="([^"]+)"', s)
        name = m.group(1).strip() if m else re.sub(r'^#EXTINF[^,]*,?', '', s).strip()
    name = re.sub(r'["\u2000-\u206F\u2E00-\u2E7F\ufeff]', '', name)
    name = remove_symbols_and_emoji(remove_control_chars(name))
    name = re.sub(r'(高清|HD|标清|4K)', '', name, flags=re.I)
    return normalize_spaces(name) or "unknown"

def safe_logo_name(name):
    s = re.sub(r'[^\w\u4e00-\u9fff-]', '', remove_symbols_and_emoji(remove_control_chars(name)))
    return s[:60]

def build_logo_url(name):
    n = safe_logo_name(name)
    return BASE_LOGO_RAW + n + ".png"

# ------------------- 下载自备源 -------------------
def fetch_lines(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.text.splitlines()
    except Exception as e:
        print(f"⚠️ 下载失败 {url}: {e}")
        return []

def make_multicast_local(lines):
    out = []
    for l in lines:
        if l.startswith("http://") or l.startswith("https://"):
            l = re.sub(r"http://[\d\.]+:\d+(/rtp/.*)", f"http://{new_gateway}:{new_port}\\1", l)
        out.append(l)
    open(custom_multicast_file, "w", encoding="utf-8").write("\n".join(out))
    return out

def parse_pairs(lines, is_custom=False):
    pairs = []
    for i in range(0, len(lines)-1):
        if lines[i].startswith("#EXTINF"):
            ext, url = lines[i].strip(), lines[i+1].strip()
            title = sanitize_title(ext)
            pairs.append((title, url, is_custom))
    return pairs

multicast_pairs = parse_pairs(make_multicast_local(fetch_lines(custom_multicast_url)), True)
http_pairs = parse_pairs(fetch_lines(custom_http_url), True)

# ------------------- 分类关键字 -------------------
categories = {
    "央视": ["CCTV", "央视"], "卫视": ["卫视"], "地方": ["山东","江苏","浙江","广东","北京","上海","天津","湖南","重庆","四川","湖北","陕西","福建"],
    "港台": ["香港","TVB","台湾","台视","中视","翡翠"], "国际": ["BBC","CNN","NHK"], "网络直播": ["斗鱼","虎牙","Bilibili"]
}
category_order = ["央视","卫视","地方","港台","国际","网络直播","其他"]
cctv_order = ["CCTV-1综合","CCTV-2财经","CCTV-3娱乐","CCTV-4中文国际","CCTV-5体育","CCTV-6电影","CCTV-7国防军事","CCTV-8电视剧","CCTV-9纪录","CCTV-10科教","CCTV-11戏曲","CCTV-12社会与法","CCTV-13新闻","CCTV-14少儿","CCTV-15音乐"]

name_map = {
    "CCTV1":"CCTV-1综合","央视综合":"CCTV-1综合","CCTV-2":"CCTV-2财经","央视财经":"CCTV-2财经",
    "CCTV-13":"CCTV-13新闻","央视新闻":"CCTV-13新闻"
}

# ------------------- 合并所有源 -------------------
lines = open(input_file, encoding="utf-8").read().splitlines() if os.path.exists(input_file) else []
working_pairs = parse_pairs(lines, False)
merged = multicast_pairs + http_pairs + working_pairs  # 自备源在前

# ------------------- 构建频道表 -------------------
channel_map = {c: defaultdict(list) for c in categories}
channel_map["其他"] = defaultdict(list)
custom_channels = set()

for title, url, is_custom in merged:
    std_name = normalize_spaces(remove_symbols_and_emoji(remove_control_chars(name_map.get(title, title))))
    cat = "其他"
    for c, kws in categories.items():
        if any(kw.lower() in std_name.lower() for kw in kws):
            cat = c; break
    if url not in channel_map[cat][std_name]:
        if is_custom:
            channel_map[cat][std_name].insert(0, url)
            custom_channels.add(std_name)  # 标记该频道有自备源
        else:
            channel_map[cat][std_name].append(url)

# ------------------- 输出 -------------------
summary = ["#EXTM3U"]
for cat in category_order:
    keys = list(channel_map[cat].keys())
    if cat == "央视":
        keys.sort(key=lambda x: cctv_order.index(x) if x in cctv_order else 999)
    else:
        keys.sort()
    # 让含自备源的频道整体置顶
    keys.sort(key=lambda x: 0 if x in custom_channels else 1)
    path = os.path.join(output_dir, f"{cat}.m3u")
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for k in keys:
            logo = build_logo_url(k)
            for u in channel_map[cat][k]:
                line = f'#EXTINF:-1 tvg-name="{k}" tvg-logo="{logo}" group-title="{cat}",{k}'
                f.write(line + "\n" + u + "\n")
                summary.append(line); summary.append(u)

open(os.path.join(output_dir,"summary.m3u"),"w",encoding="utf-8").write("\n".join(summary))
print("✅ classify.py 执行完成：台标正确，自备源频道整体置顶。")