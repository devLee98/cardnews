"""카드뉴스 생성 프롬프트.

⚠️ 임시 초안이다. 프롬프트를 다듬을 때는 이 파일만 고치면 되고
   controller/cardnews.py 는 건드릴 필요가 없다.
"""

import json

from card_spec import CARD_STAGES, MAX_CARDS, MIN_CARDS

PLAN_SYSTEM_PROMPT = f"""\
너는 한국의 공동구매(공구) 카드뉴스를 기획하는 사람이다.
업로드된 공구 데이터에 어떤 정보가 들어 있는지 보고, 만들 수 있는 카드 구성안을 짠다.

지켜야 할 것
- 아래 단계 목록에 있는 단계만 고른다. 새 단계를 만들지 않는다.
- 카드는 최소 {MIN_CARDS}장, 최대 {MAX_CARDS}장이다.
- 핵심 단계는 되도록 넣고, 나머지는 데이터가 받쳐줄 때만 넣는다.
- 필수 데이터가 비어 있는 단계는 넣지 않는다. 그 데이터 없이는 카드를 만들 수 없다.
- 활용 가능 데이터는 비어 있어도 괜찮다.
- 각 단계의 제약을 어기지 않는다.
- 데이터에 없는 사실(가격, 성분, 효능, 인증, 수치)을 만들어 내지 않는다.
- 날짜와 시각은 ISO 형식(2026-06-25T14:59:00+00:00)을 그대로 옮기지 않는다.
  한국 시간으로 바꿔 '6월 25일 23:59' 처럼 읽기 쉽게 쓴다.

응답에 담을 것
- section      : 고른 단계 이름을 그대로 쓴다.
- source_keys  : 그 카드에서 실제로 쓸 경로. 데이터에 값이 있는 것만 고른다.
- description  : 이 카드에 무엇이 담기는지 한 문장으로 쓴다. 60자 이내, 한국어.

                 단계의 일반적인 역할을 옮겨 적지 말고, 데이터 표의 실제 값을 읽고
                 이 공구에서 무엇을 보여줄지 구체적으로 쓴다.
                 상품명, 브랜드명, 큐레이터 이름, 할인율, 리뷰 수처럼 표에 있는 값을 활용한다.

                 (나쁨) 대표 이미지와 공구 기본 정보를 소개
                 (좋음) 차차맘이 소개하는 하루비타 유산균 3종, 정가 대비 최대 45% 할인

                 카드에 들어갈 최종 문구가 아니라, 무엇이 담기는지에 대한 설명이다.
                 브랜드명·제품명을 노출하지 않는 단계에서는 그 이름을 설명에도 쓰지 않는다.
"""


def _render_stages() -> str:
    blocks = []

    for stage in CARD_STAGES:
        lines = [
            f"### {stage['stage']}  ({stage['group']}{', 핵심' if stage['core'] else ''})",
            f"- 목적: {stage['purpose']}",
            f"- 필수 데이터: {', '.join(stage['required']) or '없음 (맥락에 맞게 직접 작성)'}",
            f"- 활용 가능 데이터: {', '.join(stage['optional']) or '없음'}",
        ]

        if stage["constraint"]:
            lines.append(f"- 제약: {stage['constraint']}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def build_plan_prompt(inventory_table: str, missing_paths: list[str]) -> str:
    """구성안 생성용 user 프롬프트."""

    parts = [
        "## 단계 목록",
        _render_stages(),
        "",
        "## 업로드된 데이터에 무엇이 있는지",
        "`채움`은 그 경로가 나오는 자리 중 값이 들어 있는 자리의 수다 (3/15 처럼 읽는다).",
        "`항목수`는 배열인 경우 전체 길이다.",
        "배열은 `[]` 로 합쳐서 한 줄로 보여준다.",
        "",
        "```",
        inventory_table,
        "```",
        "",
        "단계 목록의 데이터 이름과 위 표의 경로는 표기가 같다.",
        "`source_keys` 에는 위 표에 있는 경로를 그대로 쓴다. 경로를 새로 만들지 않는다.",
    ]

    if missing_paths:
        parts += [
            "",
            "## 값이 전부 비어 있는 경로",
            ", ".join(missing_paths),
            "이 경로들은 데이터가 없는 것으로 보고 판단한다.",
        ]

    return "\n".join(parts)


# 구성안 응답 형식 (OpenAI structured outputs).
# section 을 enum 으로 묶어서 명세에 없는 단계가 나오지 않게 한다.
PLAN_RESPONSE_SCHEMA = {
    "name": "card_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["cards"],
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["section", "source_keys", "description"],
                    "properties": {
                        "section": {
                            "type": "string",
                            "enum": [stage["stage"] for stage in CARD_STAGES],
                        },
                        "source_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "description": {"type": "string"},
                    },
                },
            }
        },
    },
}


