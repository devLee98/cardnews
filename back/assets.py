"""공구 데이터에 들어 있는 상세 이미지를 카드에 쓸 수 있는지 살펴본다.

상세페이지 이미지 목록에는 쓸 만한 연출컷과 그렇지 않은 것이 섞여 있다.
  - 860x1 짜리 여백 띠
  - 브랜드 로고만 있는 상단 배너
  - 글자가 가득한 설명 이미지
  - 실제 제품 연출컷, 후기 애니메이션

URL 이름만 봐서는 구분이 안 되므로, 실제로 받아서 크기를 재고
비전 모델에게 무엇이 찍혀 있는지 물어본 뒤 카드에 쓸지 정한다.
"""

import asyncio
import base64
import hashlib
import io
from typing import Any

from PIL import Image

from inventory import extract_values

#: 카드 배경으로 쓰려면 이 정도는 되어야 한다
MIN_EDGE = 400
#: 세로로 너무 긴 상세컷은 잘라내면 내용이 남지 않는다
MIN_RATIO = 0.35
MAX_RATIO = 2.5
#: 움직이는 상세컷은 사용자가 직접 고르는 목록이라 자르지 않고 최대한 살린다.
MAX_ANIMATED_CANDIDATES = 20
#: 정지 상세컷은 참조용이라 이 정도면 충분하다.
MAX_STATIC_CANDIDATES = 12

DOWNLOAD_TIMEOUT = 20


class Candidate:
    __slots__ = ("url", "width", "height", "animated", "preview", "digest")

    def __init__(
        self,
        url: str,
        width: int,
        height: int,
        animated: bool,
        preview: str,
        digest: str,
    ) -> None:
        self.url = url
        self.width = width
        self.height = height
        self.animated = animated
        #: 비전 모델에 보낼 첫 프레임 (data URL). gif 도 여기서는 정지 이미지가 된다.
        self.preview = preview
        #: 내려받은 파일 자체의 해시. 같은 사진이 다른 이름으로 올라온 것을 잡는다.
        self.digest = digest

    @property
    def ratio(self) -> float:
        return self.width / self.height if self.height else 0


def collect_urls(data: Any, limit: int = 300) -> list[str]:
    """데이터에서 상세 이미지 URL 을 중복 없이 모은다."""

    paths = ["events[].products[].detail_image_urls"]
    urls: list[str] = []

    for values in extract_values(
        data, paths, max_items=limit, max_length=4000
    ).values():
        for value in values:
            for candidate in value if isinstance(value, list) else [value]:
                if (
                    isinstance(candidate, str)
                    and candidate.startswith("http")
                    and candidate not in urls
                ):
                    urls.append(candidate)

    return urls[:limit]


def _inspect(url: str, raw: bytes) -> Candidate | None:
    """실제 크기를 재고, 카드에 쓰기 어려운 것은 걸러낸다."""

    try:
        image = Image.open(io.BytesIO(raw))
        width, height = image.size

        if width < MIN_EDGE or height < MIN_EDGE:
            return None

        ratio = width / height
        if ratio < MIN_RATIO or ratio > MAX_RATIO:
            return None

        animated = getattr(image, "n_frames", 1) > 1

        # 비전 모델에 보낼 축소본. gif 는 첫 프레임만 쓴다.
        image.seek(0)
        preview = image.convert("RGB")
        preview.thumbnail((512, 512))

        buffer = io.BytesIO()
        preview.save(buffer, format="JPEG", quality=70)
        encoded = base64.b64encode(buffer.getvalue()).decode()

        return Candidate(
            url=url,
            width=width,
            height=height,
            animated=animated,
            preview=f"data:image/jpeg;base64,{encoded}",
            digest=hashlib.sha256(raw).hexdigest(),
        )
    except Exception:
        return None


