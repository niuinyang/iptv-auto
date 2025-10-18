#!/usr/bin/env python3
# coding: utf-8
import os, re, unicodedata, requests, json
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
name_map_file = "custom_m3u/name_map_auto.json"

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

def parse_pairs(lines, is_custom=False, source_type="other"):
    pairs = []
    for i in range(0, len(lines)-1):
        if lines[i].startswith("#EXTINF"):
            ext, url = lines[i].strip(), lines[i+1].strip()
            title = sanitize_title(ext)
            pairs.append((title, url, is_custom, source_type))
    return pairs

# ------------------- 分类关键字 -------------------
categories = {
    "央视": ["CCTV", "央视"], 
    "卫视": ["卫视"], 
    "地方": ["山东","江苏","浙江","广东","北京","上海","天津","湖南","重庆","四川","湖北","陕西","福建"],
    "港台": ["香港","TVB","台湾","台视","中视","翡翠"], 
    "国际": ["BBC","CNN","NHK"], 
    "网络频道": ["斗鱼","虎牙","Bilibili"],
    "4K频道": []
}
category_order = ["央视","卫视","地方","港台","国际","网络频道","4K频道","其他"]
cctv_order = ["CCTV-1综合","CCTV-2财经","CCTV-3娱乐","CCTV-4中文国际","CCTV-5体育","CCTV-6电影",
              "CCTV-7国防军事","CCTV-8电视剧","CCTV-9纪录","CCTV-10科教","CCTV-11戏曲",
              "CCTV-12社会与法","CCTV-13新闻","CCTV-14少儿","CCTV-15音乐"]

group_title_map = {
    "央视": "央视频道",
    "卫视": "卫视频道",
    "地方": "地方频道",
    "港台": "港台频道",
    "国际": "国际频道",
    "网络频道": "网络频道",
    "4K频道": "4K频道",
    "其他": "其他频道"
}

# ------------------- 智能 name_map + 自动更新 -------------------
name_map = {
    "CCTV1":"CCTV-1综合","央视综合":"CCTV-1综合",
    "CCTV-2":"CCTV-2财经","央视财经":"CCTV-2财经",
    "CCTV-13":"CCTV-13新闻","央视新闻":"CCTV-13新闻"
}
province_channels = {
    "山东卫视": ["山东卫视", "SDTV", "山东电视"],
    "江苏卫视": ["江苏卫视", "JSTV"],
    "浙江卫视": ["浙江卫视", "ZJTV"],
    "广东卫视": ["广东卫视", "GDTV"],
    "北京卫视": ["北京卫视", "BTV"],
    "上海东方卫视": ["东方卫视", "SHTV-DF"],
    "湖南卫视": ["湖南卫视", "HNTV"],
    "重庆卫视": ["重庆卫视", "CQTV"],
    "四川卫视": ["四川卫视", "SCTV"],
    "湖北卫视": ["湖北卫视", "HUBTV"],
    "陕西卫视": ["陕西卫视", "SXTV"],
    "福建东南卫视": ["东南卫视", "FJTV"]
}
if os.path.exists(name_map_file):
    with open(name_map_file, "r", encoding="utf-8") as f:
        auto_name_map_dict = json.load(f)
else:
    auto_name_map_dict = {}
unmapped = set()

def smart_name_map(title):
    t = title.strip()
    if not t:
        return "unknown"
    if t in name_map: return name_map[t]
    if t in auto_name_map_dict: return auto_name_map_dict[t]

    t_clean = re.sub(r'(高清|HD|标清|4K)', '', t, flags=re.I).replace(" ", "").replace("-", "")
    if t_clean.upper().startswith("CCTV") or t_clean.startswith("央视"):
        m = re.search(r'\d+', t_clean)
        if m:
            num = m.group(0)
            mapping = {str(i): f"CCTV-{i}{suffix}" for i,suffix in 
                       enumerate(["综合","财经","娱乐","中文国际","体育","电影","国防军事","电视剧","纪录","科教","戏曲","社会与法","新闻","少儿","音乐"],1)}
            return mapping.get(num, t)
    t_upper = t_clean.upper()
    for std_name, aliases in province_channels.items():
        for a in aliases:
            a_clean = a.upper().replace(" ", "").replace("-", "")
            if a_clean in t_upper:
                return std_name
    unmapped.add(t)
    result = normalize_spaces(remove_symbols_and_emoji(remove_control_chars(t)))
    return result if result else "unknown"

