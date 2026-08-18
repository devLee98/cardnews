import type { JsonValue } from "@/lib/json";

/* ────────────────────────────────────────────────
   업로드한 공구 JSON 을 훑어서 카드를 만들기 전에 짚고 넘어갈 것들을 뽑는다.
   - 값이 비어 있는 Key
   - 형식이 어긋난 Key
   ──────────────────────────────────────────────── */

export type Analysis = {
  emptyKeys: string[];
  invalidKeys: string[];
};

function isEmptyValue(value: JsonValue) {
  if (value === null) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

const DATE_KEY = /(date|_at|time)$/i;
const NUMBER_KEY = /(price|count|rate|amount|quantity|fee|follower)/i;
const URL_KEY = /(url|link)$/i;

/**
 * Key 이름이 기대하는 형식과 값이 맞는지 본다.
 * 비어 있는 값은 여기서 걸러내지 않고 `emptyKeys` 로 따로 모은다.
 */
function isInvalidValue(key: string, value: JsonValue) {
  if (typeof value === "string" && value.trim() !== "") {
    if (DATE_KEY.test(key)) return Number.isNaN(Date.parse(value));
    if (URL_KEY.test(key)) return !/^https?:\/\//i.test(value);

    if (NUMBER_KEY.test(key)) {
      // "22,900원", "49 %" 처럼 단위가 붙은 것도 숫자로 본다
      const stripped = value.replace(/[,\s원%]/g, "");
      return stripped === "" || Number.isNaN(Number(stripped));
    }
  }

  // 숫자여야 할 자리에 불리언이 들어온 경우
  if (typeof value === "boolean" && NUMBER_KEY.test(key)) return true;

  return false;
}

export function analyzeData(data: JsonValue): Analysis {
  const invalid = new Set<string>();
  const occurrences = new Map<string, number>();
  const emptyOccurrences = new Map<string, number>();

  function bump(map: Map<string, number>, key: string) {
    map.set(key, (map.get(key) ?? 0) + 1);
  }

  function walk(value: JsonValue) {
    if (Array.isArray(value)) {
      value.forEach(walk);
      return;
    }

    if (!value || typeof value !== "object") return;

    for (const [key, child] of Object.entries(value)) {
      bump(occurrences, key);

      if (isEmptyValue(child)) {
        bump(emptyOccurrences, key);
      } else if (isInvalidValue(key, child)) {
        invalid.add(key);
      }

      walk(child);
    }
  }

  walk(data);

  // 어쩌다 한 군데 비어 있는 건 정상이므로, 나오는 자리마다 전부 비어 있을 때만 신고한다.
  const empty = [...emptyOccurrences]
    .filter(([key, count]) => count === occurrences.get(key))
    .map(([key]) => key);

  return {
    emptyKeys: empty.sort(),
    invalidKeys: [...invalid].sort(),
  };
}
