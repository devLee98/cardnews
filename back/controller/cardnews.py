import asyncio
import base64
import io
import ipaddress
import json
import os
import random
from typing import Any
from urllib.parse import urlparse

from PIL import Image

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

import avatar
from assets import (
    ACCENT_IMAGES,
    fit_to_card,
    gather_candidates,
    pick_accent,
    to_supported,
)
from card_spec import CARD_STAGES, MAX_CARDS
from comparison import build_comparison, render_comparison, summarize_comparison
from inventory import (
    build_inventory,
    empty_paths,
    extract_product_rows,
    extract_values,
    find_image_urls,
    render_inventory,
    split_product_paths,
)
from prompts import (
    ASSET_RESPONSE_SCHEMA,
    ASSET_SYSTEM_PROMPT,
    DRAFT_RESPONSE_SCHEMA,
    DRAFT_SYSTEM_PROMPT,
    IMAGE_SIZE,
    PLAN_RESPONSE_SCHEMA,
    PLAN_SYSTEM_PROMPT,
    build_draft_prompt,
    build_image_prompt,
    build_plan_prompt,
)

# main.py 를 거치지 않고 이 모듈만 불러도 .env 가 읽히도록 한다
load_dotenv()

router = APIRouter(
    prefix="/cardnews",
    tags=["cardnews"],
)

TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5")

# gpt-5 계열은 답하기 전에 스스로 생각하는 시간을 갖는다. 그 시간을 조절하는 값이다.
# 추론 모델이 아닌 모델(gpt-4.1 등)을 쓸 때는 빈 값으로 두어 옵션을 빼야 한다.
#
# 구성안 고르기와 사진 분류는 생각을 오래 시켜도 결과가 거의 같아서 low 로 둔다.
# (medium 은 한 번에 50초를 넘긴다. 배포 nginx 응답 제한은 300초다)
REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "low").strip()

# 문구 쓰기만 따로 올린다.
#
# 카드 8장을 한 번에 쓰면서 서로 말이 겹치지 않게 하고, 22/60자를 지키고,
# 가격 세 종류(정가·공구가·타채널 최저가)를 헷갈리지 않아야 한다.
# 세 호출 중 생각이 실제로 필요한 곳은 여기뿐이라, 여기만 medium 을 준다.
# 전부 올리면 사진 분류까지 같이 느려져서 기다리는 시간만 늘어난다.
DRAFT_REASONING_EFFORT = os.getenv(
    "OPENAI_DRAFT_REASONING_EFFORT", "medium"
).strip()

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

# 카드에 글자를 직접 그려 넣기 때문에 화질이 곧 글자 선명도다.
# 빈 값으로 두면 옵션을 빼고 부른다 (모델이 알아서 판단).
#
# high 로 올려 봤더니 한 장당 시간이 눈에 띄게 늘어 카드 8장 전체가 두 배 가까이
# 걸렸다. 화질 차이는 그만큼 크지 않아서 기본값으로 되돌렸다.
# 배포 nginx 응답 제한이 300초라, 올릴 생각이면 한 장당 시간을 먼저 재야 한다.
IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "").strip()

# 참조로 넣은 브랜드 실사를 얼마나 그대로 따라갈지.
#
# ⚠️ gpt-image-1 계열 전용이다. gpt-image-2 에 넘기면 400 으로 카드가 통째로 실패한다.
#      "The model 'gpt-image-2' does not support the 'input_fidelity' parameter."
#    그래서 기본값은 꺼 둔다. gpt-image-1 로 내릴 때만 켠다.
INPUT_FIDELITY = os.getenv("OPENAI_INPUT_FIDELITY", "").strip()

# 화면에서 그대로 내려받을 수 있게 png 로 고정한다.
# 응답을 data:image/png 로 감싸 돌려주므로 이 값과 어긋나면 안 된다.
IMAGE_FORMAT = "png"

#: 이미지 생성에 참조로 넣을 수 있는 유일한 경로
REFERENCE_PATH = "events[].products[].detail_image_urls"

# 단계를 명세 순서대로 되돌리기 위한 표
STAGE_ORDER = {stage["stage"]: index for index, stage in enumerate(CARD_STAGES)}

#: 큐레이터 아바타를 얹는 카드와 사진 경로
COVER_STAGE = "표지"
CURATOR_IMAGE_PATH = "events[].curator.profile_image_url"