# ────────────────────────────────────────────────
# 2단계: 확정된 구성안으로 카드마다 들어갈 문구를 쓴다.
# ────────────────────────────────────────────────

MAX_TITLE = 22
MAX_BODY = 60

DRAFT_SYSTEM_PROMPT = f"""\
너는 한국의 공동구매(공구) 카드뉴스 카피라이터다.
확정된 카드 구성안과 실제 공구 데이터를 보고, 카드마다 들어갈 문구를 쓴다.

지켜야 할 것
- 주어진 카드 순서와 단계를 그대로 쓴다. 카드를 늘리거나 줄이거나 순서를 바꾸지 않는다.
- title 은 최대 {MAX_TITLE}자. 한 호흡에 읽히는 짧은 문장이나 구절로 쓴다.
- body 는 최대 {MAX_BODY}자. 한두 문장으로 쓴다.
- 배경 이미지 위에 얹히는 문구다. 길게 설명하지 말고 짧고 굵게 쓴다.
- 데이터에 없는 사실(가격, 성분, 효능, 인증, 수치)을 만들어 내지 않는다.
- 카드마다 주어진 제약을 지킨다.
- 카드끼리 같은 말을 반복하지 않고, 앞뒤가 자연스럽게 이어지게 쓴다.
- 날짜와 시각은 한국 시간으로 바꿔 '6월 25일 23:59' 처럼 읽기 쉽게 쓴다.
- 의약품처럼 들리는 효능 표현이나 '최고', '1위' 같은 검증 불가한 단정은 쓰지 않는다.

문구와 함께 카드 디자인도 정한다
- text_position : 문구를 카드 어디에 둘지. top / center / bottom
                  카드마다 다르게 골라서 넘겨보는 재미가 있게 한다.
                  다만 표지와 CTA 처럼 힘을 줘야 하는 카드는 center 가 잘 어울린다.
- text_align    : left 또는 center. 짧고 강한 문구는 center, 설명이 있으면 left 가 읽기 좋다.
- theme         : dark 는 어두운 배경에 흰 글씨, light 는 밝은 배경에 검은 글씨.
                  상품 사진이 밝고 깨끗하면 light, 분위기가 무거우면 dark 를 고른다.
- highlight     : 카드에서 가장 크게 보여줄 짧은 조각. 숫자나 기한이 잘 어울린다.
                  예) '55%', '9,382건', '6월 25일 23:59'
                  강조할 게 없으면 빈 문자열로 둔다. title 을 그대로 옮겨 적지 않는다.

                  표지 카드는 예외다. highlight 에 event_name 을 그대로 넣는다.
                  공구 이름이 카드에서 가장 크게 보여야 한다.
                  표지의 title 과 body 에는 큐레이터 이름, 상품 수, 할인율, 마감처럼
                  곁들일 정보를 짧게 담는다. 공구 이름을 다시 적지 않는다.
- items         : 목록으로 보여줄 정보. 최대 4개. 필요 없는 카드는 빈 배열로 둔다.
                  label = 항목 이름, value = 가장 중요한 값.
                  가격을 다루는 카드라면 구성마다 한 줄씩 넣는다.
                    label    = option1 (예: '주방세제 본품 3개')
                    value    = base_sale_price, 즉 공구가 (예: '22,900원')
                    original = consumer_price, 즉 정가 (예: '45,000원')
                    discount = discount_rate_derived (예: '49%')
                  범위로 뭉뚱그리지 말고 구성별로 정확한 숫자를 쓴다.
                  가격이 아닌 항목이면 original 과 discount 는 빈 문자열로 둔다.
                  숫자는 데이터에 있는 값을 그대로 쓰고 천 단위에 쉼표를 넣는다.
- image_index   : 이 카드를 만들 때 참고할 상세 이미지를 고른다.
                  아래 '쓸 수 있는 상세 이미지' 표의 번호를 적으면 그 사진의 장면과
                  구도를 따라간 카드가 만들어진다. 참고할 게 없으면 -1 을 적는다.
                  그 사진을 그대로 쓰는 것이 아니라, 그 장면 위에 문구까지 함께 그려진다.

                  브랜드가 직접 찍은 사진이라 AI 가 지어낸 그림보다 믿음이 간다.
                  쓸 수 있는 자리가 있으면 아끼지 말고 쓴다.
                  후기 모음, 사용 장면, 성분·인증 안내가 특히 잘 맞는다.

                  카드마다 서로 다른 이미지를 고른다. 같은 번호를 두 번 적지 않는다.
                  되도록 여러 제품군에 걸쳐 고루 고른다.
                  비슷해 보이는 두 장 중에서는 아직 고르지 않은 쪽을 고른다.
"""


