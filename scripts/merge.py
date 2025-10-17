import requests, os

sources_file = "m3u_sources/list.txt"
output_file = "output/total.m3u"

os.makedirs("output", exist_ok=True)

merged = "#EXTM3U\n"
with open(sources_file, "r", encoding="utf-8") as f:
    for url in f:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        print(f"📡 Fetching: {url}")
        try:
            if url.startswith("http"):
                text = requests.get(url, timeout=10).text
            else:
                with open(url, encoding="utf-8") as f2:
                    text = f2.read()
            merged += "\n".join([l for l in text.splitlines() if not l.strip().startswith("#EXTM3U")]) + "\n"
        except Exception as e:
            print(f"❌ Failed: {url} ({e})")

with open(output_file, "w", encoding="utf-8") as f:
    f.write(merged)

print(f"✅ 合并完成: {output_file}")