async def gather_candidates(data: Any) -> list[Candidate]:
    """상세 이미지를 내려받아 쓸 만한 것만 남긴다."""

    import httpx2

    urls = collect_urls(data)
    if not urls:
        return []

    async with httpx2.AsyncClient(
        timeout=DOWNLOAD_TIMEOUT, follow_redirects=True
    ) as http:

        async def fetch(url: str) -> Candidate | None:
            try:
                response = await http.get(url)
                response.raise_for_status()

                # Content-Type 을 안 보내는 서버가 있다 (프랭클린 상세페이지의 webp 가 그렇다).
                # 헤더를 믿지 말고 실제로 열어 보고 판단한다.
                return _inspect(url, response.content)
            except Exception:
                return None

        results = await asyncio.gather(*(fetch(url) for url in urls))

    # URL 이 다르면 다른 이미지로 보고 여기까지 온다. 하지만 브랜드가 같은 사진을
    # 상품마다 다른 이름으로 올리거나 CDN 파라미터만 바꿔 두는 일이 흔해서,
    # 화면에 같은 후기 움짤이 여러 장 뜬다.
    # 파일을 이미 받아 뒀으니 내용으로 한 번 더 거른다. 먼저 나온 쪽을 남긴다.
    found: list[Candidate] = []
    seen: set[str] = set()

    for item in results:
        if not item or item.digest in seen:
            continue

        seen.add(item.digest)
        found.append(item)

    # 앞에서부터 자르면 문서 앞쪽 상품(주방세제)의 이미지만 남고
    # 뒤쪽 상품(핸드워시, 욕조클리너)의 움짤이 통째로 사라진다.
    # 움직이는 것과 정지한 것을 따로 세어 종류별로 골고루 남긴다.
    animated = [item for item in found if item.animated]
    static = [item for item in found if not item.animated]

    return (
        animated[:MAX_ANIMATED_CANDIDATES] + static[:MAX_STATIC_CANDIDATES]
    )


#: 이미지 편집 API 가 받는 형식
SUPPORTED_MIME = {"image/jpeg", "image/png", "image/webp"}


def to_supported(raw: bytes, content_type: str) -> tuple[bytes, str] | None:
    """참조로 넘길 수 있는 형식으로 맞춘다.

    gif 와 움직이는 webp 는 편집 API 가 받지 않으므로 첫 프레임만 뽑아 PNG 로 바꾼다.
    Content-Type 이 비어 있는 서버도 있어서 그럴 때도 열어 보고 판단한다.
    """

    if content_type in SUPPORTED_MIME:
        try:
            image = Image.open(io.BytesIO(raw))
            # 움직이는 webp 는 형식은 맞지만 편집 API 가 받지 않는다
            if getattr(image, "n_frames", 1) == 1:
                return raw, content_type
        except Exception:
            return None

    try:
        image = Image.open(io.BytesIO(raw))
        image.seek(0)

        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")

        return buffer.getvalue(), "image/png"
    except Exception:
        return None


# ────────────────────────────────────────────────
# 포인트 색 뽑기
#
# 카드 문구는 흰색 아니면 먹색뿐이라 공구마다 톤이 똑같아 보였다.
# 그렇다고 AI 에게 색을 고르라고 하면 사진에 없는 색을 지어내 제품과 겉돈다.
#
# 데이터에는 브랜드 색이 없다 (brand.keyword 는 비어 있고 색 필드도 없다).
# 그래서 브랜드가 직접 찍은 사진에서 색을 빌려 온다.
# 사진에 실제로 있는 색이라 무엇을 고르든 제품과 어울린다.
# ────────────────────────────────────────────────

#: 색을 세는 동안 쓸 크기. 원본 그대로 훑으면 느리고, 이 정도면 색 분포는 같다.
ACCENT_SIZE = 80

#: 색을 뽑을 때 볼 대표컷 수. 상품마다 포장 색이 달라서 여러 장을 합쳐야 색이 안 흔들린다.
#: 상세컷 대신 대표컷을 쓴다. 상세컷은 맨 앞이 흰 배너인 경우가 많고 30MB짜리도 있다.
ACCENT_IMAGES = 5

