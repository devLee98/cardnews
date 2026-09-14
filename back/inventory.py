"""업로드된 공구 JSON 을 프롬프트에 넣을 수 있는 크기로 압축한다.

실제 파일은 리뷰 본문까지 들어 있어 수십만 자에 이르기 때문에 그대로 보낼 수 없다.
카드 단계를 고르는 데 필요한 건 '어떤 데이터가 얼마나 있는지'이므로
경로별로 값이 채워진 정도와 짧은 예시만 남긴다.

경로를 쓰는 이유
  실제 데이터에는 brand.name 과 products[].name 처럼 이름이 겹치는 Key 가 있다.
  Key 이름만 세면 둘이 한 줄로 합쳐져 어느 쪽 데이터인지 알 수 없다.
  배열 인덱스는 [] 로 합쳐서 상품 15개가 한 줄로 모이게 한다.
"""

import json
from typing import Any

MAX_SAMPLE_LENGTH = 80
MAX_PATHS = 200

#: 비교표 필드는 경로를 세지 않고 값도 뽑지 않는다. comparison.py 가 따로 다룬다.
#:
#: 이 셋을 그냥 두면 경로가 249개 늘어난다. values 와 product_notes 가
#: 경쟁사 제품명을 Key 로 쓰기 때문에 상품 하나마다 새 경로가 생기는 탓이다.
#: 늘어난 경로는 MAX_PATHS 상한에 걸려, 경로 순으로 뒤에 있는 consumer_price·name·
#: reviews 같은 정작 필요한 것들을 밀어낸다.
#: 경로 자체에 경쟁사 제품명이 박혀 있어 표에 싣는 것만으로 이름이 노출되기도 한다.
COMPARISON_KEYS = ("comparison_status", "comparison_info", "comparison_rows")

#: 맨 바깥의 이 키는 통째로 건너뛴다. 파일에 대한 설명이지 공구에 대한 설명이 아니다.
#:
#: 빼는 이유가 셋이다.
#:   1. 숫자가 틀리다. 화면이 공구 하나만 남겨 보낼 때 events 만 자르고 meta 는 그대로 둔다.
#:      그래서 상품 16개를 보내면서 meta.product_count 는 154 라고 말한다.
#:   2. 경로 95개 중 23개를 차지한다. 해시, 원본 파일명, 집계 같은 것들이다.
#:   3. 읽는 법을 설명하는 산문이 들어 있다 (meta.comparison_usage).
#:      comparison_rows 를 읽으라고 안내하는데, 그 경로는 여기서 이미 빠져 있다.
IGNORED_ROOTS = ("meta",)

#: 값이 짧을 때만 여러 개를 모은다. 상품이 6종이면 이름 6개 중 3개를 보여줘야
#: "주방세제·밤스슈트 등"처럼 실제 내용을 아는 설명을 쓸 수 있다.
MAX_SAMPLES = 3
SHORT_VALUE_LENGTH = 40


class PathStat:
    __slots__ = ("path", "occurrences", "filled", "items", "samples")

    def __init__(self, path: str) -> None:
        self.path = path
        self.occurrences = 0
        self.filled = 0
        self.items = 0
        self.samples: list[str] = []

    def add_sample(self, value: Any) -> None:
        if len(self.samples) >= MAX_SAMPLES:
            return

        # 첫 예시가 긴 문장이면(큐레이터 피치, 리뷰 본문 등) 하나로 충분하다
        if self.samples and len(self.samples[0]) > SHORT_VALUE_LENGTH:
            return

        sample = _summarize(value)
        if sample and sample not in self.samples:
            self.samples.append(sample)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _summarize(value: Any) -> str | None:
    """스칼라나 스칼라 배열이면 짧은 예시를 만든다. 구조체는 예시를 남기지 않는다."""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        flat = " ".join(value.split())
        return (
            flat if len(flat) <= MAX_SAMPLE_LENGTH else f"{flat[:MAX_SAMPLE_LENGTH]}…"
        )

    if isinstance(value, list) and value and not isinstance(value[0], (dict, list)):
        return _summarize(value[0])

    return None


def build_inventory(data: Any) -> list[dict[str, Any]]:
    stats: dict[str, PathStat] = {}

    def walk(value: Any, path: str) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item, f"{path}[]")
            return

        if not isinstance(value, dict):
            return

        for key, child in value.items():
            if key in COMPARISON_KEYS or (not path and key in IGNORED_ROOTS):
                continue

            child_path = f"{path}.{key}" if path else key

            stat = stats.get(child_path)
            if stat is None:
                stat = PathStat(child_path)
                stats[child_path] = stat

            stat.occurrences += 1

            if not _is_empty(child):
                stat.filled += 1

                if isinstance(child, list):
                    stat.items += len(child)

                stat.add_sample(child)

            walk(child, child_path)

    walk(data, "")

    rows = [
        {
            "path": stat.path,
            # 나오는 자리 중 몇 군데가 채워져 있는지 (3/15 처럼 읽는다)
            "filled": stat.filled,
            "occurrences": stat.occurrences,
            "items": stat.items,
            "samples": stat.samples,
        }
        for stat in stats.values()
    ]

    # 구조를 따라 읽히도록 경로 순으로 둔다
    rows.sort(key=lambda row: row["path"])

    return rows[:MAX_PATHS]


