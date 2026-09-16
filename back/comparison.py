"""비교표 데이터에서 카드뉴스에 쓸 수 있는 행만 남긴다.

업로드 JSON 에 `comparison_status` / `comparison_info` / `comparison_rows[]` 가
붙으면서 상품마다 경쟁사 비교표가 함께 들어온다.
이 표는 카드뉴스용이 아니라 내부 분석용이라 그대로 프롬프트에 넣으면 세 가지가 망가진다.

  1. 경쟁사 브랜드명·제품명이 그대로 노출된다.
     `values` 와 `product_notes` 는 경쟁사 제품명을 Key 로 쓴다.
     inventory 가 Key 를 경로로 세기 때문에 표에도, 뽑아 낸 값에도 그대로 실린다.
  2. 가격이 섞인다. 비교표 가격은 단품 기준이고 공구는 묶음이라 값이 다르다.
  3. 경로 수가 249개 늘어난다. inventory 의 상한(200)에 걸려
     정작 카드에 필요한 경로(가격·리뷰·제품명)가 잘려 나간다.

그래서 걸러 내는 일을 AI 에게 맡기지 않고 여기서 먼저 끝낸다.
inventory 는 이 필드들을 아예 건너뛰고(`inventory.COMPARISON_KEYS`),
프롬프트에는 이 파일이 만든 표만 넘어간다.

경쟁사 값은 A급 행에 한해 이름을 떼고 값만 나란히 싣는다.
우리 값만 보여주면 AI 가 '용량 500ml' 를 장점처럼 쓰는데, 타사가 1,000ml·2,000ml 인
표였다. 앞서는 항목인지 뒤지는 항목인지는 타사 값을 봐야 알 수 있다.
홍보/전파 카드가 '타사보다 나은 점'을 모으는 자리라 이 판단이 꼭 필요하다.
경쟁사 브랜드명과 제품명은 여전히 표 밖으로 나가지 않는다.

고정 행 가운데 '총평'은 우리 제품 열만 살린다. 분석자가 우리 제품의 강점을 세 줄로
요약한 것이라 홍보/전파 카드의 뼈대로 가장 알맞다. 가격·최상급·경쟁사 열 번호가 든
줄은 다른 설명문과 같은 기준으로 버린다.

필터 기준은 `docs/02-prompts.md` 의 '비교표 데이터' 절과 짝을 이룬다.
"""

import re
from typing import Any

#: 비교표를 쓸 수 있는 상태. 그 밖의 값은 연결된 완료 비교 이력이 없다는 뜻이다.
AVAILABLE = "available"

#: 우리 제품 값이 이것이면 채택하지 않는다. 값이 없다는 뜻이라 소재가 되지 못한다.
EMPTY_VALUES = {"정보 없음", "정보없음", "미확인", "확인 불가", "확인불가", "미기재", "-"}

#: 이것으로 시작하면 우리 제품에 '없는' 속성이다. 장점 소재가 아니다.
#: 예) '세스코 멤버쉽 가입 여부: 없음', 'VOCs 테스트 완료 여부: 없음'
ABSENT_PREFIXES = ("없음", "불가", "미지원", "미제공", "미적용", "해당 없음", "해당없음")

#: 고정 행이 아닌데도 가격·리뷰·판매량이 담긴 행이 있다.
#: 가격은 단품 기준이라 공구가와 어긋나고, 리뷰·평점은 naver_review_count 와
#: 스냅샷 시점이 달라 카드마다 다른 숫자가 나온다. 항목 이름으로 한 번 더 걸러 낸다.
#: (예: 가성비 분류의 '개당 단가', '배송비', 'ml당 가격')
NUMERIC_TRAPS = re.compile(
    r"가격|단가|할인|정가|원가|배송비|리뷰|평점|별점|후기|판매량|매출|순위"
)

#: 통째로 버리는 분류. '인기도'는 리뷰 수·평점·누적 판매량만 담고 있어
#: NUMERIC_TRAPS 와 같은 이유로 쓸 수 없다. 1주차 파일에는 없던 분류다.
BANNED_CATEGORIES = {"인기도"}