#: 배경과 그림자를 걸러 내는 기준.
#: 제품컷은 흰 배경이 대부분이라 걸러 내지 않으면 언제나 회색이 뽑힌다.
ACCENT_MIN_SATURATION = 0.25
ACCENT_MIN_VALUE = 0.15
ACCENT_MAX_VALUE = 0.95

#: 색이라고 할 만한 픽셀이 이보다 적으면 포인트 색을 쓰지 않는다.
#: 흑백에 가까운 사진에서 억지로 색을 뽑으면 엉뚱한 색이 나온다.
ACCENT_MIN_RATIO = 0.02

#: 비슷한 색끼리 묶을 칸 수. 24칸이면 한 칸이 15도다.
ACCENT_BUCKETS = 24

#: 뽑은 색은 색상(hue)만 쓰고 진하기는 여기로 고정한다.
#: 사진에서 나온 채도·명도를 그대로 쓰면 글자가 배경에 묻히거나 형광색이 된다.
#: theme 이 dark 여도 모델이 밝은 사진을 그려 오는 일이 있어서, 연한 색은 묻힌다.
#: 채도를 올려 두면 배경이 밝든 어둡든 글자가 버틴다.
ACCENT_ON_LIGHT = (0.60, 0.50)  # 밝은 바탕 위 — 깊고 차분하게
ACCENT_ON_DARK = (0.60, 0.88)  # 어두운 바탕 위 — 밝게 띄우되 채도로 버틴다


def pick_accent(images: list[bytes], *, on_dark: bool = False) -> str | None:
    """제품 사진들에서 포인트로 쓸 색을 뽑는다. 색이 없다시피 하면 None.

    한 장만 보면 그 상품 포장 색이 공구 전체의 색이 된다.
    같은 공구 안에서도 상품마다 색이 달라서(주방세제는 초록, 욕조클리너는 파랑)
    어느 한 장을 골랐느냐에 따라 카드 색이 뒤바뀐다.
    그래서 여러 장의 색을 모두 합쳐 가장 넓게 쓰인 색을 고른다.
    """

    import colorsys

    # 색상 칸마다 픽셀 수와 색상 합을 모은다.
    # 칸 안에서도 색이 조금씩 다르므로 평균을 내야 대표색이 된다.
    counts = [0] * ACCENT_BUCKETS
    hues = [0.0] * ACCENT_BUCKETS
    colored = 0
    looked = 0

    for raw in images:
        try:
            image = Image.open(io.BytesIO(raw))
            image.seek(0)
            image = image.convert("RGB").resize((ACCENT_SIZE, ACCENT_SIZE))
        except Exception:
            continue

        looked += 1

        for red, green, blue in image.getdata():
            hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255, green / 255, blue / 255
            )

            if saturation < ACCENT_MIN_SATURATION:
                continue
            if not ACCENT_MIN_VALUE <= value <= ACCENT_MAX_VALUE:
                continue

            index = min(int(hue * ACCENT_BUCKETS), ACCENT_BUCKETS - 1)
            counts[index] += 1
            hues[index] += hue
            colored += 1

    if not looked or colored < ACCENT_SIZE * ACCENT_SIZE * looked * ACCENT_MIN_RATIO:
        return None

    best = max(range(ACCENT_BUCKETS), key=lambda index: counts[index])
    hue = hues[best] / counts[best]

    saturation, value = ACCENT_ON_DARK if on_dark else ACCENT_ON_LIGHT
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)

    return "#{:02X}{:02X}{:02X}".format(
        round(red * 255), round(green * 255), round(blue * 255)
    )


# ────────────────────────────────────────────────
# 움짤을 카드 규격에 맞추기
#
# 움짤 카드는 AI 가 그리지 못해 브랜드 원본을 그대로 쓴다.
# 그래서 문구를 이미지 안에 그려 넣을 수가 없고, 화면에서만 아래에 따로 붙여 뒀다.
# 내보내면 그 문구가 사라진다. DOM 에만 있던 글자라 파일에는 담기지 않는다.
#
# 게다가 원본은 비율이 제각각이다 (실측 0.62 ~ 2.13). 4:5 카드 아홉 장 사이에
# 혼자 다른 비율로 끼면 한 덱으로 보이지 않는다.
#
# 그래서 저장할 때 4:5 로 맞춘다. 다만 잘라내지 않는다.
# 가로로 긴 원본(860x403)을 4:5 로 자르면 폭의 63%가 날아간다.
# 대신 남는 자리를 원본 가장자리 색으로 채운다. 배경이 흰 상세컷이 대부분이라
# 검은 띠와 달리 이어 붙인 티가 나지 않는다.
# ────────────────────────────────────────────────

