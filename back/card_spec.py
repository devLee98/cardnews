"""카드 단계 명세 — 엑셀 '카드 구성안' 시트를 옮긴 것.

시트가 갱신되면 이 파일만 고치면 된다.

단계 구분
  데려오기 : 도입부로 관심 환기
  믿음주기 : body. 제품 소구점 + 정성/정량적 근거 + 객관적 가격/스펙으로 신뢰 형성
  부추기기 : 공구 현황을 통해 행동 유도

용어
  required  필수 데이터 — 이 카드를 만들 때 반드시 반영해야 하는 값.
            비어 있으면 안내나 조치가 필요하다.
  optional  활용 가능 데이터 — 참고되었으면 하는 값.
            비어 있으면 활용하지 않아도 된다.
  core      엑셀에서 볼드로 표시된 핵심 6개 카드.
            카드뉴스는 최소 6장, 최대 10장이며 입력 데이터에 따라 AI가 단계를 골라 장수를 확정한다.

⚠️ 데이터 이름은 엑셀 표기가 아니라 실제 JSON 경로를 쓴다.
   엑셀은 중첩 객체를 밑줄로 합쳐 적어서(brand_name) 데이터에 없는 이름이 된다.
   배열은 [] 로 표기하며, inventory.py 가 만드는 경로와 형태가 같아야 한다.

   엑셀 표기            → 실제 경로
   curator_nickname          → events[].curator.nickname
   curator_profile_image_url → events[].curator.profile_image_url
   brand_name                → events[].brand.name
   brand_tagline             → events[].brand.tagline
   brand_description         → events[].brand.description
   brand_keyword             → events[].brand.keyword
   social_post_cpation(오타) → events[].social_posts[].caption
   reservation_add_count     → events[].reservation.add_count
   spec[]                    → events[].products[].structured_specs
   curator[]                 → events[].curator (배열이 아니라 객체 하나)
   name                      → events[].products[].name (브랜드명이 아니라 제품명)
   hashtags                  → 제품·인스타 양쪽 모두 사용
"""

from typing import TypedDict


class CardStage(TypedDict):
    stage: str
    group: str
    core: bool
    required: list[str]
    optional: list[str]
    purpose: str
    constraint: str | None