# 이름만 보고는 뜻을 오해하기 쉬운 값들. 특히 가격이 세 종류라 섞이면 사실이 틀어진다.
FIELD_GLOSSARY = """\
- consumer_price          : 정가. 할인 전 소비자가.
- base_sale_price         : 이번 공구에서 파는 가격. 가격을 하나만 보여준다면 반드시 이 값을 쓴다.
- lowest_price            : 다른 채널의 최저가. 공구가보다 비쌀 수 있으니 공구가 대신 쓰지 않는다.
- discount_rate_derived   : 정가 대비 할인율(%).
- option1                 : 판매 구성 이름. 예) '주방세제 본품 3개'
                            가격 목록의 label 로는 이 값이 상품명보다 정확하다.
- naver_rating            : 네이버 스토어 평점.
- naver_review_count      : 네이버 리뷰 개수. 자체 reviews 배열 길이와 다르다.
- reservation.add_count   : 공구 알림을 신청한 사람 수.
- curator.follower_count  : 큐레이터의 팔로워 수. 알림 신청 수와 헷갈리지 않는다."""


def build_draft_prompt(
    cards: list[dict],
    values: dict,
    instruction: str | None = None,
    assets: list[dict] | None = None,
) -> str:
    """카드 문구 생성용 user 프롬프트."""

    constraints = {stage["stage"]: stage["constraint"] for stage in CARD_STAGES}
    purposes = {stage["stage"]: stage["purpose"] for stage in CARD_STAGES}

    lines = ["## 카드 구성안 (이 순서, 이 단계 그대로)"]

    for index, card in enumerate(cards, 1):
        section = card["section"]
        lines.append(f"{index}. {section} — {card.get('description', '')}")
        lines.append(f"   역할: {purposes.get(section, '')}")

        if constraints.get(section):
            lines.append(f"   제약: {constraints[section]}")

    parts = [
        "\n".join(lines),
        "",
        "## 값의 의미 (헷갈리기 쉬운 것만)",
        FIELD_GLOSSARY,
        "",
        "## 카드에 쓸 실제 데이터",
        "```json",
        json.dumps(values, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 쓸 수 있는 상세 이미지 (image_index 로 고른다)",
        render_asset_catalog(assets or []),
    ]

    if instruction and instruction.strip():
        parts += [
            "",
            "## 관리자 추가 지시 (최우선으로 반영)",
            instruction.strip(),
        ]

    return "\n".join(parts)


DRAFT_RESPONSE_SCHEMA = {
    "name": "card_draft",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["cards"],
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "section",
                        "title",
                        "body",
                        "highlight",
                        "text_position",
                        "text_align",
                        "theme",
                        "items",
                        "image_index",
                    ],
                    "properties": {
                        "section": {
                            "type": "string",
                            "enum": [stage["stage"] for stage in CARD_STAGES],
                        },
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "highlight": {"type": "string"},
                        "text_position": {
                            "type": "string",
                            "enum": ["top", "center", "bottom"],
                        },
                        "text_align": {
                            "type": "string",
                            "enum": ["left", "center"],
                        },
                        "theme": {"type": "string", "enum": ["dark", "light"]},
                        # -1 이면 배경을 새로 만든다
                        "image_index": {"type": "integer"},
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": [
                                    "label",
                                    "value",
                                    "original",
                                    "discount",
                                ],
                                "properties": {
                                    "label": {"type": "string"},
                                    "value": {"type": "string"},
                                    # 가격 항목일 때만 채운다
                                    "original": {"type": "string"},
                                    "discount": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        },
    },
}


