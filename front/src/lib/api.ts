import type { JsonValue } from "@/lib/json";

export type CardPlanItem = {
  /** 카드 단계 이름 (표지, 문제 제기 …) */
  section: string;
  /** 이 카드에서 실제로 쓰는 JSON Key */
  sourceKeys: string[];
  /** 이 카드가 무엇을 보여주는 카드인지 한 줄 설명 */
  description: string;
};

export type CardPlanResponse = {
  cards: CardPlanItem[];
  emptyKeys: string[];
};

/** FastAPI 는 실패를 {detail: "..."} 로 돌려준다. */
async function readError(response: Response) {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // 본문이 JSON 이 아니면 상태 코드만 알린다
  }

  return `요청이 실패했습니다 (HTTP ${response.status})`;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return (await response.json()) as T;
}

export function requestCardPlan(data: JsonValue) {
  return post<CardPlanResponse>("/api/cardnews/plan", { data });
}

/* ── 카드 문구 ── */

export type CardItem = {
  label: string;
  value: string;
  /** 가격 항목일 때만 채워진다 — 정가와 할인율 */
  original: string;
  discount: string;
};

export type CardText = {
  section: string;
  title: string;
  body: string;
  /** 이 카드를 만들 때 우선으로 참고할 브랜드 상세컷. 최종 이미지가 아니라 참조다 */
  referenceUrl: string;
  /** 움직이는 상세컷을 쓰는 카드면 그 주소. 이 카드는 생성하지 않고 원본을 그대로 쓴다 */
  animatedUrl: string;
  /** 카드에서 가장 크게 보여줄 짧은 조각 (숫자·기한 등). 없으면 빈 문자열 */
  highlight: string;
  /** 아래는 AI 가 카드마다 정한 디자인 */
  textPosition: "top" | "center" | "bottom";
  textAlign: "left" | "center";
  theme: "dark" | "light";
  /** 가격표처럼 목록으로 보여줄 정보. 없으면 빈 배열 */
  items: CardItem[];
};

/** 카드 문구는 한 번에 다 받는다. 그래야 카드끼리 흐름이 이어진다. */
export function requestCardDraft(
  data: JsonValue,
  cards: CardPlanItem[],
  instruction: string,
  assets: CardAsset[],
) {
  return post<{ cards: CardText[] }>("/api/cardnews/draft", {
    data,
    cards,
    instruction,
    assets,
  });
}

/* ── 브랜드 상세 이미지 ── */

export type CardAsset = {
  index: number;
  url: string;
  scene: string;
  textAmount: "none" | "some" | "heavy";
  suggest: string;
  animated: boolean;
};

/**
 * 상세페이지 이미지 중 카드에 그대로 쓸 만한 것을 골라 둔다.
 * 구성안 생성과 서로 기다릴 필요가 없어서 업로드 직후 나란히 부른다.
 */
export function requestCardAssets(data: JsonValue) {
  return post<{ images: CardAsset[] }>("/api/cardnews/assets", { data });
}

/* ── 카드 배경 이미지 ── */

export type CardImageResponse = {
  imageBase64: string;
  usedReference: boolean;
};

/**
 * 카드 한 장을 통째로 만든다. 문구도 이미지 안에 함께 그려진다.
 * 카드마다 30초 안팎이 걸려서 한 장씩 따로 부른다.
 */
export function requestCardImage(
  data: JsonValue,
  card: CardText & { sourceKeys: string[] },
) {
  return post<CardImageResponse>("/api/cardnews/image", {
    data,
    section: card.section,
    title: card.title,
    body: card.body,
    highlight: card.highlight,
    items: card.items,
    sourceKeys: card.sourceKeys,
    referenceUrl: card.referenceUrl,
    textPosition: card.textPosition,
    textAlign: card.textAlign,
    theme: card.theme,
  });
}

/**
 * 동시에 너무 많이 부르면 OpenAI 쪽에서 막히므로 몇 개씩 끊어서 돌린다.
 * 하나가 끝나면 다음 것을 바로 시작한다.
 */
export async function runWithLimit<T>(
  items: T[],
  limit: number,
  task: (item: T, index: number) => Promise<void>,
) {
  let cursor = 0;

  async function worker() {
    while (cursor < items.length) {
      const index = cursor++;
      await task(items[index], index);
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, worker),
  );
}