#: 아바타를 카드 가장자리에서 얼마나 띄울지.
#: 문구는 카드 가운데로 모이므로, 모서리에 바짝 붙일수록 글자와 덜 겹친다.
#: 56 일 때 표지의 마지막 줄 끝이 아바타에 가려지는 일이 있어 24 로 좁혔다.
AVATAR_MARGIN = 24

#: 가격표 카드는 공구 카드뉴스에 반드시 한 장 있어야 한다
PRICE_STAGE = "가격 & 스펙"
PRICE_PATHS = next(
    stage["required"] + stage["optional"]
    for stage in CARD_STAGES
    if stage["stage"] == PRICE_STAGE
)


class PlanRequest(BaseModel):
    # 업로드된 JSON 을 그대로 받는다. 구조를 고정하지 않는다.
    data: Any


class PlanCard(BaseModel):
    section: str
    source_keys: list[str] = Field(default_factory=list, alias="sourceKeys")
    description: str
    model_config = {"populate_by_name": True}


class PlanResponse(BaseModel):
    cards: list[PlanCard]
    empty_keys: list[str] = Field(default_factory=list, alias="emptyKeys")

    model_config = {"populate_by_name": True}


def _client():
    """OpenAI 클라이언트. 키가 없으면 여기서 걸러 알아보기 쉬운 오류를 낸다."""

    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY가 설정되지 않았습니다. back/.env에 키를 넣어주세요.",
        )

    from openai import AsyncOpenAI

    return AsyncOpenAI()


@router.post("/plan", response_model=PlanResponse, response_model_by_alias=True)
async def create_plan(payload: PlanRequest):
    """업로드된 공구 데이터를 보고 만들 수 있는 카드 구성안을 뽑는다."""

    inventory = build_inventory(payload.data)

    if not inventory:
        raise HTTPException(
            status_code=400,
            detail="읽을 수 있는 데이터가 없습니다. JSON 구조를 확인해주세요.",
        )

    missing = empty_paths(inventory)

    # 비교표는 inventory 표에 실리지 않는다. 어떤 소재가 있는지만 따로 알려준다.
    comparison = summarize_comparison(build_comparison(payload.data))

    client = _client()

    options: dict[str, Any] = {}
    if REASONING_EFFORT:
        options["reasoning_effort"] = REASONING_EFFORT

    try:
        completion = await client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_plan_prompt(
                        render_inventory(inventory), missing, comparison
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": PLAN_RESPONSE_SCHEMA,
            },
            **options,
        )
    except HTTPException:
        raise
    except Exception as error:  # OpenAI 쪽 실패는 그대로 흘리지 않고 502로 감싼다
        raise HTTPException(
            status_code=502,
            detail=f"카드 구성안 생성에 실패했습니다: {error}",
        ) from error

    content = completion.choices[0].message.content

    if not content:
        raise HTTPException(status_code=502, detail="구성안 응답이 비어 있습니다.")

    cards = json.loads(content).get("cards", [])

    # 같은 단계가 두 번 나오는 것을 막고, 명세 순서(데려오기 → 믿음주기 → 부추기기)로 되돌린다.
    seen: set[str] = set()
    unique = []

    for card in cards:
        section = card.get("section")
        if section in STAGE_ORDER and section not in seen:
            seen.add(section)
            unique.append(card)

    # 가격표는 공구 카드뉴스의 핵심이라 빠지면 안 된다.
    # 데이터에 가격이 있는데 AI 가 빠뜨렸으면 여기서 채워 넣는다.
    if PRICE_STAGE not in seen:
        available = {row["path"] for row in inventory if row["filled"]}
        price_paths = [path for path in PRICE_PATHS if path in available]

        if price_paths:
            unique.append(
                {
                    "section": PRICE_STAGE,
                    "source_keys": price_paths,
                    "description": "구성별 정가와 할인율, 공구가를 표로 정리",
                }
            )

    unique.sort(key=lambda card: STAGE_ORDER[card["section"]])

    return PlanResponse(
        cards=[
            PlanCard(
                section=card["section"],
                sourceKeys=card.get("source_keys", []),
                description=card.get("description", ""),
            )
            for card in unique[:MAX_CARDS]
        ],
        emptyKeys=missing,
    )


# ────────────────────────────────────────────────
# 움짤 원본 내려주기
#
# 내보내기에서 쓴다. 움짤 카드는 브랜드 서버의 원본을 그대로 쓰는데, 그 서버들이
# CORS 를 열어 주지 않아 브라우저가 직접 받지 못한다. 그래서 그 카드만 빠지고
# 나머지만 저장되는 일이 있었다. 서버는 CORS 와 무관하게 받을 수 있으니 대신 받아
# 넘겨준다.
#
# 형식은 바꾸지 않는다. gif 를 png 로 바꾸면 움직임이 사라진다.
# ────────────────────────────────────────────────