#: 값 자체가 회사 이름인 행. 타사 값을 실으면 경쟁사 이름이 그대로 나간다.
#: (예: '제조사: 러베 파트너사', '브랜드 공식 여부: 있음 (○○ 공식스토어)')
#: 우리 값은 사실로 쓸 수 있으니 행은 남기되 B급으로 내려 타사 값을 싣지 않는다.
NAME_ROWS = re.compile(r"제조사|제조원|브랜드|판매자|판매업|회사|업체|유통사")

#: 타사 값에서 경쟁사 브랜드명을 지울 때 넣는 말.
MASK = "타사"

#: 분류별 슬라이드 성격. 프롬프트에 그대로 실어 어떤 카드에 얹을지 알려준다.
CATEGORY_ROLES = {
    "안전성": "인증·성분·무첨가",
    "성능": "사용 범위·효과",
    "가성비": "용량·농축도·사용량",
    "편의성": "패키지·보관·크기",
}

#: description·product_notes 에 이 단어가 있으면 원문을 쓰지 않는다.
#: 근거 없는 최상급이 카피로 그대로 흘러 들어가는 통로다.
SUPERLATIVES = ("가장", "유일", "최우수", "최고", "최저", "최다", "최초", "1위", "압도")

#: description 의 P1~P5 는 경쟁사 열 번호다. 이 표기가 있으면 원문을 쓰지 않는다.
COLUMN_MARKER = re.compile(r"\bP[1-5]\b")

#: 총평 줄에 금액이 적혀 있으면 그 줄을 쓰지 않는다. ('ml당 12원' 같은 단품 기준 값)
#: 항목 이름을 거르는 NUMERIC_TRAPS 로는 문장 속 금액이 안 걸린다.
PRICE_MARKER = re.compile(r"\d\s*원")

#: 총평은 '1. …\n2. …\n3. …' 꼴이다. 번호를 떼고 줄 단위로 읽는다.
SUMMARY_NUMBER = re.compile(r"^\s*\d+\s*[.)]\s*")

#: tier 우선순위. 낮을수록 먼저 고른다.
TIER_ORDER = {"recommended": 0, "candidate": 1}

MAX_VALUE_LENGTH = 60
MAX_NOTE_LENGTH = 80
MAX_SUMMARY_LENGTH = 100

#: 타사 값 하나의 길이. 여러 개가 한 칸에 나란히 실리므로 우리 값보다 짧게 자른다.
#: 앞서는지 뒤지는지만 알면 되는 값이라 뒤가 잘려도 뜻이 남는다.
MAX_RIVAL_LENGTH = 30

#: 상품 하나가 차지할 수 있는 행 수. 한 슬라이드에 3~4개를 넘기지 않지만,
#: 홍보/전파 카드가 '앞서는 항목'만 골라 모으므로 그보다 넉넉히 주고 고르게 한다.
MAX_ROWS_PER_PRODUCT = 8

#: 총평에서 살릴 줄 수. 원문이 세 줄이라 그 이상은 나오지 않는다.
MAX_SUMMARY_LINES = 3

#: 프롬프트에 실을 상품 수. 공구 하나에 상품이 수십 개라 전부 실으면 프롬프트가 넘친다.
MAX_PRODUCTS = 8


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "예" if value else "아니오"
    return " ".join(str(value).split())


def _clean(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[:limit]}…"


def _usable_prose(value: Any, me: str) -> str:
    """description·product_notes 원문 중 카피 소재로 쓸 수 있는 것만 돌려준다.

    객체형이면 우리 제품 열의 값만 본다. 경쟁사 열은 읽지 않는다.
    최상급 단어나 P1~P5 표기가 섞여 있으면 통째로 버린다.
    일부만 지우면 남은 문장이 원래 뜻과 달라져서, 고치는 쪽이 더 위험하다.

    길이는 자르지 않고 돌려준다. 부르는 쪽에서 값과 겹치는지 본 다음 자른다.
    """

    if isinstance(value, dict):
        value = value.get(me)

    text = _text(value)

    if not text:
        return ""
    if any(word in text for word in SUPERLATIVES):
        return ""
    if COLUMN_MARKER.search(text):
        return ""

    return text


