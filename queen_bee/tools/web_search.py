def fetch_url(url: str, timeout: int = 15) -> str:
    import urllib.request, json, re
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", text)
            return json.dumps({"status": resp.status, "text": text[:3000]})
    except Exception as e:
        return json.dumps({"status": -1, "error": str(e)})