#: 카드 비율 (가로/세로)
CARD_RATIO = 4 / 5

#: 4:5 로 맞춘 뒤의 최대 가로 길이. 원본이 이보다 크면 줄인다.
#: 프레임이 141장짜리 webp 도 있어서 줄이지 않으면 파일이 감당이 안 된다.
CARD_MAX_WIDTH = 1080

#: 여백 색을 고를 때 볼 테두리 두께
EDGE_BAND = 4


def _edge_color(frame: Image.Image) -> tuple[int, int, int]:
    """가장자리에 가장 많은 색. 여백을 이 색으로 채우면 이어 붙인 티가 덜 난다."""

    width, height = frame.size
    counts: dict[tuple[int, int, int], int] = {}

    for x in range(0, width, max(1, width // 60)):
        for y in (0, height - 1):
            counts[frame.getpixel((x, y))] = counts.get(frame.getpixel((x, y)), 0) + 1

    for y in range(0, height, max(1, height // 60)):
        for x in (0, width - 1):
            counts[frame.getpixel((x, y))] = counts.get(frame.getpixel((x, y)), 0) + 1

    return max(counts, key=counts.get) if counts else (255, 255, 255)


def _fit_frame(
    frame: Image.Image, canvas: tuple[int, int], background: tuple[int, int, int]
) -> Image.Image:
    """프레임을 4:5 캔버스 가운데에 얹는다. 잘라내지 않고 줄이기만 한다."""

    width, height = canvas
    scaled = frame.copy()
    scaled.thumbnail((width, height), Image.LANCZOS)

    card = Image.new("RGB", canvas, background)
    card.paste(scaled, ((width - scaled.width) // 2, (height - scaled.height) // 2))

    return card


def fit_to_card(raw: bytes, content_type: str) -> tuple[bytes, str] | None:
    """움짤을 4:5 로 맞춰 같은 형식으로 다시 담는다. 실패하면 None (원본을 그대로 쓴다)."""

    from PIL import ImageSequence

    fmt = {"image/gif": "GIF", "image/webp": "WEBP"}.get(content_type)

    if not fmt:
        return None

    try:
        image = Image.open(io.BytesIO(raw))

        width = min(image.width, CARD_MAX_WIDTH)
        canvas = (width, round(width / CARD_RATIO))

        first = image.convert("RGB")
        background = _edge_color(first)

        frames = []
        durations = []

        for frame in ImageSequence.Iterator(image):
            durations.append(frame.info.get("duration", image.info.get("duration", 100)))
            frames.append(_fit_frame(frame.convert("RGB"), canvas, background))

        if not frames:
            return None

        extra = {}

        if fmt == "GIF":
            # RGB 로 그냥 저장하면 프레임마다 팔레트가 따로 생겨 파일이 대여섯 배로 분다.
            # 첫 프레임의 팔레트를 나머지가 함께 쓰게 하면 원본 크기 수준으로 돌아온다.
            base = frames[0].quantize(colors=256)
            frames = [base] + [
                frame.quantize(palette=base, colors=256) for frame in frames[1:]
            ]
            extra["optimize"] = True

        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            format=fmt,
            save_all=len(frames) > 1,
            append_images=frames[1:],
            duration=durations,
            loop=image.info.get("loop", 0),
            **extra,
        )

        return buffer.getvalue(), content_type
    except Exception:
        # 형식이 특이하거나 프레임이 너무 많아 실패할 수 있다.
        # 그때는 원본을 그대로 내보낸다. 비율은 안 맞아도 카드가 빠지는 것보다 낫다.
        return None