def render_inventory(rows: list[dict[str, Any]]) -> str:
    """프롬프트에 넣을 표 형태의 문자열."""

    lines = ["경로 | 채움 | 항목수 | 예시"]

    for row in rows:
        state = f"{row['filled']}/{row['occurrences']}"
        items = str(row["items"]) if row["items"] else "-"
        samples = " / ".join(row["samples"]) or "-"
        lines.append(f"{row['path']} | {state} | {items} | {samples}")

    return "\n".join(lines)


def empty_paths(rows: list[dict[str, Any]]) -> list[str]:
    """나오는 자리마다 전부 비어 있는 경로."""

    return sorted(row["path"] for row in rows if row["filled"] == 0)


# ────────────────────────────────────────────────
# 문구를 쓰려면 '무엇이 있는지'가 아니라 '실제 값'이 필요하다.
# 구성안이 카드마다 쓸 경로를 알려주므로, 그 경로의 값만 뽑아 쓴다.
# ────────────────────────────────────────────────

EXTRACT_MAX_ITEMS = 6
EXTRACT_MAX_LENGTH = 600


def _compact(value: Any, max_length: int, max_items: int) -> Any:
    """프롬프트에 넣을 수 있게 긴 값을 잘라 낸다."""

    if isinstance(value, str):
        flat = " ".join(value.split())
        return flat if len(flat) <= max_length else f"{flat[:max_length]}…"

    if isinstance(value, list):
        return [_compact(item, max_length, max_items) for item in value[:max_items]]

    if isinstance(value, dict):
        return {
            key: _compact(child, max_length, max_items)
            for key, child in value.items()
            if not _is_empty(child)
        }

    return value


def extract_values(
    data: Any,
    paths: list[str],
    *,
    max_items: int = EXTRACT_MAX_ITEMS,
    max_length: int = EXTRACT_MAX_LENGTH,
) -> dict[str, list[Any]]:
    """주어진 경로들의 실제 값을 뽑는다. 경로마다 최대 max_items 개까지만."""

    wanted = set(paths)
    found: dict[str, list[Any]] = {}
    seen: dict[str, set[str]] = {}

    def walk(value: Any, path: str) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item, f"{path}[]")
            return

        if not isinstance(value, dict):
            return

        for key, child in value.items():
            # 구성안이 비교표나 meta 경로를 적어 오더라도 값을 뽑지 않는다.
            # 비교표는 걸러 내지 않은 원본이라 경쟁사 이름과 단품 가격이 그대로 들어 있고,
            # meta 는 공구가 아니라 파일에 대한 설명이라 카드에 쓸 것이 없다.
            if key in COMPARISON_KEYS or (not path and key in IGNORED_ROOTS):
                continue

            child_path = f"{path}.{key}" if path else key

            if child_path in wanted and not _is_empty(child):
                bucket = found.setdefault(child_path, [])

                if len(bucket) < max_items:
                    compact = _compact(child, max_length, max_items)

                    # 같은 값이 여러 상품에 반복되는 일이 흔하다.
                    # 걸러내지 않으면 자리를 다 차지해서 뒤쪽 상품의 고유한 내용이 잘린다.
                    marker = (
                        compact
                        if isinstance(compact, str)
                        else json.dumps(compact, ensure_ascii=False, sort_keys=True)
                    )
                    known = seen.setdefault(child_path, set())

                    if marker not in known:
                        known.add(marker)
                        bucket.append(compact)

            walk(child, child_path)

    walk(data, "")

    return found


# ────────────────────────────────────────────────
# 상품별로 묶어서 뽑기
#
# extract_values 는 경로마다 값을 따로 모으고, 같은 값이 여러 상품에 반복되면
# 뒤쪽 상품이 잘리지 않도록 중복을 걸러 낸다. 한 경로만 볼 때는 이게 맞다.
#
# 그런데 상품 이름과 숫자를 함께 말하려면 문제가 된다.
# 경로마다 중복을 따로 걸러서 목록의 길이가 제각각이 되기 때문이다.
#
#   name               ['주방세제', '바스앤샴푸', '엉덩이클렌저', '핸드워시', '욕조클리너']
#   naver_rating       [4.92, 4.94, 4.91, 4.95]
#   naver_review_count [9382, 7171, 8897, 10053, 849, 5953]
#
# 몇 번째끼리 짝인지 알 수 없는데 자리만 보고 짝지으면 '핸드워시 후기 10,053건,
# 4.95점' 같은 문구가 나온다. 세 값이 전부 다른 상품 것이다. (실제 4.92점 3,598건)
#
# 그래서 상품 단위 값은 상품별로 묶어서 따로 넘긴다. 한 줄 안의 값은 반드시 한 상품 것이다.
# 목록형 값(reviews, detail_image_urls 등)은 양이 커서 여기 담지 않고 기존 방식대로 둔다.
# ────────────────────────────────────────────────