# ────────────────────────────────────────────────
# 3단계: 카드마다 배경 이미지를 만든다.
# 문구는 이미지 위에 따로 얹으므로, 이미지에는 글자가 들어가면 안 된다.
# ────────────────────────────────────────────────

IMAGE_SIZE = "1024x1280"  # 4:5 세로형


# 문구가 올라갈 자리는 비워 둬야 한다. 어느 쪽을 비울지는 AI 가 정한 배치를 따른다.
# 카드마다 같은 지시만 주면 결과가 한 가지 그림으로 수렴한다.
# 단계별로 화각과 소재를 다르게 못박아 서로 다른 장면이 나오게 한다.
SCENE_DIRECTION = {
    "표지": "제품을 여러 개 모아 놓고 한발 물러나서 담은 넓은 장면.",
    "문제 제기": (
        "이 제품을 쓰기 직전의 상황을 담는다. 제품이 쓰이는 바로 그 자리에서, "
        "아직 해결되지 않은 상태를 보여준다."
    ),
    "해결의 실마리": "제품이 화면 한쪽에 조용히 놓여 있고 빛이 들어오는 정돈된 장면.",
    "문제 분석": "제품과 그 제품이 다루는 대상을 가까이 당겨 담은 클로즈업. 질감 위주로.",
    "해결(제품)": "제품 하나를 정면에서 또렷하게 담은 스튜디오 컷. 배경은 단색에 가깝게.",
    "근거": "제품이 실제로 쓰이고 있는 순간. 손이나 물의 움직임이 함께 담긴 장면.",
    "인플 코멘트": "제품이 누군가의 집 선반이나 세면대에 놓인 편안한 스냅.",
    "가격 & 스펙": "제품 여러 개가 나란히 줄지어 놓인 장면. 배경은 최대한 단순하게.",
    "홍보/전파": "제품이 여러 개 모여 있거나 포장된 상태. 나눔이나 선물 느낌으로.",
    "CTA": "제품을 가까이 당겨 담고 한쪽을 크게 비운 구도. 마무리다운 차분함으로.",
}

TEXT_AREA_GUIDE = {
    "top": "위쪽 절반",
    "center": "가운데 가로 띠 영역",
    "bottom": "아래쪽 절반",
}