#: 원본을 그대로 넘겨줄 형식. 이 밖의 것은 카드 이미지가 아니므로 받지 않는다.
PASSTHROUGH_MIME = {
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

ASSET_TIMEOUT = 30

#: 브랜드 상세컷은 프레임이 100장을 넘는 것이 있어 생각보다 크다.
#: 실제로 141프레임 webp 가 31MB 였다. 너무 조이면 그 카드만 또 빠진다.
MAX_ASSET_BYTES = 64_000_000


async def _reject_private(host: str) -> None:
    """사내망이나 로컬 주소를 향한 요청을 막는다.

    주소를 받아서 서버가 대신 열어 주는 창구라, 막아 두지 않으면 바깥에서
    내부 주소를 넣어 훔쳐보는 통로가 된다. 이름을 실제로 풀어 본 뒤 판단한다.
    """

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except Exception:
        raise HTTPException(status_code=400, detail="주소를 찾을 수 없습니다.")

    for info in infos:
        address = ipaddress.ip_address(info[4][0])

        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
        ):
            raise HTTPException(status_code=400, detail="허용되지 않는 주소입니다.")


@router.get("/asset")
async def fetch_asset(url: str):
    """움짤 원본을 받아서 형식 그대로 넘겨준다."""

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=400, detail="http(s) 주소만 받습니다.")

    await _reject_private(parsed.hostname)

    import httpx2

    try:
        async with httpx2.AsyncClient(
            timeout=ASSET_TIMEOUT, follow_redirects=True
        ) as http:
            response = await http.get(url)
            response.raise_for_status()
    except Exception as error:
        raise HTTPException(
            status_code=502, detail=f"원본을 받지 못했습니다: {error}"
        ) from error

    if len(response.content) > MAX_ASSET_BYTES:
        raise HTTPException(status_code=502, detail="파일이 너무 큽니다.")

    content_type = response.headers.get("content-type", "").split(";")[0].strip()

    # Content-Type 을 안 보내거나 엉뚱하게 보내는 서버가 있다 (프랭클린 상세페이지가 그렇다).
    # 헤더를 믿지 말고 실제로 열어 보고 판단한다.
    if content_type not in PASSTHROUGH_MIME:
        try:
            fmt = Image.open(io.BytesIO(response.content)).format or ""
        except Exception:
            raise HTTPException(status_code=502, detail="이미지가 아닙니다.")

        content_type = f"image/{fmt.lower()}"

        if content_type not in PASSTHROUGH_MIME:
            raise HTTPException(
                status_code=502, detail=f"내려받을 수 없는 형식입니다: {fmt}"
            )

    # 4:5 로 맞춰서 내보낸다. 움짤 카드는 원본을 그대로 쓰기 때문에 비율이 제각각이라,
    # 손대지 않으면 4:5 카드 아홉 장 사이에 혼자 다른 비율로 끼게 된다.
    # 맞추지 못하면 원본을 그대로 준다. 비율이 안 맞아도 카드가 빠지는 것보다 낫다.
    fitted = fit_to_card(response.content, content_type)
    content, content_type = fitted or (response.content, content_type)

    return Response(content=content, media_type=content_type)


# ────────────────────────────────────────────────
# 상세 이미지 살펴보기
# 브랜드가 이미 만들어 둔 사진 중 카드에 그대로 쓸 만한 것을 골라 둔다.
# 업로드 직후 구성안 생성과 나란히 돌려도 되므로 따로 뺐다.
# ────────────────────────────────────────────────


class AssetRequest(BaseModel):
    data: Any


class AssetCard(BaseModel):
    index: int
    url: str
    scene: str
    text_amount: str = Field(alias="textAmount")
    suggest: str
    animated: bool

    model_config = {"populate_by_name": True}


class AssetResponse(BaseModel):
    images: list[AssetCard]