def _is_absent(value: str) -> bool:
    return value in EMPTY_VALUES or value.startswith(ABSENT_PREFIXES)


def _grade(row: dict, me: str, rivals: list[str]) -> str:
    """경쟁 열이 전부 확인된 행만 A급이다.

    B급은 '경쟁사에 그 기능이 없다'가 아니라 '확인되지 않았다'는 뜻이라
    비교·순위 표현을 붙일 수 없다.
    """

    if not rivals:
        return "B"

    confidences = row.get("value_confidences") or {}
    values = row.get("values") or {}

    for rival in rivals:
        if confidences.get(rival) != "high":
            return "B"
        if _is_absent(_text(values.get(rival))):
            return "B"

    return "A"


def _rival_brands(product: dict, rivals: list[str]) -> list[str]:
    """타사 값 안에서 지워야 할 경쟁사 이름들.

    고정 행 '브랜드'의 경쟁 열 값과, 경쟁 제품명의 첫 단어를 모은다.
    ('러베 비건 젖병 세정제 …' 의 '러베') 값 문장 안에 브랜드가 섞여 나오는 일이 있어서다.
    한 글자짜리는 엉뚱한 글자까지 지우므로 빼고, 긴 이름부터 지운다.
    """

    brands: set[str] = set()

    for rival in rivals:
        first = rival.split(" ", 1)[0]
        if len(first) >= 2:
            brands.add(first)

    for row in product.get("comparison_rows") or []:
        if not row.get("is_fixed") or _text(row.get("item_name")) != "브랜드":
            continue

        for rival in rivals:
            for word in _text((row.get("values") or {}).get(rival)).split():
                if len(word) >= 2:
                    brands.add(word)

    return sorted(brands, key=len, reverse=True)


def _rival_values(row: dict, rivals: list[str], brands: list[str]) -> str:
    """A급 행의 타사 값을 이름 없이 한 줄로 잇는다.

    이름을 떼고 값만 넘겨야 AI 가 우리 값이 앞서는지 볼 수 있다.
    값 안에 경쟁사 이름이 섞여 있으면 그 자리만 '타사'로 바꾼다.
    B급 행은 비교 표현 자체를 못 쓰므로 부르는 쪽에서 빈 문자열로 둔다.
    """

    values = row.get("values") or {}
    cells = []

    for rival in rivals:
        value = _text(values.get(rival))

        for brand in brands:
            value = value.replace(brand, MASK)

        cells.append(_clean(value, MAX_RIVAL_LENGTH))

    return " / ".join(cells)


def _summary_lines(product: dict, me: str) -> list[str]:
    """고정 행 '총평'에서 우리 제품 줄만 골라 낸다.

    분석자가 우리 제품의 강점을 세 줄로 요약한 것이다. 경쟁사 열은 읽지 않는다.
    줄마다 설명문과 같은 기준(최상급·P번호)으로 거르고, 금액이 적힌 줄도 버린다.
    비교표 금액은 단품 기준이라 공구가와 어긋난다.
    """

    for row in product.get("comparison_rows") or []:
        if not row.get("is_fixed") or _text(row.get("item_name")) != "총평":
            continue

        raw = (row.get("values") or {}).get(me)
        lines = []

        for line in str(raw or "").splitlines():
            line = _usable_prose(SUMMARY_NUMBER.sub("", line), me)

            if not line or PRICE_MARKER.search(line):
                continue

            lines.append(_clean(line, MAX_SUMMARY_LENGTH))

        return lines[:MAX_SUMMARY_LINES]

    return []