PRODUCT_PREFIX = "events[].products[]."

#: 상품별로 보여줄 최대 개수. 한 공구에 상품이 44개까지 있어서 전부 싣지 못한다.
MAX_PRODUCT_ROWS = 12

#: 이보다 긴 글은 상품별 표에 담지 않는다. 이름·구성명은 넉넉히 들어가고
#: 셀링포인트나 큐레이터 피치는 걸러지는 길이다.
PRODUCT_TEXT_LIMIT = 40


def _product_values(data: Any):
    """업로드 데이터의 상품들을 차례로 돌려준다."""

    for event in (data.get("events") if isinstance(data, dict) else None) or []:
        if not isinstance(event, dict):
            continue

        for product in event.get("products") or []:
            if isinstance(product, dict):
                yield product


def split_product_paths(data: Any, paths: list[str]) -> tuple[list[str], list[str]]:
    """상품별로 묶을 수 있는 경로와 나머지를 갈라 낸다.

    묶을 수 있는 것은 상품 하나에 값이 하나씩 붙는 경로뿐이다.
    `events[].products[].name` 은 되지만 아래 둘은 안 된다.

    - `events[].products[].reviews[].body` — 상품 하나에 여러 개다 (경로에 [] 가 더 붙는다)
    - `events[].products[].detail_image_urls` — 값 자체가 목록이라 한 칸에 담기지 않는다
    - `events[].products[].curator_pitch` — 긴 글이다

    뒤의 둘은 경로 모양만 봐서는 알 수 없어서 실제 값의 생김새를 본다.
    긴 글을 빼는 이유는 이 표에 중복 제거가 없기 때문이다. 구성이 여러 개면 같은 피치가
    글자 그대로 네 번 실려서, 정작 짝지어야 할 숫자가 묻힌다.
    긴 글은 어느 상품 것인지 헷갈릴 일도 없으니 원래 자리에 두면 된다.
    """

    grouped, rest = [], []
    products = list(_product_values(data))

    for path in paths:
        tail = path[len(PRODUCT_PREFIX) :] if path.startswith(PRODUCT_PREFIX) else ""
        flat = bool(tail) and "." not in tail and "[" not in tail

        if flat:
            flat = not any(_too_big_to_group(product.get(tail)) for product in products)

        (grouped if flat else rest).append(path)

    return grouped, rest


def _too_big_to_group(value: Any) -> bool:
    """상품별 표의 한 칸에 담기에 버거운 값인지."""

    if isinstance(value, (list, dict)):
        return True

    return isinstance(value, str) and len(value.strip()) > PRODUCT_TEXT_LIMIT


def extract_product_rows(
    data: Any,
    paths: list[str],
    *,
    max_rows: int = MAX_PRODUCT_ROWS,
    max_length: int = EXTRACT_MAX_LENGTH,
) -> list[dict[str, Any]]:
    """상품별로 값을 묶어 돌려준다. 한 줄이 상품 하나다."""

    wanted = [path[len(PRODUCT_PREFIX) :] for path in paths if path.startswith(PRODUCT_PREFIX)]

    if not wanted:
        return []

    rows: list[dict[str, Any]] = []

    for product in _product_values(data):
        row = {
            key: _compact(product[key], max_length, 1)
            for key in wanted
            if key in product and not _is_empty(product[key])
        }

        if row:
            rows.append(row)

    return rows[:max_rows]


# 받아 볼 만한 이미지 형식. gif 는 첫 프레임을 뽑아 쓰므로 함께 받는다.
SUPPORTED_IMAGE = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def find_image_urls(data: Any, paths: list[str], limit: int = 3) -> list[str]:
    """구성안이 지목한 경로에서 참조로 쓸 상품 사진 URL 을 뽑는다.

    대표 사진(image_url)이 먼저 나오고, 그다음 상세 이미지(detail_image_urls)가 붙는다.
    상세 이미지는 브랜드가 실제로 찍은 연출컷이라 배경 분위기를 잡는 데 도움이 된다.
    """

    urls: list[str] = []

    # 대표 사진을 먼저 채우기 위해 경로를 두 번 훑는다
    for wanted_detail in (False, True):
        for path, values in extract_values(
            data, paths, max_items=limit * 2, max_length=2000
        ).items():
            is_detail = "detail_image_urls" in path

            if is_detail != wanted_detail:
                continue
            if not ("image_url" in path or "image_urls" in path):
                continue

            for value in values:
                candidates = value if isinstance(value, list) else [value]

                for candidate in candidates:
                    if not isinstance(candidate, str):
                        continue
                    if not candidate.startswith("http"):
                        continue
                    if not candidate.lower().split("?")[0].endswith(SUPPORTED_IMAGE):
                        continue

                    if candidate not in urls:
                        urls.append(candidate)

                    if len(urls) >= limit:
                        return urls

    return urls