@router.post("/assets", response_model=AssetResponse, response_model_by_alias=True)
async def inspect_assets(payload: AssetRequest):
    """상세 이미지를 훑어서 카드에 쓸 만한 것만 설명과 함께 돌려준다."""

    candidates = await gather_candidates(payload.data)

    if not candidates:
        return AssetResponse(images=[])

    client = _client()

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": "\n".join(
                f"{index}번 이미지 ({candidate.width}x{candidate.height}"
                + (", 움직이는 이미지" if candidate.animated else "")
                + ")"
                for index, candidate in enumerate(candidates)
            ),
        }
    ]

    for candidate in candidates:
        content.append(
            {
                "type": "image_url",
                # 자세히 볼 필요는 없고 무엇이 찍혔는지만 알면 된다
                "image_url": {"url": candidate.preview, "detail": "low"},
            }
        )

    options: dict[str, Any] = {}
    if REASONING_EFFORT:
        options["reasoning_effort"] = REASONING_EFFORT

    try:
        completion = await client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": ASSET_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": ASSET_RESPONSE_SCHEMA,
            },
            **options,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"상세 이미지를 살펴보지 못했습니다: {error}",
        ) from error

    body = completion.choices[0].message.content
    if not body:
        return AssetResponse(images=[])

    judged = {item["index"]: item for item in json.loads(body).get("images", [])}

    images = []
    for index, candidate in enumerate(candidates):
        verdict = judged.get(index)

        # 움직이는 것은 사용자가 눈으로 보고 직접 고르므로 판단으로 걸러내지 않는다.
        # 정지한 것은 참조로 자동으로 쓰이니 쓸 만하다고 본 것만 남긴다.
        if not candidate.animated and (not verdict or not verdict.get("usable")):
            continue

        images.append(
            AssetCard(
                index=index,
                url=candidate.url,
                scene=(verdict or {}).get("scene", ""),
                textAmount=(verdict or {}).get("text_amount", "none"),
                suggest=(verdict or {}).get("suggest", "없음"),
                animated=candidate.animated,
            )
        )

    return AssetResponse(images=images)


# ────────────────────────────────────────────────
# 카드 문구 생성
# 카드를 한 번에 다 쓰게 해야 앞뒤 흐름이 이어지고 같은 말이 겹치지 않는다.
# ────────────────────────────────────────────────


class PlanCardInput(BaseModel):
    section: str
    source_keys: list[str] = Field(default_factory=list, alias="sourceKeys")
    description: str = ""

    model_config = {"populate_by_name": True}


class AssetInput(BaseModel):
    index: int
    url: str
    scene: str = ""
    text_amount: str = Field(default="none", alias="textAmount")
    suggest: str = ""
    animated: bool = False

    model_config = {"populate_by_name": True}


class DraftRequest(BaseModel):
    data: Any
    cards: list[PlanCardInput]
    instruction: str | None = None
    assets: list[AssetInput] = Field(default_factory=list)


class DraftItem(BaseModel):
    label: str
    value: str
    # 가격 항목일 때만 채워진다 (정가 / 할인율)
    original: str = ""
    discount: str = ""


class DraftCard(BaseModel):
    section: str
    title: str
    body: str
    # 문구와 함께 AI 가 정한 카드 디자인
    highlight: str = ""
    text_position: str = Field(default="bottom", alias="textPosition")
    text_align: str = Field(default="left", alias="textAlign")
    theme: str = "dark"
    items: list[DraftItem] = Field(default_factory=list)
    #: 이 카드를 만들 때 우선으로 참고할 브랜드 상세컷 (정지 이미지).
    #: 최종 이미지가 아니라 참조다. 문구는 새로 그려진다.
    reference_url: str = Field(default="", alias="referenceUrl")
    #: 움직이는 상세컷을 고른 카드면 그 주소.
    #: gpt-image 는 gif 를 못 만들어서 이 카드만 원본을 그대로 쓰고 문구는 아래에 붙인다.
    animated_url: str = Field(default="", alias="animatedUrl")

    model_config = {"populate_by_name": True}


class DraftResponse(BaseModel):
    cards: list[DraftCard]


TEXT_POSITIONS = {"top", "center", "bottom"}
TEXT_ALIGNS = {"left", "center"}
THEMES = {"dark", "light"}
MAX_ITEMS = 4

#: 움직이는 상세컷을 그대로 쓸 수 있는 카드 수의 상한.
#: 이 카드만 문구가 이미지 밖에 붙어서 결이 다르므로 너무 많으면 흐름이 깨진다.
#: 화면에서도 하나만 고를 수 있다. 두 곳의 값이 같아야 한다.
MAX_ANIMATED = 1

#: 문구 생성 때 한 번에 보여줄 상세컷 수.
#: 후보를 전부 보여주면 매번 같은 것만 고른다. 매번 다른 묶음을 보여줘 결과를 갈리게 한다.
CATALOG_SAMPLE = 8

