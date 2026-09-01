import type { JsonValue } from "@/lib/json";

/* 업로드 JSON 한 건에는 공구가 여러 건(최대 5건) 들어 있을 수 있다.
   카드뉴스는 공구 한 건 기준으로 만들어지므로, 여기서 목록을 뽑아
   고른 것 하나만 남긴 JSON 을 만들어 서버로 보낸다.
   서버는 공구가 한 건인 평소 데이터와 똑같이 다루면 되어 손댈 것이 없다. */

export type EventOption = {
  /** 원본 events 배열에서의 자리 */
  index: number;
  /** 화면에 보여줄 공구 이름 */
  name: string;
  /** 이 공구에 딸린 상품 수 — 어느 공구인지 가늠하는 데 쓴다 */
  productCount: number;
};

/** 객체일 때만 꺼내 쓴다. 배열이나 원시값이면 null. */
function fields(value: JsonValue | undefined) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as { [key: string]: JsonValue })
    : null;
}

/**
 * 업로드된 JSON 에서 공구 목록을 뽑는다.
 * events 가 배열이 아니거나 비어 있으면 빈 배열을 돌려준다. (호출한 쪽에서 안내한다)
 */
export function readEvents(root: JsonValue): EventOption[] {
  const events = fields(root)?.events;
  if (!Array.isArray(events)) return [];

  return events.map((event, index) => {
    const item = fields(event);
    const name = item?.event_name;
    const products = item?.products;

    return {
      index,
      // 이름이 비어 있어도 고를 수는 있어야 하므로 자리 번호로 대신한다
      name:
        typeof name === "string" && name.trim()
          ? name.trim()
          : `이름 없는 공구 ${index + 1}`,
      productCount: Array.isArray(products) ? products.length : 0,
    };
  });
}

/**
 * 고른 공구 하나만 남긴 JSON 을 만든다.
 * events 바깥의 값은 그대로 둔다. 원본은 건드리지 않는다.
 */
export function pickEvent(root: JsonValue, index: number): JsonValue {
  const item = fields(root);
  const events = item?.events;

  if (!item || !Array.isArray(events) || !events[index]) return root;

  return { ...item, events: [events[index]] };
}
