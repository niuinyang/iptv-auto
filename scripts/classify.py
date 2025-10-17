import os

input_file = "output/working.m3u"
output_dir = "output"

categories = {
    "央视": ["CCTV", "央视"],
    "卫视": ["卫视"],
    "地方": ["山东", "江苏", "浙江", "广东", "北京", "上海", "天津"],
    "港台": ["香港", "TVB", "台湾", "台视", "中视", "华视", "翡翠"],
    "国际": ["BBC", "CNN", "NHK", "FOX", "HBO", "Discovery"],
    "网络直播": ["斗鱼", "虎牙", "Bilibili", "哔哩"],
}

os.makedirs(output_dir, exist_ok=True)

data = open(input_file, encoding="utf-8").read().splitlines()
pairs = [(data[i], data[i+1]) for i in range(0, len(data)-1) if data[i].startswith("#EXTINF")]

files = {k: ["#EXTM3U"] for k in categories}
files["其他"] = ["#EXTM3U"]

for title, url in pairs:
    added = False
    for cat, kws in categories.items():
        if any(kw.lower() in title.lower() for kw in kws):
            files[cat].append(title)
            files[cat].append(url)
            added = True
            break
    if not added:
        files["其他"].append(title)
        files["其他"].append(url)

for cat, content in files.items():
    with open(os.path.join(output_dir, f"{cat}.m3u"), "w", encoding="utf-8") as f:
        f.write("\n".join(content))

print("✅ 分类完成！")