#: 참조로 넣을 상품 사진 최대 장수.
#: 브랜드 상세컷을 여러 장 보여줄수록 실제 촬영 톤에 가깝게 나온다.
MAX_REFERENCES = 5


def _pick(value: Any, allowed: set[str], fallback: str) -> str:
    return value if value in allowed else fallback


@router.post("/draft", response_model=DraftResponse, response_model_by_alias=True)
async def create_draft(payload: DraftRequest):
    """확정된 구성안으로 카드마다 들어갈 제목과 본문을 쓴다."""

    if not payload.cards:
        raise HTTPException(status_code=400, detail="카드 구성안이 비어 있습니다.")

    # 구성안이 지목한 경로의 실제 값만 뽑는다. 원본 JSON 은 너무 커서 그대로 못 보낸다.
    paths = sorted({path for card in payload.cards for path in card.source_keys})

    # 상품 단위 값은 상품별로 묶어서 따로 넘긴다.
    # 한 목록에 섞어 두면 어느 값이 어느 상품 것인지 알 수 없어 숫자가 어긋난다.
    product_paths, other_paths = split_product_paths(payload.data, paths)
    values = extract_values(payload.data, other_paths)
    product_rows = extract_product_rows(payload.data, product_paths)

    # 비교표는 구성안이 고른 경로와 상관없이 늘 넘긴다.
    # 경로로 고를 수 있는 값이 아니라 걸러 낸 결과이기 때문이다.
    comparison = render_comparison(build_comparison(payload.data))

    plan = [card.model_dump(by_alias=False) for card in payload.cards]

    # 후보를 전부, 그것도 늘 같은 순서로 보여주면 매번 같은 것만 고른다.
    # 번호는 그대로 두고 매번 다른 묶음을 다른 차례로 보여준다.
    catalog = [asset.model_dump(by_alias=False) for asset in payload.assets]
    if len(catalog) > CATALOG_SAMPLE:
        catalog = random.sample(catalog, CATALOG_SAMPLE)
    random.shuffle(catalog)

    client = _client()

    # 문구 쓰기만 생각을 더 시킨다. 다른 두 호출과 값이 다르다.
    options: dict[str, Any] = {}
    if DRAFT_REASONING_EFFORT:
        options["reasoning_effort"] = DRAFT_REASONING_EFFORT

    try:
        completion = await client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_draft_prompt(
                        plan,
                        values,
                        payload.instruction,
                        catalog,
                        comparison,
                        product_rows,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": DRAFT_RESPONSE_SCHEMA,
            },
            **options,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"카드 문구 생성에 실패했습니다: {error}",
        ) from error

    content = completion.choices[0].message.content
    if not content:
        raise HTTPException(status_code=502, detail="문구 응답이 비어 있습니다.")

    written = json.loads(content).get("cards", [])

    by_index = {asset.index: asset for asset in payload.assets}
    taken: set[str] = set()

    animated_used = 0
    last_index = len(payload.cards) - 1

    # 움짤은 사용자가 고른 것만 넘어온다. 고른 개수와 상한 중 작은 쪽까지 쓴다.
    picked = [asset for asset in payload.assets if asset.animated][:MAX_ANIMATED]
    max_animated = len(picked)

    # 단계가 밀리지 않도록 순서대로 짝지어 붙이고, 단계 이름은 구성안 것을 쓴다.
    cards = []
    for index, card in enumerate(payload.cards):
        source = written[index] if index < len(written) else {}
        items = source.get("items") or []

        # 같은 상세컷이 여러 카드에 겹쳐 쓰이지 않게 한 번 쓰면 뺀다
        asset = by_index.get(source.get("image_index", -1))
        chosen = asset.url if asset else ""

        if chosen in taken:
            chosen, asset = "", None
        if chosen:
            taken.add(chosen)

        # 움짤을 원본 그대로 쓸지 판단한다.
        # 첫 장과 마지막 장은 공구 이름과 마감 시각이 크게 들어가야 해서 쓰지 않는다.
        # 자리가 없으면 버리지 않고 정지 참조로 돌린다 (첫 프레임이 참고 자료가 된다).
        use_animated = bool(asset and asset.animated)

        if use_animated and (
            index in (0, last_index) or animated_used >= max_animated
        ):
            use_animated = False

        if use_animated:
            animated_used += 1

        cards.append(
            DraftCard(
                section=card.section,
                # 움짤 카드는 문구를 비운다.
                # 원본을 그대로 쓰는 카드라 글자를 이미지 안에 그려 넣을 수가 없다.
                # 화면에서만 아래에 붙여 두면 내보낼 때 그 글자가 사라져서,
                # 미리 보던 카드와 저장된 카드가 달라진다.
                # 움직임 하나로 보여주는 카드로 두는 편이 낫다.
                title="" if use_animated else source.get("title", ""),
                body="" if use_animated else source.get("body", ""),
                highlight="" if use_animated else source.get("highlight", ""),
                textPosition=_pick(
                    source.get("text_position"), TEXT_POSITIONS, "bottom"
                ),
                textAlign=_pick(source.get("text_align"), TEXT_ALIGNS, "left"),
                theme=_pick(source.get("theme"), THEMES, "dark"),
                items=[
                    DraftItem(
                        label=item.get("label", ""),
                        value=item.get("value", ""),
                        original=item.get("original", ""),
                        discount=item.get("discount", ""),
                    )
                    for item in ([] if use_animated else items[:MAX_ITEMS])
                    if item.get("label") or item.get("value")
                ],
                referenceUrl="" if use_animated else chosen,
                animatedUrl=chosen if use_animated else "",
            )
        )

    _place_picked_animations(cards, picked)

    return DraftResponse(cards=cards)