def _pick_rows(product: dict, me: str, rivals: list[str]) -> list[dict]:
    """채택 필터를 통과한 행만 등급을 붙여 돌려준다."""

    picked = []
    brands = _rival_brands(product, rivals)

    for row in product.get("comparison_rows") or []:
        # 고정 행 7개(사진·제품명·브랜드·가격·리뷰 수·평점·총평)는 여기서 다루지 않는다.
        # 경쟁사 정보가 담겨 있고, 가격은 단품 기준이라 공구가와 다르다.
        # 총평만 _summary_lines 가 따로 읽는다.
        if row.get("is_fixed"):
            continue

        category = _text(row.get("weight_category"))

        if category in BANNED_CATEGORIES:
            continue

        item_name = _text(row.get("item_name"))

        if not item_name or NUMERIC_TRAPS.search(item_name):
            continue

        confidences = row.get("value_confidences") or {}

        # medium·none 은 출처를 찾지 못한 값이다. 전부 버린다.
        if confidences.get(me) != "high":
            continue

        value = _text((row.get("values") or {}).get(me))

        if _is_absent(value):
            continue

        # 통과한 행의 것만 읽는다. 버린 행의 note 는 신뢰도 게이트를 거치지 않았다.
        note = _usable_prose(row.get("product_notes"), me) or _usable_prose(
            row.get("description"), me
        )

        # note 가 값을 그대로 옮겨 적은 것이면 붙이지 않는다. 표만 길어지고 알려 주는 게 없다.
        if note and (note in value or value in note):
            note = ""

        # 회사 이름이 값인 행은 타사 값을 실을 수 없으니 B급으로 내린다.
        grade = "B" if NAME_ROWS.search(item_name) else _grade(row, me, rivals)

        picked.append(
            {
                "item_name": item_name,
                "value": _clean(value, MAX_VALUE_LENGTH),
                "category": category or "기타",
                "grade": grade,
                "tier": _text(row.get("tier")),
                "note": _clean(note, MAX_NOTE_LENGTH),
                # 타사 값은 A급에만 싣는다. B급은 비교 표현을 못 쓰니 볼 이유가 없다.
                "rivals": _rival_values(row, rivals, brands) if grade == "A" else "",
            }
        )

    # A급과 recommended 를 앞으로 보낸다. 잘려 나가는 쪽이 덜 아쉬운 순서다.
    picked.sort(key=lambda row: (row["grade"], TIER_ORDER.get(row["tier"], 2)))

    return picked[:MAX_ROWS_PER_PRODUCT]


def _ranking_banned(names: list[str], brand: str) -> bool:
    """순위·최상급 표현을 아예 막아야 하는 표인지.

    자사 다른 옵션이 경쟁 열로 들어간 표에서 '1위'라고 말하면 자기 제품끼리 겨룬 것이 된다.
    비교 열이 하나도 없는 표도 마찬가지다. 겨룬 상대가 없으면 순위가 성립하지 않는다.
    """

    if len(names) < 2:
        return True

    return bool(brand) and sum(1 for name in names if brand in name) >= 2


def _label(product: dict) -> str:
    """어느 상품의 표인지 알아볼 이름.

    option1 하나로는 모자란다. 'ORANGE', '엠버', '아이보리 / 베이지 / 그레이' 처럼
    색이나 캐릭터만 적힌 구성이 있어서, 그것만 보면 무슨 제품인지 알 수 없다.
    반대로 option1 이 제품명을 이미 품고 있으면('주방세제 본품 3개') 앞에 또 붙일 필요가 없다.
    """

    name = _text(product.get("name"))
    option = _text(product.get("option1"))

    if not option:
        return name or "이름 없는 상품"
    if not name or name in option:
        return option

    return f"{name} · {option}"


def _review_conflict(product: dict, me: str) -> str | None:
    """비교표의 '리뷰 수' 고정 행과 naver_review_count 가 어긋나는지.

    스냅샷 시점이 달라 생기는 차이다. 값은 언제나 naver_review_count 를 쓰고
    차이는 알리기만 한다.
    """

    counted = product.get("naver_review_count")

    if not isinstance(counted, int):
        return None

    for row in product.get("comparison_rows") or []:
        if not row.get("is_fixed") or _text(row.get("item_name")) != "리뷰 수":
            continue

        raw = _text((row.get("values") or {}).get(me))
        digits = re.sub(r"[^0-9]", "", raw)

        if digits and int(digits) != counted:
            return f"{_label(product)} — 비교표 {raw} / naver_review_count {counted:,}"

    return None


