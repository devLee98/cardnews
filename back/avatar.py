"""큐레이터 프로필 사진을 표지에 얹을 원형 아바타로 만든다.

카드는 이미지 모델이 문구까지 통째로 그리지만, 큐레이터 얼굴만은 실제 사진이라
모델이 그릴 수 없다. 그래서 다 만들어진 표지 위에 이것만 따로 합성한다.

디자이너가 준 순서 그대로다.
  1. 프로필 이미지 로드
  2. 정사각형 센터 크롭 (짧은 변 기준)
  3. 260x260 리사이즈
  4. 원형 마스크 (테두리 5px 안쪽 = 반지름 125px)
  5. 보라 → 핫핑크 세로 그라디언트 테두리 5px 합성
  6. 260x260 RGBA PNG (배경 투명)
"""

import io

from PIL import Image, ImageDraw

SIZE = 260
BORDER = 5

#: 테두리 그라디언트. 디자이너 스펙 그대로 세로 방향이다.
GRADIENT_START = (150, 0, 255)  # 보라 (상단)
GRADIENT_END = (255, 0, 80)  # 핫핑크 (하단)

#: 원 가장자리가 계단처럼 보이지 않도록 크게 그린 뒤 줄인다
SCALE = 4


def _square(image: Image.Image) -> Image.Image:
    """짧은 변을 기준으로 가운데를 정사각형으로 잘라낸다."""

    edge = min(image.size)
    left = (image.width - edge) // 2
    top = (image.height - edge) // 2

    return image.crop((left, top, left + edge, top + edge))


def _gradient() -> Image.Image:
    """위에서 아래로 흐르는 세로 그라디언트."""

    grad = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(grad)

    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        draw.line(
            ((0, y), (SIZE, y)),
            fill=tuple(
                round(start + (end - start) * ratio)
                for start, end in zip(GRADIENT_START, GRADIENT_END)
            ),
        )

    return grad


def _circle(diameter: int) -> Image.Image:
    """가운데 정렬된 원 마스크."""

    big = Image.new("L", (SIZE * SCALE, SIZE * SCALE), 0)
    inset = (SIZE - diameter) / 2 * SCALE

    ImageDraw.Draw(big).ellipse(
        (inset, inset, SIZE * SCALE - inset - 1, SIZE * SCALE - inset - 1),
        fill=255,
    )

    return big.resize((SIZE, SIZE), Image.LANCZOS)


def build(raw: bytes) -> bytes | None:
    """프로필 사진 원본 → 원형 아바타 PNG. 열지 못하면 None."""

    try:
        image = Image.open(io.BytesIO(raw))
        # 움직이는 프로필이면 첫 프레임만 쓴다
        image.seek(0)
        photo = _square(image.convert("RGB")).resize((SIZE, SIZE), Image.LANCZOS)
    except Exception:
        return None

    # 마스크를 paste 의 인자로 넘기면 반투명한 가장자리가 투명 배경(검정)과 섞여
    # 테두리 색이 죽는다. 색은 그대로 두고 알파만 씌운 뒤 겹쳐야 스펙대로 나온다.
    ring = _gradient().convert("RGBA")
    ring.putalpha(_circle(SIZE))

    face = photo.convert("RGBA")
    face.putalpha(_circle(SIZE - BORDER * 2))

    # 그라디언트 원을 통째로 깔고 그 위에 사진을 얹으면 가장자리 5px 만 테두리로 남는다
    avatar = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    avatar = Image.alpha_composite(avatar, ring)
    avatar = Image.alpha_composite(avatar, face)

    buffer = io.BytesIO()
    avatar.save(buffer, format="PNG")

    return buffer.getvalue()