def _place_picked_animations(
    cards: list[DraftCard], picked: list[AssetInput]
) -> None:
    """사용자가 고른 움짤이 빠짐없이 쓰이도록 자리를 잡아 준다.

    어느 카드에 넣을지는 AI 가 정하는 게 원칙이지만, 고른 것을 쓰지 않고 넘어가면
    고른 의미가 없다. AI 가 빠뜨린 것만 여기서 채워 넣는다.
    """

    if not picked or len(cards) < 3:
        return

    used = {card.animated_url for card in cards if card.animated_url}
    # 첫 장과 마지막 장은 공구 이름과 마감 시각이 크게 들어가야 해서 비워 둔다
    open_slots = list(range(1, len(cards) - 1))

    for asset in picked:
        if asset.url in used:
            continue

        # 이미 움짤이 들어간 자리는 건너뛴다
        free = [index for index in open_slots if not cards[index].animated_url]
        if not free:
            return

        # 비전 모델이 어울린다고 본 단계를 먼저 찾고, 없으면 앞쪽 빈자리에 넣는다
        target = next(
            (index for index in free if cards[index].section == asset.suggest),
            free[0],
        )

        cards[target].animated_url = asset.url
        cards[target].reference_url = ""

        # 여기서 움짤로 바뀐 카드도 문구를 비운다.
        # 위 반복문에서 이미 비운 카드와 같은 규칙이어야 한다.
        cards[target].title = ""
        cards[target].body = ""
        cards[target].highlight = ""
        cards[target].items = []

        used.add(asset.url)


# ────────────────────────────────────────────────
# 카드 배경 이미지 생성
# 카드마다 30~60초가 걸려서 한 장씩 따로 부른다. 프론트가 몇 개씩 나눠 호출한다.
# ────────────────────────────────────────────────


class ImageRequest(BaseModel):
    data: Any
    section: str
    title: str = ""
    body: str = ""
    highlight: str = ""
    items: list[DraftItem] = Field(default_factory=list)
    source_keys: list[str] = Field(default_factory=list, alias="sourceKeys")
    #: 이 카드에 어울린다고 고른 상세컷. 있으면 맨 앞 참조로 쓴다.
    reference_url: str = Field(default="", alias="referenceUrl")
    # 문구를 이미지 안에 함께 그리므로 배치와 톤도 넘긴다
    text_position: str = Field(default="bottom", alias="textPosition")
    text_align: str = Field(default="left", alias="textAlign")
    theme: str = "dark"
    #: 문구 단계와 같은 지시문. 여기서는 장면에 관한 부분만 읽는다.
    instruction: str | None = None

    model_config = {"populate_by_name": True}


class ImageResponse(BaseModel):
    image_base64: str = Field(alias="imageBase64")
    used_reference: bool = Field(alias="usedReference")

    model_config = {"populate_by_name": True}


#: 배너나 여백용으로 쓰이는 얇은 띠 이미지가 섞여 있어서 너무 작은 파일은 버린다
MIN_REFERENCE_BYTES = 20_000
MAX_REFERENCE_BYTES = 20_000_000