# ------------------- 合并源 -------------------
lines = open(input_file, encoding="utf-8").read().splitlines() if os.path.exists(input_file) else []
working_pairs = parse_pairs(lines, False, "other")
multicast_pairs = parse_pairs(make_multicast_local(fetch_lines(custom_multicast_url)), True, "multicast")
http_pairs = parse_pairs(fetch_lines(custom_http_url), True, "http")
merged = multicast_pairs + http_pairs + working_pairs

# ------------------- 构建频道表 -------------------
channel_map = {c: defaultdict(list) for c in categories}
channel_map["其他"] = defaultdict(list)
custom_channels = set()
for title,url,is_custom,source_type in merged:
    std_name = smart_name_map(title)
    std_name = std_name or "unknown"
    is_4k = bool(re.search(r'4K', title, re.I))
    if is_4k: cat="4K频道"
    else:
        cat="其他"
        for c,kws in categories.items():
            if c=="4K频道": continue
            if any(kw.lower() in (std_name or "").lower() for kw in kws):
                cat=c
                break
    lst = channel_map[cat][std_name]
    if is_custom:
        custom_channels.add(std_name)
        if source_type=="multicast": lst.insert(0,url)
        elif source_type=="http":
            idx = next((i for i,v in enumerate(lst) if not v.startswith("http://"+new_gateway)), len(lst))
            lst.insert(idx,url)
    else: lst.append(url)

# ------------------- 输出 summary & 分类文件 -------------------
summary_lines=["#EXTM3U"]
for cat in category_order:
    keys=list(channel_map[cat].keys())
    if cat=="央视": keys.sort(key=lambda x: cctv_order.index(x) if x in cctv_order else 999)
    else: keys.sort()
    keys.sort(key=lambda x: 0 if x in custom_channels else 1)
    path=os.path.join(output_dir,f"{cat}.m3u")
    with open(path,"w",encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for k in keys:
            logo=build_logo_url(k)
            group_title=group_title_map.get(cat,cat)
            for u in channel_map[cat][k]:
                line=f'#EXTINF:-1 tvg-name="{k}" tvg-logo="{logo}" group-title="{group_title}",{k}'
                f.write(line+"\n"+u+"\n")
                summary_lines.append(line)
                summary_lines.append(u)

# ------------------- 成人黑名单 -------------------
def fetch_adult_blacklist():
    urls=[
        "https://raw.githubusercontent.com/emiliodallatorre/adult-hosts-list/main/list.txt",
        "https://raw.githubusercontent.com/columndeeply/hosts/main/hosts00",
        "https://raw.githubusercontent.com/Bon-Appetit/porn-domains/main/domains.txt"
    ]
    domains=set()
    for url in urls:
        try:
            r=requests.get(url,timeout=10); r.raise_for_status()
            for line in r.text.splitlines():
                line=line.strip()
                if line and not line.startswith("#"):
                    domain=re.sub(r'^0\.0\.0\.0\s+','',line)
                    domains.add(domain.lower())
        except Exception as e:
            print(f"⚠️ 下载成人黑名单失败: {url}, 错误: {e}")
    return domains

adult_domains = fetch_adult_blacklist()
adult_channels=[]; clean_summary=[]
for i in range(0,len(summary_lines),2):
    if i+1>=len(summary_lines): break
    ext, url = summary_lines[i], summary_lines[i+1]
    if any(d in url.lower() for d in adult_domains):
        adult_channels.append((ext,url))
    else:
        clean_summary.append(ext); clean_summary.append(url)

# 写入 au.m3u
with open(os.path.join(output_dir,"au.m3u"),"w",encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for ext,url in adult_channels:
        f.write(ext+"\n"+url+"\n")

# 覆盖 summary.m3u
with open(os.path.join(output_dir,"summary.m3u"),"w",encoding="utf-8") as f:
    f.write("\n".join(clean_summary))

# ------------------- 自动更新 name_map -------------------
if unmapped:
    auto_name_map_dict.update({k:k for k in unmapped})
    os.makedirs(os.path.dirname(name_map_file),exist_ok=True)
    with open(name_map_file,"w",encoding="utf-8") as f:
        json.dump(auto_name_map_dict,f,ensure_ascii=False,indent=2)
    print(f"📝 更新自动 name_map 文件: {name_map_file}, 新增 {len(unmapped)} 个未匹配频道")

print(f"✅ classify.py 执行完成，summary、4K、分类文件生成，自备源置顶，成人源分离完成")