def build_comparison(data: Any) -> dict[str, Any]:
    """업로드 데이터에서 비교표 부분만 걸러 낸 결과를 만든다.

    돌려주는 것
      products  : 채택된 행이 남은 상품들
      review    : 비교 대상이 어긋나 쓸 수 없는 상품 이름들
      conflicts : 기존 값과 어긋나는 것으로 확인된 항목
    """

    products: list[dict[str, Any]] = []
    review: list[str] = []
    conflicts: list[str] = []

    events = data.get("events") if isinstance(data, dict) else None

    for event in events or []:
        if not isinstance(event, dict):
            continue

        brand = _text((event.get("brand") or {}).get("name"))

        for product in event.get("products") or []:
            if not isinstance(product, dict):
                continue
            if product.get("comparison_status") != AVAILABLE:
                continue

            info = product.get("comparison_info") or {}
            me = _text(info.get("product_name"))

            if not me:
                continue

            # 비교 대상이 어긋난 표다. 성인용과 유아용이 한 표에 섞인 것들이라
            # 행 단위로 걸러 낼 수가 없다. 표 전체를 쓰지 않는다.
            if info.get("review_required"):
                review.append(_label(product))
                continue

            conflict = _review_conflict(product, me)

            if conflict:
                conflicts.append(conflict)

            names = [_text(name) for name in info.get("product_names") or []]
            rivals = [name for name in names if name and name != me]
            rows = _pick_rows(product, me, rivals)

            if not rows:
                continue

            products.append(
                {
                    "label": _label(product),
                    "rows": rows,
                    "summary": _summary_lines(product, me),
                    "ranking_banned": _ranking_banned(names, brand),
                }
            )

    merged = _merge_same_rows(products)

    # 쓸 수 있는 행이 많은 상품을 앞에 둔다. 잘려도 덜 아쉽다.
    merged.sort(key=lambda item: -len(item["rows"]))

    return {
        "products": merged[:MAX_PRODUCTS],
        "review": review,
        "conflicts": _merge_same_gap(conflicts),
    }