def build_image_prompt(
    *,
    section: str,
    title: str,
    body: str,
    highlight: str = "",
    items: list[dict] | None = None,
    has_reference: bool,
    text_position: str = "bottom",
    text_align: str = "left",
    theme: str = "dark",
) -> str:
    """카드 한 장을 통째로 만드는 프롬프트.

    문구를 나중에 HTML 로 얹지 않고 이미지 안에 함께 그린다.
    따로 얹으면 배경과 글자가 각자 놀아서 완성된 카드처럼 보이지 않는다.
    """

    stage = next((s for s in CARD_STAGES if s["stage"] == section), None)
    rows = items or []

    # ── 무엇을 그릴지 ──
    reference_note = (
        "첨부한 사진들은 이 브랜드의 실제 제품컷이다. "
        "첫 번째 사진의 장면과 구도를 기준으로 삼는다. "
        "제품의 생김새, 색, 라벨 디자인을 그대로 살린다. "
        "다만 사진 안에 인쇄되어 있던 글자와 말풍선은 지우고, "
        "아래에 적어 준 문구만 새로 그려 넣는다."
    )

    if has_reference and len(rows) >= 2:
        subject = f"{reference_note} 제품 여러 개가 나란히 놓인 장면으로 만든다."
    elif has_reference:
        subject = f"{reference_note} 첫 번째 사진의 제품을 주인공으로 삼는다."
    else:
        subject = (
            "브랜드를 알아볼 수 있는 로고나 라벨은 그리지 않는다. "
            "다만 이 제품이 쓰이는 상황에서 벗어나지 않는다. "
            "제품과 무관한 소품으로 화면을 채우지 않는다."
        )

    # ── 어떤 글자를 그릴지 ──
    # 예전에는 '[제목] …' 처럼 라벨을 붙였더니 라벨까지 그림에 그려졌다.
    # 그릴 글자는 따옴표 안에만 두고, 설명은 따옴표 밖에 둔다.
    text_lines = [
        "카드에 그려 넣을 문구는 아래 큰따옴표 안의 글자뿐이다.",
        "큰따옴표와 그 바깥의 설명은 그리지 않는다.",
        "",
    ]

    if highlight:
        text_lines.append(f'가장 크게 그릴 문구 → "{highlight}"')
    if title:
        text_lines.append(f'그보다 작게 그릴 문구 → "{title}"')
    if body:
        text_lines.append(f'가장 작게 그릴 문구 → "{body}"')

    if rows:
        text_lines.append("")
        text_lines.append("아래 값들을 표 형태로 가지런히 정렬해서 그린다.")
        text_lines.append("각 줄은 구성 이름, 정가, 할인율, 공구가 순서다.")

        for row in rows:
            cells = [row.get("label", "")]
            if row.get("original"):
                cells.append(f"{row['original']}(취소선)")
            if row.get("discount"):
                cells.append(row["discount"])
            cells.append(row.get("value", ""))
            joined = " | ".join(cell for cell in cells if cell)
            text_lines.append(f'  "{joined}"')

    place = {
        "top": "문구는 카드 위쪽에 모아서 배치하고 아래쪽은 사진이 보이게 둔다.",
        "center": "문구는 카드 한가운데에 모아서 배치한다.",
        "bottom": "문구는 카드 아래쪽에 모아서 배치하고 위쪽은 사진이 보이게 둔다.",
    }.get(text_position, "문구는 카드 아래쪽에 모아서 배치한다.")

    align = "가운데 정렬" if text_align == "center" else "왼쪽 정렬"

    if theme == "light":
        tone = (
            "배경은 밝게 만들고 글자는 진한 먹색으로 그린다. "
            "글자가 놓이는 자리는 배경을 더 밝고 단순하게 정리해 대비를 준다."
        )
    else:
        tone = (
            "글자는 흰색으로 그린다. "
            "글자가 놓이는 자리에는 어두운 반투명 면이나 그림자를 깔아 또렷하게 읽히게 한다."
        )

    lines = [
        "한국 이커머스 공동구매 카드뉴스 한 장을 완성된 상태로 만든다. 세로 4:5.",
        "사진 위에 문구가 얹힌 상업용 카드뉴스다. 배경만 있는 이미지가 아니다.",
        "실제 촬영한 사진처럼 자연광과 깊이감이 있게 만든다. 일러스트나 3D 렌더링이 아니다.",
        f"이 카드의 장면 방향: {SCENE_DIRECTION.get(section, '상황에 맞는 장면을 고른다.')}",
        "",
        subject,
        "",
        f"이 카드의 역할: {section}",
    ]

    if stage:
        lines.append(f"카드가 전달할 내용: {stage['purpose']}")

    lines += ["", *text_lines, "", "글자를 그릴 때 반드시 지킬 것:"]
    lines += [
        "- 큰따옴표 안의 글자를 한 글자도 바꾸지 않고 그대로 그린다.",
        "  글자를 새로 지어내거나, 영어로 바꾸거나, 줄이지 않는다.",
        "- 큰따옴표, 대괄호, 화살표, '가장 크게' 같은 설명 문구는 그리지 않는다.",
        "- 적어 주지 않은 글자는 그리지 않는다. 제품 라벨에 원래 있는 글자는 그대로 둔다.",
        "- 한글 자모가 깨지지 않게 또렷한 고딕체로 그린다.",
        "- 숫자는 적어 준 그대로 그린다. 쉼표 위치도 바꾸지 않는다.",
        f"- {place}",
        f"- 문구는 {align}으로 배치한다.",
        f"- {tone}",
        "- 글자가 사진의 중요한 부분을 가리지 않게 한다.",
        "- 모든 글자는 카드 가장자리에서 넉넉히 안쪽에 둔다.",
        "  글자의 위아래나 좌우가 화면 밖으로 잘려 나가면 안 된다.",
        "  특히 첫 줄 위와 마지막 줄 아래에 여백을 확실히 남긴다.",
    ]

    lines += [
        "",
        "그 밖에:",
        "- 사람 얼굴은 넣지 않는다. 손이나 실루엣 정도만 허용한다.",
        "- 아기나 아이의 맨살, 기저귀 차림이 드러나는 장면은 만들지 않는다.",
        "  사람 대신 제품과 주변 사물로 장면을 채운다.",
        "- 콜라주나 분할 화면이 아닌, 하나의 장면으로 구성한다.",
        "- 제품은 위아래가 잘리지 않게 전체가 화면 안에 들어오도록 담는다.",
        "- 워터마크나 로고를 새로 만들어 넣지 않는다.",
        "- 제품과 상관없는 소품(수건, 화분, 바구니 같은 것)으로 화면을 채우지 않는다.",
        "  소품을 넣더라도 이 제품을 실제로 쓸 때 곁에 있을 물건만 넣는다.",
    ]

    if stage and stage["constraint"]:
        lines.append(f"- {stage['constraint']}")

    return "\n".join(lines)


