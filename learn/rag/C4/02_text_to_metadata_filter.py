from dotenv import load_dotenv
load_dotenv("../../.env")
from langchain_community.document_loaders import BiliBiliLoader
from bilibili_api.utils import network

# aiohttp 默认可能请求 Brotli (br)，某些 Bilibili 响应无法正确解码。
# 只协商 gzip/deflate，不关闭 SSL 验证，也不修改第三方包文件。
network.HEADERS["Accept-Encoding"] = "gzip, deflate"
# 1. 初始化视频数据
video_urls = [
    "https://www.bilibili.com/video/BV1Bo4y1A7FU",
    "https://www.bilibili.com/video/BV1ug4y157xA",
    "https://www.bilibili.com/video/BV1yh411V7ge",
]

bili = []
try:
    loader = BiliBiliLoader(video_urls=video_urls)
    docs = loader.load()
    for doc in docs:
        original = doc.metadata

        # 提取基本元数据字段
        metadata = {
            'title': original.get('title', '未知标题'),
            'author': original.get('owner', {}).get('name', '未知作者'),
            'source': original.get('bvid', '未知ID'),
            'view_count': original.get('stat', {}).get('view', 0),
            'length': original.get('duration', 0),
        }

        doc.metadata = metadata
        bili.append(doc)
except Exception as e:
    message = str(e)
    if "412" in message:
        print("加载BiliBili视频失败：Bilibili 返回 412（风控拦截）。请稍后重试，或检查登录状态及当前网络。")
    else:
        print(f"加载BiliBili视频失败: {message}")

print()
