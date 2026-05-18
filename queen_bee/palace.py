"""Memory Palace — 文件级持久化记忆系统（潮汐记忆优化版 v2）

优化项：
① PalaceIndex 内存索引替代 grep 子进程
② _save_map 批量写入（累积5次或间隔30秒再flush）
③ 锚点文件缓存（首次读取后按 st_mtime 校验）
④ jieba 可选分词 + BM25 排序召回
"""

import json
import re
import hashlib
import time
import math
import atexit
from datetime import datetime
from pathlib import Path
from typing import Optional


# jieba 懒加载 — 仅在分词需要时导入
_jieba_available = None


# ═══════════════════════════════════════════
# ③ 锚点文件缓存（模块级全局，跨 Palace 实例共享）
# ═══════════════════════════════════════════
_anchor_cache: dict = {}  # {path_str: {"content": str, "mtime": float}}


def _load_anchors_cached(anchor_path: Path) -> str:
    """加载锚点文件，带 st_mtime 缓存校验；只在文件变更时重读"""
    key = str(anchor_path)
    if not anchor_path.exists():
        _anchor_cache.pop(key, None)
        return ""
    try:
        stat = anchor_path.stat()
        cached = _anchor_cache.get(key)
        if cached and cached["mtime"] == stat.st_mtime:
            return cached["content"]
    except OSError:
        return ""
    try:
        content = anchor_path.read_text(encoding="utf-8")
        _anchor_cache[key] = {"content": content, "mtime": anchor_path.stat().st_mtime}
        return content
    except Exception:
        return ""