def _avatar_spot(text_position: str, card: tuple[int, int]) -> tuple[str, tuple[int, int]]:
    """아바타를 놓을 모서리 이름과 좌표.

    기본은 오른쪽 아래다. 다만 문구도 아래쪽에 모이면 서로 겹치므로
    그때만 오른쪽 위로 피한다. 문구 위치는 이미 정해져서 넘어오기 때문에
    겹칠지 아닐지를 여기서 계산할 수 있다.
    """

    width, height = card
    x = width - avatar.SIZE - AVATAR_MARGIN

    if text_position == "bottom":
        return "오른쪽 위", (x, AVATAR_MARGIN)

    return "오른쪽 아래", (x, height - avatar.SIZE - AVATAR_MARGIN)


async def _fetch_avatar(data: Any) -> bytes | None:
    """큐레이터 프로필 사진을 받아 원형 아바타로 만든다.

    참조 사진과 달리 크기 하한을 두지 않는다. 프로필은 원래 작은 파일이다.
    """

    values = extract_values(data, [CURATOR_IMAGE_PATH], max_items=1).get(
        CURATOR_IMAGE_PATH, []
    )
    url = next((v for v in values if isinstance(v, str) and v.startswith("http")), None)

    if not url:
        return None

    import httpx2

    try:
        async with httpx2.AsyncClient(timeout=15, follow_redirects=True) as http:
            response = await http.get(url)
            response.raise_for_status()

            return avatar.build(response.content)
    except Exception:
        # 아바타가 없다고 카드까지 실패시키지는 않는다
        return None


def _paste_avatar(card_png: bytes, badge: bytes, text_position: str) -> bytes:
    """만들어진 카드 위에 아바타를 얹는다."""

    card = Image.open(io.BytesIO(card_png)).convert("RGBA")
    badge_image = Image.open(io.BytesIO(badge)).convert("RGBA")

    _, spot = _avatar_spot(text_position, card.size)
    card.alpha_composite(badge_image, spot)

    buffer = io.BytesIO()
    card.convert("RGB").save(buffer, format="PNG")

    return buffer.getvalue()


async def _download(url: str) -> tuple[bytes, str] | None:
    """상품 사진을 내려받는다. 쓸 수 없는 파일이면 None 을 준다."""

    import httpx2

    try:
        async with httpx2.AsyncClient(timeout=20, follow_redirects=True) as http:
            response = await http.get(url)
            response.raise_for_status()

            # Content-Type 을 안 보내는 서버가 있어서 헤더만 보고 거르지 않는다.
            # 실제로 열리는지는 to_supported 가 판단한다.
            content_type = response.headers.get("content-type", "").split(";")[0]

            size = len(response.content)
            if size < MIN_REFERENCE_BYTES or size > MAX_REFERENCE_BYTES:
                return None

            # gif 나 헤더가 없는 파일은 여기서 형식을 맞춰 준다
            return to_supported(response.content, content_type)
    except Exception:
        return None


#: 공구마다 포인트 색을 한 번만 계산해 둔다.
#: 카드는 한 장씩 따로 만들어지므로 캐시가 없으면 같은 사진을 카드 수만큼 다시 받는다.
_ACCENT_CACHE: dict[str, str] = {}

#: 포인트 색을 뽑을 사진. 상품 대표컷이다.
ACCENT_PATH = "events[].products[].image_url"


async def _accent_color(data: Any, *, on_dark: bool) -> str:
    """이 공구의 포인트 색.

    카드는 한 장씩 따로 만들어지지만 색은 공구 하나에 하나여야 한다.
    카드가 제 참조컷에서 뽑으면 카드마다 색이 달라져 시리즈가 흐트러진다.
    그래서 카드가 무엇을 골랐든 늘 같은 대표컷 목록에서 뽑는다.
    """

    urls = find_image_urls(data, [ACCENT_PATH], limit=ACCENT_IMAGES)

    if not urls:
        return ""

    key = f"{'|'.join(urls)}|{on_dark}"

    if key in _ACCENT_CACHE:
        return _ACCENT_CACHE[key]

    downloaded = await asyncio.gather(*(_download(url) for url in urls))
    images = [item[0] for item in downloaded if item]

    accent = pick_accent(images, on_dark=on_dark) or ""
    _ACCENT_CACHE[key] = accent

    return accent


