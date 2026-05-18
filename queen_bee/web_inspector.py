"""网站检测模块 — 页面分析、断链检测、性能评估

对标OpenCode的网页检测能力，纯stdlib实现，无外部依赖。
"""

import re
import json
import gzip
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any

USER_AGENT = (
    "Mozilla/5.0 (compatible; EvaAgent/1.0; +https://github.com/nousresearch)"
)

MAX_LINKS_TO_CHECK = 20
LINK_CHECK_TIMEOUT = 10
LINK_CHECK_WORKERS = 5


# ── HTML解析工具（轻量，不依赖BeautifulSoup） ──────────────

def _extract_tag_content(html: str, tag: str) -> List[str]:
    """提取指定标签的完整内容（包括属性）"""
    pattern = rf"<{tag}\b[^>]*>(.*?)</{tag}>"
    return re.findall(pattern, html, flags=re.DOTALL | re.IGNORECASE)


def _extract_tag_attr(html: str, tag: str, attr: str) -> List[str]:
    """提取指定标签的某个属性值"""
    pattern = rf"<{tag}\b[^>]*?\b{attr}\s*=\s*['\"]([^'\"]*)['\"]"
    return re.findall(pattern, html, flags=re.IGNORECASE)


def _extract_self_closing_attr(html: str, tag: str, attr: str) -> List[str]:
    """提取自闭合标签的属性值（如 <img src=... />）"""
    pattern = rf"<{tag}\b[^>]*?\b{attr}\s*=\s*['\"]([^'\"]*)['\"]"
    return re.findall(pattern, html, flags=re.IGNORECASE)


def _count_tags(html: str, tag: str) -> int:
    """统计标签数量"""
    pattern = rf"<{tag}\b"
    return len(re.findall(pattern, html, flags=re.IGNORECASE))


def _get_meta_content(html: str, name: str) -> Optional[str]:
    """获取meta标签的content值"""
    pattern = rf'<meta\b[^>]*?\bname\s*=\s*["\']{re.escape(name)}["\'][^>]*?\bcontent\s*=\s*["\']([^"\']*)["\']'
    m = re.search(pattern, html, flags=re.IGNORECASE)
    if not m:
        # 也尝试 content 在 name 前面的情况
        pattern2 = rf'<meta\b[^>]*?\bcontent\s*=\s*["\']([^"\']*)["\'][^>]*?\bname\s*=\s*["\']{re.escape(name)}["\']'
        m = re.search(pattern2, html, flags=re.IGNORECASE)
    return m.group(1) if m else None


# ── HTTP请求工具 ──────────────────────────────────────────