# ═══════════════════════════════════════════
# ① 内存索引 PalaceIndex
# ═══════════════════════════════════════════
class PalaceIndex:
    """启动时加载所有 .md 文件到内存，提供 O(1) 标签查找和 BM25 关键词检索"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.by_tag: dict[str, list[dict]] = {}
        self.by_type: dict[str, list[dict]] = {}
        self.all_docs: list[dict] = []  # [{path, rel_path, meta, body}]
        self._built = False

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        """解析 YAML 前置元数据 (--- 分隔)"""
        content = content.strip()
        if not content.startswith("---"):
            return {}, content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content
        meta = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        return meta, parts[2].strip()

    def build(self):
        """扫描 base_dir 下所有 .md 文件，填充索引"""
        self.by_tag.clear()
        self.by_type.clear()
        self.all_docs.clear()

        for md_file in self.base_dir.rglob("*.md"):
            if "map.json" in str(md_file) or "anchors/" in str(md_file):
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            meta, body = self._parse_frontmatter(text)
            rel_path = str(md_file.relative_to(self.base_dir))

            doc = {
                "path": md_file,
                "rel_path": rel_path,
                "meta": meta,
                "body": body,
            }
            self.all_docs.append(doc)

            # 按 type 索引
            doc_type = meta.get("type", "unknown")
            self.by_type.setdefault(doc_type, []).append(doc)

            # 按 tag 索引
            tags_str = meta.get("tags", "")
            if tags_str:
                tags_clean = tags_str.strip("[]").replace("'", "").replace('"', "")
                for tag in tags_clean.split(","):
                    tag = tag.strip()
                    if tag:
                        self.by_tag.setdefault(tag, []).append(doc)

        self._built = True

    def get_by_tag(self, tag: str) -> list[dict]:
        """O(1) 标签查找"""
        return self.by_tag.get(tag, [])

    def get_by_type(self, doc_type: str) -> list[dict]:
        """O(1) 类型查找"""
        return self.by_type.get(doc_type, [])

    def search_keywords(self, keywords: list[str]) -> list[dict]:
        """BM25 风格关键词搜索，返回按相关度排序的文档列表"""
        if not keywords or not self.all_docs:
            return []

        N = len(self.all_docs)
        doc_lengths = [len(d["body"]) for d in self.all_docs]
        avg_dl = sum(doc_lengths) / max(N, 1)

        # 计算每个关键词的文档频率
        df = {}
        for kw in keywords:
            df[kw] = sum(1 for d in self.all_docs if kw in d["body"])

        k1 = 1.5
        b = 0.75

        scored = []
        for i, doc in enumerate(self.all_docs):
            body = doc["body"]
            doc_len = doc_lengths[i]
            score = 0.0
            for kw in keywords:
                n = df.get(kw, 0)
                if n == 0:
                    continue
                # IDF
                idf = math.log((N - n + 0.5) / (n + 0.5) + 1.0)
                # TF
                tf = body.count(kw)
                if tf == 0:
                    continue
                # BM25
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * doc_len / max(avg_dl, 1))
                score += idf * numerator / denominator

            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored]

    def add_doc(self, rel_path: str, meta: dict, body: str):
        """增量添加文档到索引（remember() 时调用）"""
        doc = {
            "path": self.base_dir / rel_path,
            "rel_path": rel_path,
            "meta": meta,
            "body": body,
        }
        self.all_docs.append(doc)

        doc_type = meta.get("type", "unknown")
        self.by_type.setdefault(doc_type, []).append(doc)

        tags_val = meta.get("tags", "")
        if tags_val:
            if isinstance(tags_val, list):
                tag_list = tags_val
            else:
                # frontmatter 解析出的字符串格式 "[tag1, tag2]"
                tags_clean = str(tags_val).strip("[]").replace("'", "").replace('"', "")
                tag_list = [t.strip() for t in tags_clean.split(",") if t.strip()]
            for tag in tag_list:
                if tag:
                    self.by_tag.setdefault(tag, []).append(doc)


# ═══════════════════════════════════════════
# Palace 主类（含②批量写入）
# ═══════════════════════════════════════════
class Palace:
    """Memory Palace — 文件级持久化记忆系统（潮汐记忆优化版）"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir or Path.home() / ".eva_palace")
        self.map_path = self.base_dir / "map.json"
        self._map: dict = {}
        self._ensure_dirs()
        self._map = self._load_map()

        # ① 内存索引
        self._index = PalaceIndex(self.base_dir)
        self._index.build()

        # ② 批量写入
        self._save_pending = 0
        self._last_save_time = time.time()
        self._save_batch = 5       # 累积5次 remember 再写
        self._save_interval = 30   # 或间隔30秒

        # 注册进程退出时 flush
        atexit.register(self._flush_map)

    def _ensure_dirs(self) -> None:
        """创建子目录结构"""
        for d in ("code", "fixes", "decisions", "context", "mirrors", "anchors"):
            (self.base_dir / d).mkdir(parents=True, exist_ok=True)

    def _load_map(self) -> dict:
        """加载 map.json 索引，不存在时返回默认结构"""
        if self.map_path.exists():
            return json.loads(self.map_path.read_text())
        return {"code": {}, "fixes": {}, "decisions": [], "tags_index": {}}

    def _save_map(self) -> None:
        """② 批量写入：累积次数或超时间隔后才 flush"""
        self._save_pending += 1
        now = time.time()
        if self._save_pending >= self._save_batch or (now - self._last_save_time) >= self._save_interval:
            self._flush_map()

    def _flush_map(self) -> None:
        """立即写入 map.json（强制 flush）"""
        try:
            self.map_path.write_text(
                json.dumps(self._map, ensure_ascii=False, indent=2)
            )
        except Exception:
            pass
        self._save_pending = 0
        self._last_save_time = time.time()

    _parse_frontmatter = staticmethod(PalaceIndex._parse_frontmatter)

    @staticmethod
    def _build_filename(metadata: dict) -> str:
        """根据元数据生成唯一文件名: {timestamp}_{hash}.md"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw = f"{metadata.get('type', 'unknown')}-{metadata.get('title', ts)}"
        h = hashlib.md5(raw.encode()).hexdigest()[:8]
        return f"{ts}_{h}.md"

    def remember(
        self,
        type: str,
        title: str,
        content: str,
        tags: list[str] = None,
        lang: str = None,
        file: str = None,
    ) -> dict:
        """Store a memory. Returns dict with memory_id, path, type."""
        tags = tags or []

        metadata = {
            "type": type,
            "title": title,
            "date": datetime.now().isoformat(),
        }
        if lang:
            metadata["lang"] = lang
        if file:
            metadata["file"] = file
        if tags:
            metadata["tags"] = tags

        type_dirs = {
            "code_snippet": "code",
            "bug_fix": "fixes",
            "decision": "decisions",
            "pattern": "code",
            "context": "context",
            "mirror": "mirrors",
        }
        subdir = type_dirs.get(type, "mirrors")

        filename = self._build_filename(metadata)
        filepath = self.base_dir / subdir / filename

        fm_lines = [
            f"type: {type}",
            f"title: {title}",
            f"date: {metadata['date']}",
        ]
        if lang:
            fm_lines.append(f"lang: {lang}")
        if file:
            fm_lines.append(f"file: {file}")
        if tags:
            fm_lines.append(f"tags: [{', '.join(tags)}]")

        frontmatter = "\n".join(fm_lines)
        full_text = f"---\n{frontmatter}\n---\n\n{content}\n"

        filepath.write_text(full_text)

        rel_path = f"{subdir}/{filename}"

        if type in ("code_snippet", "pattern"):
            code_lang = lang or "general"
            if code_lang not in self._map["code"]:
                self._map["code"][code_lang] = []
            if rel_path not in self._map["code"][code_lang]:
                self._map["code"][code_lang].append(rel_path)
        elif type == "bug_fix":
            bug_key = hashlib.md5(title.encode()).hexdigest()[:8]
            self._map["fixes"][bug_key] = rel_path
        elif type in ("decision",):
            if rel_path not in self._map["decisions"]:
                self._map["decisions"].append(rel_path)

        for tag in tags:
            if tag not in self._map["tags_index"]:
                self._map["tags_index"][tag] = []
            if rel_path not in self._map["tags_index"][tag]:
                self._map["tags_index"][tag].append(rel_path)

        # ① 增量更新内存索引
        self._index.add_doc(rel_path, metadata, content)

        # ② 批量写入（非立即）
        self._save_map()

        return {
            "memory_id": filename.replace(".md", ""),
            "path": str(filepath),
            "type": type,
        }

    def recall(self, query: str = "") -> list[dict]:
        """Search memories via memory index. Returns list of {memory_id, path, type, title, preview}."""
        results = []
        seen = set()

        if query:
            from .semantic import expand
            search_terms = expand(query)

            # ① 语义扩展标签匹配（O(1)）
            for term in search_terms:
                if term in self._map["tags_index"]:
                    for rel_path in self._map["tags_index"][term]:
                        if rel_path not in seen:
                            doc = self._doc_from_index(rel_path)
                            if doc:
                                results.append(self._to_result(doc))
                                seen.add(rel_path)

            # ② 原始关键词 BM25 检索
            keywords = self._extract_keywords(query)
            if keywords:
                matched = self._index.search_keywords(keywords)
                for doc in matched:
                    if doc["rel_path"] not in seen:
                        results.append(self._to_result(doc))
                        seen.add(doc["rel_path"])
        else:
            # 无查询时返回最近文档
            all_files = sorted(
                self.base_dir.rglob("*.md"),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            for fp in all_files[:20]:
                if "map.json" in str(fp):
                    continue
                rel_path = str(fp.relative_to(self.base_dir))
                if rel_path not in seen:
                    doc = self._doc_from_index(rel_path)
                    if doc is None:
                        try:
                            meta, body = self._parse_frontmatter(fp.read_text())
                            doc = {"rel_path": rel_path, "meta": meta, "body": body}
                        except Exception:
                            continue
                    results.append(self._to_result(doc))
                    seen.add(rel_path)

        return results[:20]

    def _doc_from_index(self, rel_path: str) -> Optional[dict]:
        """从内存索引查找文档"""
        for doc in self._index.all_docs:
            if doc["rel_path"] == rel_path:
                return doc
        # fallback: 直接读取
        fp = self.base_dir / rel_path
        if fp.exists():
            try:
                meta, body = self._parse_frontmatter(fp.read_text())
                return {"rel_path": rel_path, "meta": meta, "body": body}
            except Exception:
                pass
        return None

    @staticmethod
    def _to_result(doc: dict) -> dict:
        """将索引文档转为结果字典"""
        rel_path = doc["rel_path"]
        meta = doc.get("meta", {})
        body = doc.get("body", "")
        return {
            "memory_id": rel_path.split("/")[-1].replace(".md", ""),
            "path": str(rel_path),
            "type": meta.get("type", "unknown"),
            "title": meta.get("title", ""),
            "preview": body[:200],
        }

    def summary(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        mirrors_dir = self.base_dir / "mirrors"
        mirrors_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for fp in sorted(mirrors_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if fp.stem == today:
                continue
            if datetime.fromtimestamp(fp.stat().st_mtime).strftime("%Y-%m-%d") != today:
                continue
            meta, body = self._parse_frontmatter(fp.read_text())
            title = meta.get("title", fp.stem)
            preview = body[:100].replace("\n", " ")
            items.append(f"- **{title}**: {preview}")
        lines = [f"# Mirror Summary - {today}"] + items + [""]
        summary_path = mirrors_dir / f"{today}.md"
        summary_path.write_text("\n".join(lines))
        return str(summary_path)

    def context_snapshot(self, state: dict) -> None:
        state = {k: v for k, v in state.items() if k != "updated_at"}
        state["updated_at"] = datetime.now().isoformat()
        nuwa_path = self.base_dir / "context" / "nuwa.json"
        nuwa_path.parent.mkdir(parents=True, exist_ok=True)
        nuwa_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    # ── 潮汐记忆：按需检索 ──

    def _extract_keywords(self, query: str) -> list[str]:
        """④ 中文关键词提取 — jieba 精确分词（可选依赖）+ 二元词组 fallback"""
        if not query:
            return []

        global _jieba_available
        if _jieba_available is None:
            try: import jieba; _jieba_available = True
            except ImportError: _jieba_available = False
        if _jieba_available:
            # jieba 精确分词
            words = list(jieba.cut(query))
            stop = set("的了吗是在我你他她它们和与或不就都也要会个这那有对为所以可以因为但是如果虽然然而而且然后之其及被把从到着等，。！？、；：\"\"''（）…— \t\n\r")
            result = []
            seen = set()
            for w in words:
                w = w.strip()
                if w in stop or w in seen: continue
                seen.add(w)
                if len(w) >= 2 or (len(w) == 1 and '\u4e00' <= w <= '\u9fff'):
                    result.append(w)
            return result[:8]

        # fallback: 二元词组切分（原逻辑）
        words = []
        cjk_buf = []
        for ch in query:
            if '\u4e00' <= ch <= '\u9fff':
                cjk_buf.append(ch)
            else:
                if cjk_buf:
                    cjk_str = ''.join(cjk_buf)
                    words.append(cjk_str)
                    for i in range(len(cjk_buf) - 1):
                        words.append(''.join(cjk_buf[i:i+2]))
                    cjk_buf = []
        if cjk_buf:
            cjk_str = ''.join(cjk_buf)
            words.append(cjk_str)
            for i in range(len(cjk_buf) - 1):
                words.append(''.join(cjk_buf[i:i+2]))

        stop = set("的了吗是在我你他她它们和与或不就都也要会个这那有对为所以可以因为但是如果虽然然而而且然后之其及被把从到着等")
        seen = set()
        result = []
        for w in words:
            if w in stop or w in seen:
                continue
            seen.add(w)
            # 保留2字以上词 + 非停用单字
            if len(w) >= 2 or (len(w) == 1 and '\u4e00' <= w <= '\u9fff'):
                result.append(w)
        return result[:8]

    def context_for(self, user_message: str, max_chars: int = 800) -> str:
        """潮汐检索：通过内存索引检索记忆宫殿，返回命中文档。
        只在关键词匹配时注入，否则返回空字符串。
        注入时附带严格调取指令——禁止 LLM 用自己的知识补充或改写。
        """
        if not user_message:
            return ""

        keywords = self._extract_keywords(user_message)
        if not keywords:
            return ""

        # ① 通过内存索引检索（替代 grep 子进程）
        matched = self._index.search_keywords(keywords)
        if not matched:
            return ""

        lines = []
        count = 0
        for doc in matched:
            meta = doc.get("meta", {})
            body = doc.get("body", "")
            if count == 0:
                lines.append("【⚠️ 记忆调取指令——以下内容来自记忆宫殿，是已确认的档案。】")
                lines.append("【你不得用自己的训练知识补充或改写。请直接复述档案内容。如档案不完整，说「档案内容如下」然后照念。】")
            lines.append(f"\n### [{meta.get('type', '?')}] {meta.get('title', doc['rel_path'])}\n```\n{body[:600]}\n```")
            count += 1
            if count >= 3:
                break

        result = "\n".join(lines)
        return result[:max_chars]


# ═══════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════
_palace: Optional[Palace] = None


def get_palace() -> Palace:
    """获取 Palace 全局单例"""
    global _palace
    if _palace is None:
        _palace = Palace()
    return _palace