CARD_STAGES: list[CardStage] = [
    {
        "stage": "표지",
        "group": "데려오기",
        "core": True,
        "required": [
            "events[].event_name",
            "events[].curator.nickname",
            "events[].products[].name",
        ],
        "optional": [
            # 프로필 이미지는 필수에서 뺐다.
            # 필수로 두면 이 값 하나가 비어 있을 때 AI 가 표지 카드를 통째로 뺀다.
            # ("필수 데이터가 비어 있는 단계는 넣지 않는다" 규칙을 그대로 따른 결과다)
            # 공구명·큐레이터 이름·제품명만 있으면 표지는 만들 수 있다.
            "events[].curator.profile_image_url",
            "events[].is_preorder",
            "events[].brand.name",
            "events[].brand.tagline",
            "events[].brand.description",
            "events[].brand.keyword",
        ],
        "purpose": (
            "공구 제품 대표 이미지와 함께 제품, 인플루언서, 가격 할인율 정보와 "
            "그 기한 정보를 담는다."
        ),
        "constraint": None,
    },
    {
        "stage": "문제 제기",
        "group": "데려오기",
        "core": True,
        "required": [],
        "optional": [
            "events[].products[].selling_point",
            "events[].products[].curator_pitch",
        ],
        "purpose": (
            "제품이 필요한 문제 상황을 서술한다. "
            "필수 데이터를 지정하지 않았으니 맥락에 맞게 직접 만들어 낸다."
        ),
        "constraint": "브랜드명과 제품명을 노출하지 않는다.",
    },
    {
        "stage": "해결의 실마리",
        "group": "데려오기",
        "core": False,
        "required": [],
        "optional": [
            "events[].products[].selling_point",
            "events[].products[].curator_pitch",
            "events[].products[].usp",
            "events[].products[].hashtags",
            "events[].social_posts[].hashtags",
            "events[].products[].naver_rating",
            "events[].products[].naver_review_count",
        ],
        "purpose": (
            "제품의 셀링포인트와 평판 정보를 통해 해결의 실마리를 제시한다. "
            "필수 데이터를 지정하지 않았으니 맥락에 맞게 직접 만들어 낸다."
        ),
        "constraint": "브랜드명과 제품명을 노출하지 않는다.",
    },
    {
        "stage": "문제 분석",
        "group": "믿음주기",
        "core": False,
        "required": [],
        "optional": [
            "events[].products[].selling_point",
            "events[].products[].curator_pitch",
            "events[].products[].usp",
            "events[].products[].hashtags",
            "events[].social_posts[].hashtags",
            "events[].products[].naver_rating",
            "events[].products[].naver_review_count",
        ],
        "purpose": (
            "문제 상황을 제품 속성, 인증 같은 더 객관적인 정보를 통해 설명한다."
        ),
        "constraint": None,
    },
    {
        "stage": "해결(제품)",
        "group": "믿음주기",
        "core": True,
        "required": [
            "events[].brand.name",
            "events[].products[].name",
            "events[].products[].image_url",
        ],
        "optional": [
            "events[].products[].detail_image_urls",
            "events[].products[].selling_point",
            "events[].products[].curator_pitch",
        ],
        "purpose": (
            "브랜드와 제품이 본격적으로 등장한다. 셀링포인트와 큐레이터 피치를 적극 활용한다."
        ),
        "constraint": None,
    },
    {
        "stage": "근거",
        "group": "믿음주기",
        "core": True,
        "required": [
            "events[].products[].reviews",
            "events[].products[].naver_rating",
            "events[].products[].naver_review_count",
        ],
        "optional": [
            "events[].products[].features",
            "events[].products[].materials",
            "events[].products[].certifications",
            "events[].products[].detail_image_urls",
            "events[].products[].structured_specs",
        ],
        "purpose": (
            "자체 제품 리뷰와 네이버 리뷰를 근거로 삼되, 데이터가 있으면 제품의 특성과 "
            "스펙을 활용해 어필한다."
        ),
        "constraint": (
            "리뷰 수는 숫자로 적지 않는다. 평점과 후기 내용으로 근거를 댄다."
        ),
    },
    {
        "stage": "인플 코멘트",
        "group": "믿음주기",
        "core": False,
        "required": [],
        "optional": [
            "events[].social_posts[].caption",
            "events[].products[].detail_image_urls",
        ],
        "purpose": (
            "데이터가 있으면 인플루언서가 직접 작성한 포스트 문구를 활용해 어필한다."
        ),
        "constraint": None,
    },
    {
        "stage": "가격 & 스펙",
        "group": "믿음주기",
        "core": True,
        "required": [
            "events[].products[].consumer_price",
            "events[].products[].base_sale_price",
            "events[].products[].lowest_price",
            "events[].products[].discount_rate_derived",
        ],
        "optional": [
            # 가격을 구성별로 보여주려면 어떤 구성인지 이름이 있어야 한다.
            # (엑셀에는 없지만 가격만 나열하면 무엇의 가격인지 알 수 없다)
            "events[].products[].option1",
            "events[].products[].name",
            "events[].products[].detail_image_urls",
            "events[].products[].structured_specs",
        ],
        "purpose": (
            "데이터가 있으면 제품의 가격과 객관적인 정보 위주로 전달하는 카드로, "
            "팩트 중심으로 어필한다. 구성별로 정가와 할인율, 공구가를 함께 보여준다."
        ),
        "constraint": (
            "structured_specs 값은 추론해서 만들어 내지 않는다. 데이터에 있는 값만 쓴다."
        ),
    },
    {
        "stage": "홍보/전파",
        "group": "부추기기",
        "core": False,
        # 알림 신청수(reservation.add_count)를 일부러 빼 두었다.
        # 정확한 숫자를 보여주지 않기로 했고, 경로를 주지 않으면 값 자체가 넘어가지 않아
        # 실수로 적을 일이 없다. 아래 제약은 그 위에 한 겹 더 두는 것이다.
        #
        # lowest_price 를 필수로 두면 그 값이 통째로 없는 공구에서 카드가 사라진다.
        # (실제로 8건 중 1건이 그렇다) 가격 이야기를 못 해도 리뷰로는 어필할 수 있으므로
        # 리뷰 수만 필수로 둔다. 가격은 있을 때만 쓰는 쪽이 맞다.
        "required": ["events[].products[].naver_review_count"],
        "optional": [
            "events[].products[].lowest_price",
            # 타채널 최저가는 공구가와 나란히 놓아야 싼지 비싼지 말할 수 있다
            "events[].products[].base_sale_price",
            "events[].products[].discount_rate_derived",
            "events[].products[].naver_rating",
            # reviews[].body 대신 reviews 를 통째로 준다.
            # 별점이 함께 넘어와야 낮은 별점 리뷰를 걸러 낼 수 있다.
            "events[].products[].reviews",
            "events[].curator",
            "events[].products[].minimum_sales_quantity",
        ],
        "purpose": (
            "다른 곳보다 싸게 산다는 것과 리뷰가 쌓여 있다는 것을 근거로 한 번 더 어필해 "
            "참여와 전파를 유도한다. 네이버 리뷰와 자체 리뷰를 함께 쓰고, "
            "데이터가 있으면 공구 가능 최소 수량과 인플루언서 정보도 활용한다."
        ),
        "constraint": (
            "알림 신청수는 정확한 숫자로 적지 않는다. "
            "리뷰 수도 숫자로 적지 않는다. 먼저 써 본 사람이 많다는 것만 말로 전한다. "
            "타채널 최저가(lowest_price)는 공구가와 견줄 때만 쓰고, "
            "공구가가 더 쌀 때만 싸다고 말한다. 값이 같거나 없으면 가격 이야기를 하지 않는다. "
            "리뷰를 인용할 때는 별점이 높은 것만 쓴다."
        ),
    },
    {
        "stage": "CTA",
        "group": "부추기기",
        "core": True,
        "required": ["events[].reservation.time_sale_end_time"],
        "optional": [
            "events[].products[].lowest_price",
            "events[].products[].discount_rate_derived",
            "events[].products[].selling_point",
            "events[].products[].curator_pitch",
            "events[].products[].usp",
            "events[].products[].hashtags",
            "events[].social_posts[].hashtags",
        ],
        "purpose": (
            "공구 마감 시각을 CTA로 사용하며, 필요하면 가격 정보나 셀링포인트를 써서 "
            "마지막으로 후킹한다."
        ),
        "constraint": None,
    },
]

MIN_CARDS = 6
MAX_CARDS = 10

CORE_STAGES = [stage["stage"] for stage in CARD_STAGES if stage["core"]]

#: 명세에 쓰인 모든 데이터 경로 (중복 없이)
SPEC_PATHS = sorted(
    {path for stage in CARD_STAGES for path in stage["required"] + stage["optional"]}
)
