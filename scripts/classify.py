import os
import requests
import re
from collections import defaultdict

# ------------------- 输入输出文件 -------------------
input_file = "output/working.m3u"  # 可播源
custom_multicast_url = "https://raw.githubusercontent.com/sumingyd/Telecom-Shandong-IPTV-List/refs/heads/main/Telecom-Shandong-Multicast.m3u"
custom_http_url = "https://raw.githubusercontent.com/sumingyd/Telecom-Shandong-IPTV-List/refs/heads/main/Telecom-Shandong.m3u"
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)
os.makedirs("custom_m3u", exist_ok=True)

# ------------------- 自备组播源替换网关 -------------------
new_gateway = "192.168.31.2"
new_port = "4022"
custom_multicast_file = os.path.join("custom_m3u", "Telecom-Shandong-Multicast-local.m3u")

try:
    r = requests.get(custom_multicast_url, timeout=10)
    r.raise_for_status()
    lines_multicast = r.text.splitlines()
except Exception as e:
    raise Exception(f"下载自备组播源失败: {e}")

custom_multicast_pairs = []
new_lines = []
for line in lines_multicast:
    if line.startswith("http://"):
        new_line = re.sub(r"http://[\d\.]+:\d+(/rtp/.*)", f"http://{new_gateway}:{new_port}\\1", line)
        new_lines.append(new_line)
    else:
        new_lines.append(line)
for i in range(0, len(new_lines)-1):
    if new_lines[i].startswith("#EXTINF"):
        custom_multicast_pairs.append((new_lines[i], new_lines[i+1], True))  # True 表示自备源

with open(custom_multicast_file, "w", encoding="utf-8", errors="ignore") as f:
    f.write("\n".join(new_lines))

# ------------------- 自备 HTTP 源 -------------------
try:
    r = requests.get(custom_http_url, timeout=10)
    r.raise_for_status()
    lines_http = r.text.splitlines()
except Exception as e:
    print(f"⚠️ 下载自备 HTTP 源失败: {e}")
    lines_http = []

custom_http_pairs = []
for i in range(0, len(lines_http)-1):
    if lines_http[i].startswith("#EXTINF"):
        custom_http_pairs.append((lines_http[i], lines_http[i+1], True))

# ------------------- 分类关键字 -------------------
categories = {
    "央视": ["CCTV","央视"],
    "卫视": ["卫视"],
    "地方": ["山东","江苏","浙江","广东","北京","上海","天津","湖南","济南","南京","深圳","重庆","四川","湖北","陕西","福建","贵州","云南","广西","海南","内蒙古","宁夏","青海","吉林","辽宁","黑龙江","安徽","江西","河南"],
    "港台": ["香港","TVB","台湾","台视","中视","华视","翡翠","三立"],
    "国际": ["BBC","CNN","NHK","FOX","HBO","Discovery"],
    "网络直播": ["斗鱼","虎牙","Bilibili","哔哩"],
}

# ------------------- 名称统一映射 -------------------
name_map = {
    "CCTV-1":"CCTV-1综合","CCTV1":"CCTV-1综合","央视综合":"CCTV-1综合",
    "CCTV-2":"CCTV-2财经","央视财经":"CCTV-2财经",
    "CCTV-3":"CCTV-3娱乐","央视娱乐":"CCTV-3娱乐",
    "CCTV-4":"CCTV-4中文国际","央视中文国际":"CCTV-4中文国际",
    "CCTV-5":"CCTV-5体育","央视体育":"CCTV-5体育",
    "CCTV-6":"CCTV-6电影","央视电影":"CCTV-6电影",
    "CCTV-7":"CCTV-7国防军事",
    "CCTV-8":"CCTV-8电视剧","央视电视剧":"CCTV-8电视剧",
    "CCTV-9":"CCTV-9纪录","央视纪录":"CCTV-9纪录",
    "CCTV-10":"CCTV-10科教","央视科教":"CCTV-10科教",
    "CCTV-11":"CCTV-11戏曲","央视戏曲":"CCTV-11戏曲",
    "CCTV-12":"CCTV-12社会与法","央视社会与法":"CCTV-12社会与法",
    "CCTV-13":"CCTV-13新闻","央视新闻":"CCTV-13新闻",
    "CCTV-14":"CCTV-14少儿","央视少儿":"CCTV-14少儿",
    "CCTV-15":"CCTV-15音乐","央视音乐":"CCTV-15音乐",
}

