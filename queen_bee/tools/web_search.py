"""网络抓取工具 — 仅使用Python内置urllib，无需外部依赖"""

import json
import re
import gzip
import io
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from typing import Optional


USER_AGENT = (
    "Mozilla/5.0 (compatible; EvaAgent/1.0; +https://github.com/nousresearch)"
)

MAX_CONTENT_LENGTH = 100_000  # 最大返回内容长度（字符）


def fetch_url(
    url: str,
    method: str = "GET",
    timeout: int = 15,
    headers: Optional[dict] = None,
    data: Optional[bytes] = None,
) -> str:
    """使用urllib抓取网页内容，返回文本

    Args:
        url: 目标URL
        method: HTTP方法，默认GET
        timeout: 超时秒数（默认15）
        headers: 额外的请求头字典
        data: POST请求体（bytes），如果提供则自动使用POST

    Returns:
        JSON字符串，包含 status, url, content_type, text, content_length 字段
    """
    # 验证URL格式
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return json.dumps({
            "status": -1,
            "url": url,
            "error": f"不支持的协议: {parsed.scheme}",
            "text": "",
        }, ensure_ascii=False)

    # 构建请求头
    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,text/plain,application/json,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }
    if headers:
        req_headers.update(headers)

    # 如果提供了data，自动使用POST
    actual_method = "POST" if data is not None else method

    try:
        req = Request(url, data=data, headers=req_headers, method=actual_method)
        with urlopen(req, timeout=timeout) as response:
            # 处理gzip压缩
            raw_body = response.read()
            encoding = response.headers.get("Content-Encoding", "").lower()
            if "gzip" in encoding:
                try:
                    raw_body = gzip.decompress(raw_body)
                except Exception:
                    pass  # 不是有效的gzip，使用原始数据

            # 推断字符编码
            charset = "utf-8"
            content_type = response.headers.get("Content-Type", "")
            ct_match = re.search(r"charset=([\w-]+)", content_type)
            if ct_match:
                charset = ct_match.group(1)

            # 解码文本
            try:
                text = raw_body.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                text = raw_body.decode("utf-8", errors="replace")

            # 提取纯文本（简单的HTML标签清理）
            text = _strip_html(text)

            # 截断过长内容
            original_length = len(text)
            if len(text) > MAX_CONTENT_LENGTH:
                text = text[:MAX_CONTENT_LENGTH] + f"\n...(已截断，原始长度{original_length}字符)"

            return json.dumps({
                "status": response.status,
                "url": response.url,
                "content_type": content_type,
                "text": text,
                "content_length": original_length,
            }, ensure_ascii=False)

    except HTTPError as e:
        # 尝试读取错误响应体
        try:
            error_body = e.read().decode("utf-8", errors="replace")[:1000]
        except Exception:
            error_body = ""
        return json.dumps({
            "status": e.code,
            "url": url,
            "error": f"HTTP {e.code}: {e.reason}",
            "text": error_body,
        }, ensure_ascii=False)

    except URLError as e:
        return json.dumps({
            "status": -1,
            "url": url,
            "error": f"网络错误: {e.reason}",
            "text": "",
        }, ensure_ascii=False)

    except TimeoutError:
        return json.dumps({
            "status": -1,
            "url": url,
            "error": f"请求超时（{timeout}秒）",
            "text": "",
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": -1,
            "url": url,
            "error": f"抓取失败: {e}",
            "text": "",
        }, ensure_ascii=False)


def _strip_html(text: str) -> str:
    """简单的HTML标签清理，提取可读文本"""
    # 移除script和style标签及其内容
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)

    # 移除HTML注释
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)

    # 将常见块级标签替换为换行
    text = re.sub(r"</?(?:br|p|div|li|h[1-6]|tr|table|section|article|header|footer|nav|main|aside)[^>]*>",
                  "\n", text, flags=re.IGNORECASE)

    # 移除所有剩余标签
    text = re.sub(r"<[^>]+>", " ", text)

    # 解码常见HTML实体
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")

    # 清理空白
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text
