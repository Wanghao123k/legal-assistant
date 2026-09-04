"""从《民法典》PDF 中抽取适合 RAG 演示的 50 条常用法条。"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


SELECTED_ARTICLES = {
    13: "自然人民事权利能力",
    17: "成年人与未成年人年龄标准",
    18: "完全民事行为能力人",
    19: "限制民事行为能力的未成年人",
    20: "无民事行为能力的未成年人",
    143: "民事法律行为有效条件",
    144: "无民事行为能力人实施的行为",
    145: "限制民事行为能力人实施的行为",
    146: "虚假意思表示",
    148: "欺诈实施的民事法律行为",
    153: "违反强制性规定及公序良俗",
    157: "民事法律行为无效后的处理",
    188: "普通诉讼时效",
    209: "不动产登记",
    214: "不动产物权变动生效时间",
    215: "合同效力与物权登记相区分",
    240: "所有权权能",
    282: "建设单位、物业服务人利用共有部分的收益",
    287: "业主合法权益保护",
    288: "相邻关系处理原则",
    301: "处分共有不动产或者动产",
    465: "依法成立合同的效力",
    466: "合同条款解释",
    469: "合同形式",
    470: "合同主要条款与示范文本",
    490: "书面合同成立时间",
    496: "格式条款",
    497: "格式条款无效",
    509: "合同履行原则",
    563: "合同法定解除",
    577: "违约责任",
    584: "损害赔偿范围",
    585: "约定违约金",
    657: "赠与合同",
    658: "赠与撤销",
    1042: "婚姻家庭禁止性规定",
    1043: "婚姻家庭倡导性规定",
    1046: "结婚自愿",
    1047: "法定结婚年龄",
    1051: "婚姻无效情形",
    1062: "夫妻共同财产",
    1063: "夫妻个人财产",
    1064: "夫妻共同债务",
    1076: "协议离婚",
    1079: "诉讼离婚",
    1084: "离婚后的父母子女关系",
    1085: "离婚后的子女抚养费",
    1087: "离婚时夫妻共同财产处理",
    1165: "过错责任原则",
    1179: "人身损害赔偿范围",
}

LAW_META = {
    "law_name": "中华人民共和国民法典",
    "document_number": "中华人民共和国主席令第四十五号",
    "issuing_authority": "全国人民代表大会",
    "promulgation_date": "2020-05-28",
    "effective_date": "2021-01-01",
    "status": "现行有效",
    "jurisdiction": "中华人民共和国大陆地区",
    "source_type": "用户下载的官方法典 PDF",
}


def chinese_number_to_int(value: str) -> int:
    digits = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in digits:
            number = digits[char]
        elif char in units:
            unit = units[char]
            if number == 0:
                number = 1
            section += number * unit
            number = 0
        else:
            raise ValueError(f"无法识别的中文数字：{value}")
    return total + section + number


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", "", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def extract_articles(pdf_path: Path) -> dict[int, dict]:
    reader = PdfReader(pdf_path)
    pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
    page_starts = []
    cursor = 0
    for page in pages:
        page_starts.append(cursor)
        cursor += len(page) + 1
    full_text = "\n".join(pages)
    # 仅把行首的“第X条”视为条文标题，避免误识别正文中的交叉引用。
    marker = re.compile(
        r"^第([零一二三四五六七八九十百千]+)条[\s　]*(?:【([^】]+)】)?",
        re.MULTILINE,
    )
    matches = list(marker.finditer(full_text))
    articles: dict[int, dict] = {}

    for index, match in enumerate(matches):
        number = chinese_number_to_int(match.group(1))
        if number not in SELECTED_ARTICLES:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(full_text)
        content = normalize_text(full_text[match.end():end])
        # PDF 末页在正文后还有版权/下载提示，限制仅影响最后一条的异常尾部。
        content = re.split(r"\n(?:附则|中华人民共和国主席令)", content, maxsplit=1)[0]
        start_page = bisect.bisect_right(page_starts, match.start())
        end_page = bisect.bisect_right(page_starts, max(match.start(), end - 1))
        articles[number] = {
            "chunk_id": f"civil-code-{number}",
            **LAW_META,
            "article_number": number,
            "article_label": f"第{match.group(1)}条",
            "article_title": match.group(2) or SELECTED_ARTICLES[number],
            "topic": SELECTED_ARTICLES[number],
            "content": content,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "retrieval_text": (
                f"《中华人民共和国民法典》第{number}条 "
                f"{match.group(2) or SELECTED_ARTICLES[number]} {content}"
            ),
            "source_file": pdf_path.name,
            "source_pages": list(range(start_page, end_page + 1)),
        }
    return articles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/民法典.pdf"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/civil_code_articles_50.jsonl"),
    )
    args = parser.parse_args()

    articles = extract_articles(args.input)
    missing = sorted(SELECTED_ARTICLES.keys() - articles.keys())
    if missing:
        raise RuntimeError(f"PDF 中未能抽取这些条文：{missing}")
    if any(len(item["content"]) < 10 for item in articles.values()):
        raise RuntimeError("发现异常短的条文，请人工检查 PDF 文本层")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    ordered = [articles[number] for number in SELECTED_ARTICLES]
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for item in ordered:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    manifest_path = args.output.with_name("civil_code_articles_50.manifest.json")
    manifest = {
        **LAW_META,
        "source_file": args.input.name,
        "record_count": len(ordered),
        "chunk_strategy": "一条法条一个 chunk，不跨条合并",
        "selection_strategy": "面向普通用户高频咨询场景的人工分层抽样",
        "article_numbers": list(SELECTED_ARTICLES),
        "output_file": args.output.name,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已写入 {len(ordered)} 条：{args.output}")
    print(f"清单：{manifest_path}")


if __name__ == "__main__":
    main()
