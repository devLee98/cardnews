export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type JsonPath = (string | number)[];

/** path 위치의 값만 바꾼 새 객체를 만든다. */
export function updateAtPath(
  root: JsonValue,
  path: JsonPath,
  value: JsonValue,
): JsonValue {
  if (path.length === 0) return value;

  const [head, ...rest] = path;

  if (Array.isArray(root)) {
    const next = [...root];
    next[head as number] = updateAtPath(next[head as number], rest, value);
    return next;
  }

  if (root && typeof root === "object") {
    const record = root as Record<string, JsonValue>;
    return { ...record, [head]: updateAtPath(record[head], rest, value) };
  }

  return value;
}

export function isPrimitive(value: JsonValue) {
  return value === null || typeof value !== "object";
}