def _merge_same_rows(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """채택된 행이 똑같은 상품끼리 한 덩어리로 합친다.

    한 상품의 구성이 여러 개면(본품 3개 / 1개+리필 3개 / 2개+리필 6개) 비교표가 같다.
    그대로 두면 같은 표가 서너 번 실려 자리를 차지하고, 카드마다 같은 말을 하게 된다.
    """

    groups: dict[tuple, dict[str, Any]] = {}

    for product in products:
        signature = (
            product["ranking_banned"],
            tuple(tuple(sorted(row.items())) for row in product["rows"]),
            tuple(product["summary"]),
        )
        group = groups.get(signature)

        if group is None:
            groups[signature] = {
                "rows": product["rows"],
                "summary": product["summary"],
                "ranking_banned": product["ranking_banned"],
                "labels": [product["label"]],
            }
        else:
            group["labels"].append(product["label"])

    return list(groups.values())


def _merge_same_gap(conflicts: list[str]) -> list[str]:
    """어긋난 폭이 같은 항목은 한 줄로 줄인다. 구성만 다르고 내용은 같은 것들이다."""

    merged: dict[str, list[str]] = {}

    for conflict in conflicts:
        label, _, gap = conflict.partition(" — ")
        merged.setdefault(gap, []).append(label)

    return [
        f"{labels[0]} 외 {len(labels) - 1}건 — {gap}"
        if len(labels) > 1
        else f"{labels[0]} — {gap}"
        for gap, labels in merged.items()
    ]


#: 구성안 단계에 알려 줄 A급 항목 이름 수. 설명(description)을 구체적으로 쓰라고 주는
#: 것이라 몇 개면 충분하다. 값은 문구 단계에서 본다.
MAX_SUMMARY_ITEMS = 10


def summarize_comparison(result: dict[str, Any]) -> str:
    """구성안 단계에 넣을 한 문단. 어떤 소재가 몇 개 있는지 알려준다.

    A급 항목은 이름까지 적는다. 홍보/전파 카드의 설명을
    '비교표로 확인된 강점을 모아' 같은 일반론이 아니라 실제 항목으로 쓰게 하려는 것이다.
    """

    counts: dict[str, int] = {}
    a_items: list[str] = []
    summary_lines = 0

    for product in result["products"]:
        summary_lines += len(product["summary"])

        for row in product["rows"]:
            counts[row["category"]] = counts.get(row["category"], 0) + 1

            if row["grade"] == "A" and row["item_name"] not in a_items:
                a_items.append(row["item_name"])

    if not counts:
        return ""

    listed = ", ".join(
        f"{category} {count}개" for category, count in sorted(counts.items())
    )

    lines = [
        f"상품 {len(result['products'])}종에서 검증된 비교표 항목 {sum(counts.values())}개를"
        f" 쓸 수 있다 ({listed}).",
    ]

    if a_items:
        shown = ", ".join(a_items[:MAX_SUMMARY_ITEMS])
        rest = len(a_items) - MAX_SUMMARY_ITEMS
        lines.append(
            f"그중 타사 값까지 확인되어 견줄 수 있는 항목: {shown}"
            + (f" 외 {rest}개" if rest > 0 else "")
        )

    if summary_lines:
        lines.append(
            f"분석자가 우리 제품의 강점을 요약한 총평도 {summary_lines}줄 있다."
        )

    lines += [
        "인증·성분·사용 범위처럼 객관적인 근거라 '문제 분석'과 '근거' 카드를 받쳐 준다.",
        "'홍보/전파' 카드는 이 가운데 우리 제품이 타사보다 앞서는 항목과 총평을 모아"
        " '그래서 이 제품인 이유'로 정리하는 자리다. 비교표가 있으면 홍보/전파를 넣고,"
        " 설명에는 어떤 강점을 모을지 위 항목 이름으로 적는다.",
        "이 항목들은 경로로 고르지 않는다. 문구 단계에서 따로 넘어가므로"
        " source_keys 에 적지 않는다.",
    ]

    return "\n".join(lines)


def render_comparison(result: dict[str, Any]) -> str:
    """문구 단계에 넣을 표. 경쟁사 값은 A급 행에만, 그것도 이름 없이 실린다."""

    # 빈 문자열이면 프롬프트에서 이 절이 통째로 빠진다.
    # '쓸 수 있는 항목이 없다' 같은 안내를 남기면 규칙만 있고 데이터가 없는 절이 되어,
    # 비교표가 없는 공구에서 AI 가 없는 항목을 찾으려 든다.
    if not result["products"] and not result["review"]:
        return ""

    lines = []

    for product in result["products"]:
        # 구성 이름 안에 이미 '/' 가 들어 있는 것들이 있어서(색상 목록) 한 줄로 잇지 않는다.
        for label in product["labels"]:
            lines.append(f"[{label}]")

        if product["ranking_banned"]:
            lines.append("  ※ 이 상품은 등급과 무관하게 순위·최상급 표현을 쓰지 않는다.")

        lines.append("  분류 | 등급 | 항목 | 우리 제품 값 | 타사 값 (이름 없이) | 덧붙은 설명")

        for row in product["rows"]:
            lines.append(
                f"  {row['category']} | {row['grade']}급 | {row['item_name']}"
                f" | {row['value']} | {row['rivals'] or '-'} | {row['note'] or '-'}"
            )

        if product["summary"]:
            lines.append("  분석 총평 (우리 제품에 대한 요약):")
            for line in product["summary"]:
                lines.append(f"    · {line}")

        lines.append("")

    if result["review"]:
        lines.append(
            "아래 상품은 비교 대상이 어긋난 표라 비교표에서 아무것도 가져오지 않는다."
        )
        lines.append(f"  {', '.join(result['review'])}")
        lines.append("")

    if result["conflicts"]:
        lines.append(
            "아래는 비교표와 상품 데이터의 숫자가 어긋나는 항목이다."
            " 언제나 naver_review_count 를 쓴다."
        )
        for conflict in result["conflicts"]:
            lines.append(f"  {conflict}")

    return "\n".join(lines).rstrip()