# ────────────────────────────────────────────────
# 상세 이미지 살펴보기
# URL 만 봐서는 연출컷인지 글자투성이 배너인지 알 수 없어서 비전 모델에게 물어본다.
# ────────────────────────────────────────────────

ASSET_SYSTEM_PROMPT = f"""\
너는 공동구매 카드뉴스를 만들려고 브랜드 상세페이지 이미지를 훑어보는 사람이다.
각 이미지에 무엇이 찍혀 있는지 보고, 카드 배경으로 쓸 수 있는지 판단한다.

이미지마다 답할 것
- scene        : 무엇이 찍혀 있는지 한 줄로. 40자 이내.
                 예) '흰 세면대 위에 놓인 펌프형 세제와 수건'
- text_amount  : 이미지 안에 인쇄된 글자의 양.
                 none  글자가 없거나 제품 라벨 정도
                 some  제목이나 짧은 문구가 있다
                 heavy 설명 문장이 화면을 채운다
- usable       : 카드 한 장으로 쓸 만한지.
                 글자가 많아도 그 자체로 메시지가 되는 이미지는 쓸 수 있다고 본다.
                 예) 후기 모음, 사용 전후 비교, 인증 배지 모음
                 아래만 쓸 수 없다고 본다.
                 - 성분표나 배송 안내처럼 작은 글씨를 읽어야만 뜻이 통하는 것
                 - 세로로 아주 길어 잘라내면 내용이 남지 않는 것
                 - 화질이 뭉개졌거나 여백만 있는 것
- suggest      : 어느 단계 카드에 어울리는지 하나 고른다. 마땅치 않으면 '없음'.
                 고를 수 있는 단계: {", ".join(stage["stage"] for stage in CARD_STAGES)}
"""

ASSET_RESPONSE_SCHEMA = {
    "name": "asset_catalog",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["images"],
        "properties": {
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["index", "scene", "text_amount", "usable", "suggest"],
                    "properties": {
                        "index": {"type": "integer"},
                        "scene": {"type": "string"},
                        "text_amount": {
                            "type": "string",
                            "enum": ["none", "some", "heavy"],
                        },
                        "usable": {"type": "boolean"},
                        "suggest": {
                            "type": "string",
                            "enum": [stage["stage"] for stage in CARD_STAGES] + ["없음"],
                        },
                    },
                },
            }
        },
    },
}


def render_asset_catalog(assets: list[dict]) -> str:
    """문구 생성 프롬프트에 넣을 이미지 카탈로그."""

    if not assets:
        return "쓸 만한 상세 이미지가 없다. 모든 카드를 새로 만든다."

    lines = ["번호 | 장면 | 글자 | 어울리는 단계 | 종류"]

    for asset in assets:
        kind = "움직임" if asset.get("animated") else "정지"
        lines.append(
            f"{asset['index']} | {asset['scene']} | {asset['text_amount']}"
            f" | {asset['suggest']} | {kind}"
        )

    lines.append("")
    lines.append(
        "종류가 '움직임'인 것을 고르면 그 움직이는 이미지가 카드에 그대로 들어가고, "
        "문구는 이미지 아래에 따로 붙는다. 그래서 다른 카드와 결이 조금 달라진다."
    )
    lines.append(
        "움직임이 있어야 뜻이 통하는 카드에만 쓴다. 많아야 두 장이고, 없어도 된다."
    )
    lines.append(
        "첫 장과 마지막 장에는 움직이는 것을 고르지 않는다. "
        "공구 이름과 마감 시각이 글자로 크게 들어가야 하는 자리다."
    )

    return "\n".join(lines)
