"""从带文字层的《中华人民共和国民法典》PDF 抽取全部法条。"""

import bisect
import re
from pathlib import Path

from pypdf import PdfReader

from knowledge.models import LegalChunk


ARTICLE_MARKER = re.compile(
    r"^第([零一二三四五六七八九十百千]+)条[\s　]*(?:【([^】]+)】)?",
    re.MULTILINE,
)


def chinese_number_to_int(value: str) -> int:
    digits = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    result = 0
    current = 0
    for character in value:
        if character in digits:
            current = digits[character]
        elif character in units:
            result += (current or 1) * units[character]
            current = 0
        else:
            raise ValueError(f"无法识别的中文数字：{value}")
    return result + current


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", "", text)
    return re.sub(r"\n+", "\n", text).strip()


def extract_civil_code(pdf_path: Path) -> list[LegalChunk]:
    reader = PdfReader(pdf_path)
    pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
    page_starts: list[int] = []
    cursor = 0
    for page in pages:
        page_starts.append(cursor)
        cursor += len(page) + 1

    full_text = "\n".join(pages)
    markers = list(ARTICLE_MARKER.finditer(full_text))
    chunks: list[LegalChunk] = []
    seen: set[int] = set()
    for index, marker in enumerate(markers):
        number = chinese_number_to_int(marker.group(1))
        # PDF 目录也含有“第X条”时，只保留正文中首次出现的完整且顺序递增条文。
        if number in seen or (chunks and number <= (chunks[-1].article_number or 0)):
            continue
        end = markers[index + 1].start() if index + 1 < len(markers) else len(full_text)
        content = normalize_text(full_text[marker.end():end])
        if len(content) < 5:
            continue
        start_page = bisect.bisect_right(page_starts, marker.start())
        end_page = bisect.bisect_right(page_starts, max(marker.start(), end - 1))
        title = marker.group(2) or ""
        article_label = f"第{marker.group(1)}条"
        chunks.append(LegalChunk(
            chunk_id=f"civil-code-{number}",
            law_name="中华人民共和国民法典",
            article_number=number,
            article_label=article_label,
            article_title=title,
            content=content,
            retrieval_text=(
                f"《中华人民共和国民法典》{article_label} 第{number}条 "
                f"{title} {content}"
            ),
            source_file=pdf_path.name,
            source_pages=list(range(start_page, end_page + 1)),
            effective_date="2021-01-01",
            status="现行有效",
            metadata={
                "issuing_authority": "全国人民代表大会",
                "document_number": "中华人民共和国主席令第四十五号",
                "promulgation_date": "2020-05-28",
            },
        ))
        seen.add(number)

    expected = list(range(1, 1261))
    actual = [chunk.article_number for chunk in chunks]
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        raise RuntimeError(
            f"法条抽取不完整：得到 {len(chunks)} 条，缺失条号 {missing[:20]}"
        )
    return chunks
