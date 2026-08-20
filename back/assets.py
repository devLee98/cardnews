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
    __slots__ = ("url", "width", "height", "animated", "preview")

    def __init__(
        self, url: str, width: int, height: int, animated: bool, preview: str
    ) -> None:
        self.url = url
        self.width = width
        self.height = height
        self.animated = animated
        #: 비전 모델에 보낼 첫 프레임 (data URL). gif 도 여기서는 정지 이미지가 된다.
        self.preview = preview

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

    found = [item for item in results if item]

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
