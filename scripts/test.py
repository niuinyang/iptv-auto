import requests, os

input_file = "output/total.m3u"
output_file = "output/working.m3u"

os.makedirs("output", exist_ok=True)

lines = open(input_file, encoding="utf-8").read().splitlines()
working = ["#EXTM3U"]

for i in range(len(lines)):
    if lines[i].startswith("#EXTINF"):
        url = lines[i+1] if i+1 < len(lines) else ""
        try:
            if url.startswith("http"):
                r = requests.head(url, timeout=5)
                if r.status_code == 200:
                    working.append(lines[i])
                    working.append(url)
                    print(f"✅ OK: {url}")
                else:
                    print(f"❌ {r.status_code}: {url}")
        except:
            print(f"❌ Failed: {url}")

open(output_file, "w", encoding="utf-8").write("\n".join(working))
print(f"✅ 检测完成: {output_file}")
