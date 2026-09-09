export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export function isPrimitive(value: JsonValue) {
  return value === null || typeof value !== "object";
}
