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
