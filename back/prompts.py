"""카드뉴스 생성 프롬프트.

⚠️ 임시 초안이다. 프롬프트를 다듬을 때는 이 파일만 고치면 되고
   controller/cardnews.py 는 건드릴 필요가 없다.
"""

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