@router.post("/image", response_model=ImageResponse, response_model_by_alias=True)
async def create_image(payload: ImageRequest):
    """카드 1장의 배경 이미지를 만든다. 문구는 얹지 않고 그림만 만든다."""

    client = _client()

    # 구성안이 상품 사진을 쓰라고 지목한 카드만 사진을 참조로 넣는다.
    # (제품명을 노출하면 안 되는 단계는 애초에 image_url 을 지목하지 않는다)
    #
    # 대표 사진 한 장만 주면 배경이 브랜드와 겉도는 그림이 나온다.
    # 상세 이미지까지 같이 넣으면 실제 연출 톤을 따라간다.
    # 참조는 detail_image_urls 안의 이미지만 쓴다. 반드시 지켜야 하는 규칙이다.
    # 대표 사진(image_url)은 상품마다 같은 컷이 반복되는 경우가 많아
    # 그것만 보고 그리면 카드가 다 비슷해진다.
    # 호출한 쪽이 무엇을 넘기든 여기서 경로를 고정한다.
    paths = [REFERENCE_PATH]

    # 카드마다 고른 상세컷을 맨 앞에 둔다. 그 장면을 가장 강하게 따라가게 된다.
    urls = find_image_urls(payload.data, paths, limit=12)

    theme = _pick(payload.theme, THEMES, "dark")

    accent = await _accent_color(payload.data, on_dark=theme == "dark")

    if payload.reference_url:
        urls = [payload.reference_url] + [
            url for url in urls if url != payload.reference_url
        ]

    references: list[tuple[bytes, str]] = []
    for url in urls:
        downloaded = await _download(url)
        if downloaded:
            references.append(downloaded)
        if len(references) >= MAX_REFERENCES:
            break

    text_position = _pick(payload.text_position, TEXT_POSITIONS, "bottom")

    # 표지에는 큐레이터 얼굴이 들어간다. 실제 사진이라 모델이 그리지 못하므로
    # 다 만들어진 뒤에 코드가 얹고, 프롬프트로는 그 자리를 미리 비워 둔다.
    badge = await _fetch_avatar(payload.data) if payload.section == COVER_STAGE else None
    corner = _avatar_spot(text_position, (1, 1))[0] if badge else None

    prompt = build_image_prompt(
        section=payload.section,
        title=payload.title,
        body=payload.body,
        highlight=payload.highlight,
        items=[item.model_dump() for item in payload.items],
        has_reference=bool(references),
        text_position=text_position,
        text_align=_pick(payload.text_align, TEXT_ALIGNS, "left"),
        theme=theme,
        accent=accent,
        avatar_corner=corner,
        instruction=payload.instruction,
    )

    options: dict[str, Any] = {"output_format": IMAGE_FORMAT}
    if IMAGE_QUALITY:
        options["quality"] = IMAGE_QUALITY

    async def render(with_references: bool):
        if with_references and references:
            files = [
                (f"reference{index}.{content_type.split('/')[-1]}", content, content_type)
                for index, (content, content_type) in enumerate(references)
            ]

            edit_options = dict(options)
            if INPUT_FIDELITY:
                edit_options["input_fidelity"] = INPUT_FIDELITY

            return await client.images.edit(
                model=IMAGE_MODEL,
                image=files,
                prompt=prompt,
                size=IMAGE_SIZE,
                n=1,
                **edit_options,
            )

        return await client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size=IMAGE_SIZE,
            n=1,
            **options,
        )

    try:
        result = await render(True)
    except HTTPException:
        raise
    except Exception as error:
        # 상세컷에 아기 사진 같은 게 섞여 있으면 안전 시스템이 결과물을 막는다.
        # 그 카드만 통째로 실패하는 것보다 참조 없이 한 번 더 그려보는 편이 낫다.
        if references and "moderation_blocked" in str(error):
            try:
                result = await render(False)
            except Exception as retry_error:
                raise HTTPException(
                    status_code=502,
                    detail=f"카드 생성에 실패했습니다: {retry_error}",
                ) from retry_error
        else:
            raise HTTPException(
                status_code=502,
                detail=f"카드 생성에 실패했습니다: {error}",
            ) from error

    encoded = result.data[0].b64_json if result.data else None
    if not encoded:
        raise HTTPException(status_code=502, detail="이미지 응답이 비어 있습니다.")

    if badge:
        try:
            merged = _paste_avatar(base64.b64decode(encoded), badge, text_position)
            encoded = base64.b64encode(merged).decode()
        except Exception:
            # 합성이 실패해도 카드 자체는 살린다. 아바타만 빠진다.
            pass

    return ImageResponse(
        imageBase64=f"data:image/{IMAGE_FORMAT};base64,{encoded}",
        usedReference=bool(references),
    )
