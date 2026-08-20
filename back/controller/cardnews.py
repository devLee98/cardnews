import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from card_spec import CARD_STAGES, MAX_CARDS
from inventory import build_inventory, empty_paths, render_inventory
from prompts import PLAN_RESPONSE_SCHEMA, PLAN_SYSTEM_PROMPT, build_plan_prompt

# database.py 를 거치지 않고 이 모듈만 불러도 .env 가 읽히도록 한다
load_dotenv()

router = APIRouter(
    prefix="/cardnews",
    tags=["cardnews"],
)

TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5")

# gpt-5 계열은 추론에 시간을 많이 쓴다. 기본값(medium)으로 두면 한 번에 50초를 넘겨
# 배포 환경의 nginx 기본 타임아웃(60초)에 걸린다.
# low 로 두면 17초 안팎이고 고르는 단계는 거의 같다.
# 추론 모델이 아닌 모델(gpt-4.1 등)을 쓸 때는 빈 값으로 두어 옵션을 빼야 한다.
REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "low").strip()

# 단계를 명세 순서대로 되돌리기 위한 표
STAGE_ORDER = {stage["stage"]: index for index, stage in enumerate(CARD_STAGES)}


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
                    "content": build_plan_prompt(render_inventory(inventory), missing),
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