# ------------------- 获取远程台标 -------------------
BASE_LOGO_URL = "https://raw.githubusercontent.com/fanmingming/live/main/logo/"
GITHUB_API_URL = "https://api.github.com/repos/fanmingming/live/contents/logo"

def get_logo_files():
    try:
        r = requests.get(GITHUB_API_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        return [file['name'] for file in data if file['type']=='file']
    except Exception as e:
        print("获取 logo 文件异常:", e)
        return []

logo_files = get_logo_files()
logo_cache = {}

def find_logo_cached(title_std):
    if title_std in logo_cache:
        return logo_cache[title_std]
    title_lower = title_std.lower()
    for logo in logo_files:
        name_part = os.path.splitext(logo)[0].lower()
        if name_part == title_lower or name_part in title_lower or title_lower in name_part:
            logo_cache[title_std] = BASE_LOGO_URL + logo
            return logo_cache[title_std]
    logo_cache[title_std] = ""
    return ""

# ------------------- 初始化 channel_map -------------------
channel_map = {cat: defaultdict(list) for cat in categories}
channel_map["其他"] = defaultdict(list)

# ------------------- 读取可播源 -------------------
all_pairs = []
if os.path.exists(input_file):
    data = open(input_file, encoding="utf-8").read().splitlines()
    for i in range(0, len(data)-1):
        if data[i].startswith("#EXTINF"):
            all_pairs.append((data[i], data[i+1], False))  # False 表示非自备源

# ------------------- 合并自备源 -------------------
# 顺序：可播源 → 自备组播源 → 自备 HTTP 源
all_pairs.extend(custom_multicast_pairs)
all_pairs.extend(custom_http_pairs)

# ------------------- 分类 + 名称统一 + 台标 + 自备源优先 -------------------
for title, url, is_custom in all_pairs:
    title_clean = title.replace(" 高清","").replace(" HD","").replace(" 标清","")
    title_std = name_map.get(title_clean, title_clean)

    added = False
    for cat, kws in categories.items():
        if any(kw.lower() in title_std.lower() for kw in kws):
            if is_custom:
                channel_map[cat][title_std].insert(0, url)
            else:
                channel_map[cat][title_std].append(url)
            added = True
            break
    if not added:
        if is_custom:
            channel_map["其他"][title_std].insert(0, url)
        else:
            channel_map["其他"][title_std].append(url)

# ------------------- 内部排序 -------------------
cctv_order = ["CCTV-1综合","CCTV-2财经","CCTV-3娱乐","CCTV-4中文国际",
              "CCTV-5体育","CCTV-6电影","CCTV-7国防军事","CCTV-8电视剧",
              "CCTV-9纪录","CCTV-10科教","CCTV-11戏曲","CCTV-12社会与法",
              "CCTV-13新闻","CCTV-14少儿","CCTV-15音乐"]

province_order = ["北京","天津","河北","山西","内蒙古","辽宁","吉林","黑龙江",
                  "上海","江苏","浙江","安徽","福建","江西","山东","河南",
                  "湖北","湖南","广东","广西","海南","重庆","四川","贵州",
                  "云南","西藏","陕西","甘肃","青海","宁夏","新疆"]

category_order = ["央视","卫视","地方","港台","国际","网络直播","其他"]
summary_content = ["#EXTM3U"]

for cat in category_order:
    if cat == "央视":
        sorted_channels = sorted(channel_map[cat].keys(), key=lambda x: cctv_order.index(x) if x in cctv_order else 999)
    elif cat == "地方":
        sorted_channels = sorted(channel_map[cat].keys(), key=lambda x: (next((i for i,v in enumerate(province_order) if v in x), 999), x))
    else:
        sorted_channels = sorted(channel_map[cat].keys())

    # 输出每个分类的 M3U 文件
    with open(os.path.join(output_dir, f"{cat}.m