def _fetch(url: str, timeout: int = 15) -> Dict[str, Any]:
    """抓取网页，返回原始响应数据"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"error": f"不支持的协议: {parsed.scheme}", "status_code": -1}

    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }

    start_time = time.time()
    try:
        req = Request(url, headers=req_headers)
        with urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read()
            elapsed = round(time.time() - start_time, 3)

            # 处理gzip
            encoding = resp.headers.get("Content-Encoding", "").lower()
            if "gzip" in encoding:
                try:
                    raw_body = gzip.decompress(raw_body)
                except Exception:
                    pass

            # 推断字符编码
            charset = "utf-8"
            content_type = resp.headers.get("Content-Type", "")
            ct_match = re.search(r"charset=([\w-]+)", content_type)
            if ct_match:
                charset = ct_match.group(1)

            try:
                html = raw_body.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                html = raw_body.decode("utf-8", errors="replace")

            return {
                "status_code": resp.status,
                "content_type": content_type,
                "content_encoding": resp.headers.get("Content-Encoding", ""),
                "headers": dict(resp.headers),
                "html": html,
                "raw_size": len(raw_body),
                "elapsed": elapsed,
                "url": resp.url,
            }

    except HTTPError as e:
        elapsed = round(time.time() - start_time, 3)
        try:
            error_body = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            error_body = ""
        return {
            "status_code": e.code,
            "error": f"HTTP {e.code}: {e.reason}",
            "html": error_body,
            "raw_size": len(error_body),
            "elapsed": elapsed,
            "url": url,
        }
    except URLError as e:
        elapsed = round(time.time() - start_time, 3)
        return {
            "status_code": -1,
            "error": f"网络错误: {e.reason}",
            "html": "",
            "raw_size": 0,
            "elapsed": elapsed,
            "url": url,
        }
    except TimeoutError:
        elapsed = round(time.time() - start_time, 3)
        return {
            "status_code": -1,
            "error": f"请求超时（{timeout}秒）",
            "html": "",
            "raw_size": 0,
            "elapsed": elapsed,
            "url": url,
        }
    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        return {
            "status_code": -1,
            "error": f"抓取失败: {e}",
            "html": "",
            "raw_size": 0,
            "elapsed": elapsed,
            "url": url,
        }


# ── 1. fetch_and_analyze ──────────────────────────────────

def fetch_and_analyze(url: str, timeout: int = 15) -> str:
    """抓取网页并进行全面分析

    检测项：
    - HTTP状态码、响应时间、页面大小
    - SEO问题（缺title/description/h1）
    - 链接数量、图片数量、脚本数量
    - 是否包含viewport、是否gzip压缩

    Args:
        url: 目标URL
        timeout: 超时秒数（默认15）

    Returns:
        JSON字符串，包含完整分析结果
    """
    result = _fetch(url, timeout)

    if "error" in result and result["status_code"] < 0:
        return json.dumps({
            "url": url,
            "status": result["status_code"],
            "error": result["error"],
            "elapsed": result.get("elapsed", 0),
        }, ensure_ascii=False, indent=2)

    html = result.get("html", "")
    status_code = result["status_code"]

    # ── SEO检测 ──────────────────────────────────────────
    seo_issues = []

    # 检查title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else None
    if not title:
        seo_issues.append("缺少 <title> 标签")
    elif len(title) < 10:
        seo_issues.append(f"title过短（{len(title)}字符）：'{title}'")
    elif len(title) > 70:
        seo_issues.append(f"title过长（{len(title)}字符，建议≤70）")

    # 检查meta description
    description = _get_meta_content(html, "description")
    if not description:
        seo_issues.append("缺少 <meta name='description'>")
    elif len(description) < 50:
        seo_issues.append(f"description过短（{len(description)}字符）")
    elif len(description) > 160:
        seo_issues.append(f"description过长（{len(description)}字符，建议≤160）")

    # 检查h1
    h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
    h1_count = len(h1_matches)
    if h1_count == 0:
        seo_issues.append("缺少 <h1> 标签")
    elif h1_count > 1:
        seo_issues.append(f"存在{h1_count}个 <h1> 标签（建议只保留1个）")

    # 检查viewport
    viewport = _get_meta_content(html, "viewport")
    has_viewport = bool(viewport)

    # ── 资源统计 ─────────────────────────────────────────
    link_count = _count_tags(html, "a")
    img_count = (_count_tags(html, "img") +
                 len(re.findall(r"<image\b", html, flags=re.IGNORECASE)))
    script_count = _count_tags(html, "script")
    css_count = len(re.findall(r'<link\b[^>]*?\brel\s*=\s*["\']stylesheet["\']',
                               html, flags=re.IGNORECASE))
    form_count = _count_tags(html, "form")
    iframe_count = _count_tags(html, "iframe")

    # 内联资源统计
    inline_styles = len(re.findall(r'<style\b', html, flags=re.IGNORECASE))
    inline_script_tags = len(re.findall(r'<script\b(?![^>]*\bsrc\s*=)[^>]*>',
                                        html, flags=re.IGNORECASE))
    inline_style_attrs = len(re.findall(r'\bstyle\s*=\s*["\']',
                                        html, flags=re.IGNORECASE))

    # ── gzip检测 ─────────────────────────────────────────
    content_encoding = result.get("content_encoding", "").lower()
    is_gzip = "gzip" in content_encoding

    # ── 构建响应 ─────────────────────────────────────────
    analysis = {
        "url": url,
        "final_url": str(result.get("url", url)),
        "status": status_code,
        "elapsed": result["elapsed"],
        "size_bytes": result["raw_size"],
        "size_kb": round(result["raw_size"] / 1024, 2),
        "content_type": result.get("content_type", ""),
        "is_gzip": is_gzip,
        "seo": {
            "title": title,
            "title_length": len(title) if title else 0,
            "description": description,
            "description_length": len(description) if description else 0,
            "h1_count": h1_count,
            "has_viewport": has_viewport,
            "issues": seo_issues,
            "score": max(0, 100 - len(seo_issues) * 15),
        },
        "resources": {
            "total_links": link_count,
            "images": img_count,
            "scripts": script_count,
            "css_files": css_count,
            "forms": form_count,
            "iframes": iframe_count,
            "inline_styles_tag": inline_styles,
            "inline_script_tag": inline_script_tags,
            "inline_style_attrs": inline_style_attrs,
        },
    }

    return json.dumps(analysis, ensure_ascii=False, indent=2)


# ── 2. check_links ───────────────────────────────────────

def check_links(url: str, timeout: int = 15) -> str:
    """检测页面中所有链接的有效性

    提取页面中所有 <a href> 链接，并发检查前20个的HTTP状态。

    Args:
        url: 目标URL
        timeout: 抓取页面超时秒数（默认15）

    Returns:
        JSON字符串，包含断链列表和统计信息
    """
    result = _fetch(url, timeout)

    if "error" in result and result["status_code"] < 0:
        return json.dumps({
            "url": url,
            "status": result["status_code"],
            "error": result["error"],
            "broken_links": [],
            "total_links": 0,
            "checked": 0,
        }, ensure_ascii=False, indent=2)

    html = result.get("html", "")

    # 提取所有a标签href
    hrefs = _extract_tag_attr(html, "a", "href")
    total_links = len(hrefs)

    if total_links == 0:
        return json.dumps({
            "url": url,
            "status": result["status_code"],
            "total_links": 0,
            "checked": 0,
            "broken_links": [],
            "valid_links": 0,
            "message": "页面中没有找到链接",
        }, ensure_ascii=False, indent=2)

    # 过滤和标准化链接
    normalized_links = []
    seen = set()
    for href in hrefs:
        href = href.strip()
        # 跳过空链接、锚点、javascript、mailto等
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        # 转为绝对URL
        absolute = urljoin(str(result.get("url", url)), href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if absolute not in seen:
            seen.add(absolute)
            normalized_links.append(absolute)

    unique_links = normalized_links[:MAX_LINKS_TO_CHECK]
    to_check_count = len(unique_links)

    # 并发检查链接
    broken_links = []
    valid_count = 0

    def _check_single_link(link_url: str) -> Dict:
        try:
            req = Request(link_url, headers={"User-Agent": USER_AGENT}, method="HEAD")
            with urlopen(req, timeout=LINK_CHECK_TIMEOUT) as resp:
                return {"url": link_url, "status": resp.status, "error": None}
        except HTTPError as e:
            return {"url": link_url, "status": e.code, "error": f"HTTP {e.code}: {e.reason}"}
        except URLError as e:
            return {"url": link_url, "status": -1, "error": f"连接失败: {e.reason}"}
        except TimeoutError:
            return {"url": link_url, "status": -1, "error": f"超时（{LINK_CHECK_TIMEOUT}秒）"}
        except Exception as e:
            return {"url": link_url, "status": -1, "error": str(e)}

    with ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS) as executor:
        futures = {executor.submit(_check_single_link, link): link for link in unique_links}
        for future in as_completed(futures):
            link_result = future.result()
            if link_result["status"] >= 400 or link_result["status"] < 0:
                broken_links.append(link_result)
            else:
                valid_count += 1

    # 构建结果
    check_result = {
        "url": url,
        "page_status": result["status_code"],
        "total_links": total_links,
        "unique_links": len(seen),
        "checked": to_check_count,
        "valid_links": valid_count,
        "broken_links": broken_links,
        "broken_count": len(broken_links),
        "summary": (
            f"共{total_links}个链接（去重后{len(seen)}个），"
            f"已检查前{to_check_count}个：{valid_count}个正常，{len(broken_links)}个异常"
        ),
    }

    return json.dumps(check_result, ensure_ascii=False, indent=2)


# ── 3. lighthouse_lite ───────────────────────────────────

def lighthouse_lite(url: str, timeout: int = 15) -> str:
    """轻量性能检测（对标Lighthouse）

    检测项：
    - 页面总大小(KB)
    - 资源数量（CSS/JS/图片）
    - 是否存在内联样式/脚本过多问题
    - 是否启用gzip压缩
    - 基础性能评分

    Args:
        url: 目标URL
        timeout: 超时秒数（默认15）

    Returns:
        JSON字符串，包含性能分析结果
    """
    result = _fetch(url, timeout)

    if "error" in result and result["status_code"] < 0:
        return json.dumps({
            "url": url,
            "status": result["status_code"],
            "error": result["error"],
            "score": 0,
        }, ensure_ascii=False, indent=2)

    html = result.get("html", "")
    raw_size = result["raw_size"]
    size_kb = round(raw_size / 1024, 2)

    # ── 资源统计 ─────────────────────────────────────────
    css_files = len(re.findall(
        r'<link\b[^>]*?\brel\s*=\s*["\']stylesheet["\']', html, flags=re.IGNORECASE))
    js_files = len(re.findall(
        r'<script\b[^>]*\bsrc\s*=', html, flags=re.IGNORECASE))
    img_tags = _count_tags(html, "img")

    inline_styles_tag = len(re.findall(r'<style\b', html, flags=re.IGNORECASE))
    inline_script_tags = len(re.findall(
        r'<script\b(?![^>]*\bsrc\s*=)[^>]*>', html, flags=re.IGNORECASE))
    inline_style_attrs = len(re.findall(r'\bstyle\s*=\s*["\']', html, flags=re.IGNORECASE))

    total_inline = inline_styles_tag + inline_script_tags + inline_style_attrs

    # ── gzip ─────────────────────────────────────────────
    content_encoding = result.get("content_encoding", "").lower()
    is_gzip = "gzip" in content_encoding

    # ── 性能评分（0-100） ───────────────────────────────
    score = 100
    issues = []
    warnings = []
    passed = []

    # 1. 页面大小
    if raw_size > 500_000:  # >500KB
        score -= 25
        issues.append(f"页面过大（{size_kb}KB），建议<500KB")
    elif raw_size > 200_000:  # >200KB
        score -= 10
        warnings.append(f"页面偏大（{size_kb}KB），考虑优化")
    else:
        passed.append(f"页面大小合理（{size_kb}KB）")

    # 2. gzip压缩
    if is_gzip:
        passed.append("已启用gzip压缩 ✓")
    else:
        score -= 20
        issues.append("未启用gzip压缩")

    # 3. 内联资源过多
    if total_inline > 20:
        score -= 15
        issues.append(f"内联样式/脚本过多（{total_inline}处），建议外置")
    elif total_inline > 10:
        score -= 5
        warnings.append(f"内联样式/脚本较多（{total_inline}处）")
    else:
        passed.append(f"内联资源使用合理（{total_inline}处）")

    # 4. 资源文件数量
    total_external = css_files + js_files
    if total_external > 30:
        score -= 15
        issues.append(f"外部资源过多（CSS:{css_files} + JS:{js_files} = {total_external}个）")
    elif total_external > 15:
        score -= 5
        warnings.append(f"外部资源较多（CSS:{css_files} + JS:{js_files} = {total_external}个）")
    else:
        passed.append(f"外部资源数量合理（CSS:{css_files} JS:{js_files}）")

    # 5. 图片
    if img_tags > 30:
        score -= 5
        warnings.append(f"图片数量较多（{img_tags}张），考虑懒加载")
    else:
        passed.append(f"图片数量合理（{img_tags}张）")

    score = max(0, score)

    performance = {
        "url": url,
        "status": result["status_code"],
        "elapsed": result["elapsed"],
        "total_size_kb": size_kb,
        "total_size_bytes": raw_size,
        "is_gzip": is_gzip,
        "resources": {
            "css_files": css_files,
            "js_files": js_files,
            "img_tags": img_tags,
            "total_external": total_external,
            "inline_style_tags": inline_styles_tag,
            "inline_script_tags": inline_script_tags,
            "inline_style_attrs": inline_style_attrs,
            "total_inline": total_inline,
        },
        "score": score,
        "grade": _score_to_grade(score),
        "issues": issues,
        "warnings": warnings,
        "passed": passed,
    }

    return json.dumps(performance, ensure_ascii=False, indent=2)


def _score_to_grade(score: int) -> str:
    """分数转为等级"""
    if score >= 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "F"


# ── 便捷组合函数 ─────────────────────────────────────────

def full_report(url: str, timeout: int = 20) -> str:
    """一键生成完整检测报告（分析+断链+性能）"""
    analysis = json.loads(fetch_and_analyze(url, timeout))
    links = json.loads(check_links(url, timeout))
    perf = json.loads(lighthouse_lite(url, timeout))

    report = {
        "url": url,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": analysis.get("status", -1),
        "analysis": analysis,
        "links_check": {
            "total": links.get("total_links", 0),
            "broken": links.get("broken_count", 0),
            "broken_details": links.get("broken_links", []),
        },
        "performance": {
            "score": perf.get("score", 0),
            "grade": perf.get("grade", "F"),
            "size_kb": perf.get("total_size_kb", 0),
            "is_gzip": perf.get("is_gzip", False),
            "issues": perf.get("issues", []),
        },
    }

    return json.dumps(report, ensure_ascii=False, indent=2)
