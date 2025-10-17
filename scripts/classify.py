#!/usr/bin/env python3
# coding: utf-8

import os
import re
import unicodedata
import requests
from collections import defaultdict

# ------------------- 配置 -------------------
input_file = "output/working.m3u"  # 可播源（检测通过）
custom_multicast_url = "https://raw.githubusercontent.com/sumingyd/Telecom-Shandong-IPTV-List/refs/heads/main/Telecom-Shandong-Multicast.m3u"
custom_http_url = "https://raw.githubusercontent.com/sumingyd/Telecom-Shandong-IPTV-List/refs/heads/main/Telecom-Shandong.m3u"
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)
os.makedirs("custom_m3u", exist_ok=True)

# 自备组播替换网关（示例）
new_gateway = "192.168.31.2"
new_port = "4022"
custom_multicast_file = os.path.join("custom_m3u", "Telecom-Shandong-Multicast-local.m3u")

# logo raw 基础路径（使用 raw.githubusercontent）
BASE_LOGO_RAW = "https://raw.githubusercontent.com/fanmingming/live/main/tv/"

# ------------------- 工具：清理文本 -------------------
def remove_control_chars(s: str) -> str:
    return ''.join(ch for ch in s if not unicodedata.category(ch).startswith('C'))

def remove_symbols_and_emoji(s: str) -> str:
    # 删除符号类（S*）及少量其它不可见特殊字符
    return ''.join(ch for ch in s if not unicodedata.category(ch).startswith('S'))

def normalize_spaces(s: str) -> str:
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def strip_tvg_fields(extinf: str) -> str:
    """
    移除 extinf 中可能已有的 tvg-* 属性残留（避免把它们当成频道名或 logo 名）
    例如： tvg-name="..." tvg-logo="..." group-title="..."
    """
    s = re.sub(r'tvg-[a-zA-Z0-9_-]+="[^"]*"', '', extinf)
    s = re.sub(r'group-title="[^"]*"', '', s)
    s = re.sub(r'[,]+', ',', s)  # 合并多余逗号
    return s

def sanitize_title_from_extinf(extinf_line: str) -> str:
    """
    从 #EXTINF 行提取并清洗频道显示名：
    - 优先取最后一个逗号后的部分（常见）
    - 若无逗号，尝试 tvg-name=""
    - 删除控制字符、emoji、已有 tvg-* 残留、高清等后缀
    """
    # 删除已有 tvg-* 字段残留，减少污染
    cleaned = strip_tvg_fields(extinf_line)

    # 提取名：通常在最后一个逗号后
    name = ""
    if ',' in cleaned:
        name = cleaned.split(',', 1)[1].strip()
    else:
        m = re.search(r'tvg-name="([^"]+)"', cleaned)
        if m:
            name = m.group(1).strip()
        else:
            # 兜底：去掉 "#EXTINF..." 前缀
            name = re.sub(r'^\s*#EXTINF[^,]*,?', '', cleaned).strip()

    # 删除包裹引号
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]

    # 基本清理
    name = remove_control_chars(name)
    name = remove_symbols_and_emoji(name)

    # 去掉常见后缀如 高清/HD/标清/4K 等
    name = re.sub(r'\b(高清|HD|标清|4K|4k)\b', '', name, flags=re.IGNORECASE)

    # 去掉奇怪的 unicode 分隔符
    name = re.sub(r'[\u2000-\u206F\u2E00-\u2E7F\ufeff]', '', name)

    # 统一空格
    name = normalize_spaces(name)

    # 若清理后为空，则用 extinf line 做最后兜底（进一步清理）
    if not name:
        tmp = re.sub(r'^\s*#EXTINF[^,]*,?', '', extinf_line)
        tmp = remove_control_chars(tmp)
        tmp = remove_symbols_and_emoji(tmp)
        name = normalize_spaces(tmp) or "unknown"

    return name

def safe_logo_name(title_std: str) -> str:
    """
    生成安全的 logo 文件名（用于 raw.githubusercontent.com）
    - 只保留中/英/数字/下划线/连字符
    - 删除空格、点、冒号等可能破坏路径的字符
    - 不包含任何 #EXTINF 或 tvg 字段残留
    """
    s = title_std
    s = remove_control_chars(s)
    s = remove_symbols_and_emoji(s)
    # 允许中文、字母、数字、下划线、短横
    s = re.sub(r'[^\w\u4e00-\u9fff\-_]', '', s)
    # 截断避免过长
    return s[:60] if len(s) > 60 else s

