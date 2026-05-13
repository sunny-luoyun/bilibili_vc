import http.client
import ssl
import json
import time
from datetime import datetime

# 禁用SSL验证（macOS虚拟环境常见问题）
context = ssl._create_unverified_context()
conn = http.client.HTTPSConnection("api.bilibili.com", context=context)

# 请求头必须带User-Agent
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

# 请求视频信息（bvid换成你实际想查的）
bvid = "BV1exRqBaEYg"   # 注意：这可能是无效id，可以换成一个真实存在的，比如 BV1GJ411x7h7
conn.request("GET", f"/x/web-interface/view?bvid={bvid}", headers=headers)

response = conn.getresponse()
data = response.read().decode('utf-8')
conn.close()

# 解析JSON
try:
    result = json.loads(data)
except json.JSONDecodeError:
    print("返回内容不是有效JSON，原始数据：", data)
    exit(1)

# 检查接口返回码
if result.get("code") != 0:
    print(f"接口返回错误 code={result.get('code')}, message={result.get('message')}")
    exit(1)

# 提取 data 部分
info = result.get("data", {})
if not info:
    print("未获取到视频数据")
    exit(1)

# 辅助函数：时间戳转字符串
def ts_to_str(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "未知"

# 输出整理后的信息
print("=" * 50)
print(f"视频标题：{info.get('title', '无标题')}")
print(f"UP主：{info.get('owner', {}).get('name', '未知')} (mid: {info.get('owner', {}).get('mid', '未知')})")
print(f"BV号：{info.get('bvid', '未知')}  |  AV号：aid={info.get('aid', '未知')}")
print(f"分区：{info.get('tname', '未知')} (tid={info.get('tid', '未知')})")
print(f"发布时间：{ts_to_str(info.get('pubdate'))}")
print(f"时长：{info.get('duration', 0)}秒")
print("统计信息：")
stat = info.get("stat", {})
print(f"  播放量：{stat.get('view', 0):,}")
print(f"  弹幕数：{stat.get('danmaku', 0):,}")
print(f"  评论数：{stat.get('reply', 0):,}")
print(f"  点赞数：{stat.get('like', 0):,}")
print(f"  硬币数：{stat.get('coin', 0):,}")
print(f"  收藏数：{stat.get('favorite', 0):,}")
print(f"  分享数：{stat.get('share', 0):,}")
print("=" * 50)