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

export async function requestCardPlan(
  data: JsonValue,
): Promise<CardPlanResponse> {
  const response = await fetch("/api/cardnews/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return (await response.json()) as CardPlanResponse;
}