# ------------------- 下载并处理自备组播源 -------------------
try:
    r = requests.get(custom_multicast_url, timeout=10)
    r.raise_for_status()
    lines_multicast = r.text.splitlines()
except Exception as e:
    raise Exception(f"下载自备组播源失败: {e}")

custom_multicast_pairs = []
new_lines = []
for line in lines_multicast:
    if line.startswith("http://") or line.startswith("https://"):
        # 替换网关的场景，仅替换 private rtp 格式，保留其它不变
        new_line = re.sub(r"http://[\d\.]+:\d+(/rtp/.*)", f"http://{new_gateway}:{new_port}\\1", line)
        new_lines.append(new_line)
    else:
        new_lines.append(line)

# 把 extinf+url 对解析为三元组 (raw_extinf, cleaned_title, url, is_custom)
for i in range(0, len(new_lines)-1):
    if new_lines[i].startswith("#EXTINF"):
        ext = new_lines[i].strip()
        url = new_lines[i+1].strip()
        tname = sanitize_title_from_extinf(ext)
        custom_multicast_pairs.append((ext, tname, url, True))

with open(custom_multicast_file, "w", encoding="utf-8", errors="ignore") as f:
    f.write("\n".join(new_lines))

# ------------------- 下载自备 HTTP 源 -------------------
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
        ext = lines_http[i].strip()
        url = lines_http[i+1].strip()
        tname = sanitize_title_from_extinf(ext)
        custom_http_pairs.append((ext, tname, url, True))

# ------------------- 分类关键字 -------------------
categories = {
    "央视": ["CCTV", "央视"],
    "卫视": ["卫视"],
    "地方": ["山东","江苏","浙江","广东","北京","上海","天津","湖南","济南","南京","深圳","重庆","四川","湖北","陕西","福建","贵州","云南","广西","海南","内蒙古","宁夏","青海","吉林","辽宁","黑龙江","安徽","江西","河南"],
    "港台": ["香港","TVB","台湾","台视","中视","华视","翡翠","三立"],
    "国际": ["BBC","CNN","NHK","FOX","HBO","Discovery"],
    "网络直播": ["斗鱼","虎牙","Bilibili","哔哩"]
}

# ------------------- 名称统一映射（可扩充） -------------------
name_map = {
    "CCTV-1": "CCTV-1综合", "CCTV1": "CCTV-1综合", "央视综合": "CCTV-1综合",
    "CCTV-2": "CCTV-2财经", "央视财经": "CCTV-2财经",
    "CCTV-3": "CCTV-3娱乐", "央视娱乐": "CCTV-3娱乐",
    "CCTV-4": "CCTV-4中文国际", "央视中文国际": "CCTV-4中文国际",
    "CCTV-5": "CCTV-5体育", "央视体育": "CCTV-5体育",
    "CCTV-6": "CCTV-6电影", "央视电影": "CCTV-6电影",
    "CCTV-7": "CCTV-7国防军事",
    "CCTV-8": "CCTV-8电视剧", "央视电视剧": "CCTV-8电视剧",
    "CCTV-9": "CCTV-9纪录", "央视纪录": "CCTV-9纪录",
    "CCTV-10": "CCTV-10科教", "央视科教": "CCTV-10科教",
    "CCTV-11": "CCTV-11戏曲", "央视戏曲": "CCTV-11戏曲",
    "CCTV-12": "CCTV-12社会与法", "央视社会与法": "CCTV-12社会与法",
    "CCTV-13": "CCTV-13新闻", "央视新闻": "CCTV-13新闻",
    "CCTV-14": "CCTV-14少儿", "央视少儿": "CCTV-14少儿",
    "CCTV-15": "CCTV-15音乐", "央视音乐": "CCTV-15音乐",
}

# ------------------- 初始化 channel_map -------------------
channel_map = {cat: defaultdict(list) for cat in categories}
channel_map["其他"] = defaultdict(list)

# ------------------- 读取可播源（并 sanitize） -------------------
all_pairs = []
if os.path.exists(input_file):
    lines = open(input_file, encoding="utf-8").read().splitlines()
    for i in range(0, len(lines)-1):
        if lines[i].startswith("#EXTINF"):
            ext = lines[i].strip()
            url = lines[i+1].strip()
            tname = sanitize_title_from_extinf(ext)
            all_pairs.append((ext, tname, url, False))

# 把自备源放前面（保证置顶）
# 先把组播放前，再把 http 放前（按你之前要求）
merged_pairs = []
for item in custom_multicast_pairs:
    merged_pairs.append(item)
for item in custom_http_pairs:
    merged_pairs.append(item)
# 然后拼接已经检测通过的可播源
merged_pairs.extend(all_pairs)
# merged_pairs 中每项是 (raw_extinf, cleaned_title, url, is_custom_bool)

# ------------------- 分类/统一名/去重/自备置顶 -------------------
for raw_extinf, title_name, url, is_custom in merged_pairs:
    # 标准化名称（先 name_map，再进一步清洗）
    title_std = name_map.get(title_name, title_name)
    title_std = normalize_spaces(remove_symbols_and_emoji(remove_control_chars(title_std)))

    # 找分类
    placed = False
    for cat, kws in categories.items():
        if any(kw.lower() in title_std.lower() for kw in kws):
            lst = channel_map[cat][title_std]
            if url not in lst:
                if is_custom:
                    # insert at front to ensure custom is first
                    lst.insert(0, url)
                else:
                    lst.append(url)
            placed = True
            break
    if not placed:
        lst = channel_map["其他"][title_std]
        if url not in lst:
            if is_custom:
                lst.insert(0, url)
            else:
                lst.append(url)

# ------------------- 排序规则 -------------------
cctv_order = ["CCTV-1综合","CCTV-2财经","CCTV-3娱乐","CCTV-4中文国际",
              "CCTV-5体育","CCTV-6电影","CCTV-7国防军事","CCTV-8电视剧",
              "CCTV-9纪录","CCTV-10科教","CCTV-11戏曲","CCTV-12社会与法",
              "CCTV-13新闻","CCTV-14少儿","CCTV-15音乐"]

province_order = ["北京","天津","河北","山西","内蒙古","辽宁","吉林","黑龙江",
                  "上海","江苏","浙江","安徽","福建","江西","山东","河南",
                  "湖北","湖南","广东","广西","海南","重庆","四川","贵州",
                  "云南","西藏","陕西","甘肃","青海","宁夏","新疆"]

category_order = ["央视","卫视","地方","港台","国际","网络直播","其他"]
summary_lines = ["#EXTM3U"]

# ------------------- 写文件（保证 group-title 与 logo 正确） -------------------
def build_logo_url_for_channel(title_std: str) -> str:
    """用清理后的 title_std 生成 logo 文件名并拼 raw URL（不会包含 extinf 残留）"""
    fname = safe_logo_name(title_std)
    if not fname:
        return ""
    # raw 格式
    return BASE_LOGO_RAW + fname + ".png"

for cat in category_order:
    # 排序频道名
    if cat == "央视":
        sorted_channels = sorted(channel_map[cat].keys(), key=lambda x: cctv_order.index(x) if x in cctv_order else 999)
    elif cat == "地方":
        sorted_channels = sorted(channel_map[cat].keys(), key=lambda x: (next((i for i,v in enumerate(province_order) if v in x), 999), x))
    else:
        sorted_channels = sorted(channel_map[cat].keys())

    out_path = os.path.join(output_dir, f"{cat}.m3u")
    with open(out_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write("#EXTM3U\n")
        for ch in sorted_channels:
            logo_url = build_logo_url_for_channel(ch)
            # 确保自备源在前（已经在插入时处理）
            urls = channel_map[cat][ch]
            for u in urls:
                # 严格写入规范的 EXTINF：tvg-name / tvg-logo / group-title
                tvg_name_safe = ch.replace('"', '')  # 去掉引号避免破坏格式
                f.write(f'#EXTINF:-1 tvg-name="{tvg_name_safe}" tvg-logo="{logo_url}" group-title="{cat}",{tvg_name_safe}\n')
                f.write(u + "\n")
                summary_lines.append(f'#EXTINF:-1 tvg-name="{tvg_name_safe}" tvg-logo="{logo_url}" group-title="{cat}",{tvg_name_safe}')
                summary_lines.append(u)

# 写 summary
with open(os.path.join(output_dir, "summary.m3u"), "w", encoding="utf-8", errors="ignore") as f:
    f.write("\n".join(summary_lines))

print("✅ classify.py 执行完成：已生成分类 m3u 与 summary.m3u（自备源置顶、特殊字符清理、group-title & tvg-logo 已规范）。")