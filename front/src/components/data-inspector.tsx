"use client";

import { useState } from "react";
import { ChevronRight, ImageOff } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  isPrimitive,
  updateAtPath,
  type JsonPath as Path,
  type JsonValue,
} from "@/lib/json";
import { cn } from "@/lib/utils";

/* ────────────────────────────────────────────────
   업로드한 공구 JSON을 사람이 읽을 수 있는 형태로 펼쳐 보여주고,
   값을 그 자리에서 고칠 수 있게 하는 뷰어.

   데이터가 길어서(상품 수십 개 + 리뷰) 한 번에 다 그리면 읽을 수 없기 때문에,
   목록은 한 줄 요약만 보여주고 클릭했을 때만 내용을 펼친다.
   ──────────────────────────────────────────────── */

const IMAGE_PATTERN = /\.(png|jpe?g|webp|gif|avif)(\?|$)/i;

function isImageUrl(value: JsonValue): value is string {
  return (
    typeof value === "string" &&
    /^https?:\/\//.test(value) &&
    (IMAGE_PATTERN.test(value) || /image|img|thumb|photo/i.test(value))
  );
}

function isObjectArray(value: JsonValue): value is Record<string, JsonValue>[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (item) => item !== null && typeof item === "object" && !Array.isArray(item),
    )
  );
}

/** 키 이름을 그대로 쓰되 camelCase / snake_case 는 읽기 좋게 띄운다. */
function humanize(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim();
}

function truncate(text: string, max: number) {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max)}…` : flat;
}

/** 접힌 줄에 보여줄 이름. 이름 역할을 하는 키를 먼저 찾는다. */
const TITLE_KEYS = [
  "name",
  "event_name",
  "product_name",
  "title",
  "nickname",
  "label",
  "caption",
];

function rowTitle(row: Record<string, JsonValue>, index: number) {
  for (const key of TITLE_KEYS) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return truncate(value, 40);
  }

  const fallback = Object.values(row).find(
    (value) => typeof value === "string" && value.trim(),
  );

  return typeof fallback === "string"
    ? truncate(fallback, 40)
    : `항목 ${index + 1}`;
}

/** 접힌 줄 오른쪽에 붙일 보조 정보 (옵션명, 가격, 평점 등) */
const META_KEYS = [
  "option1",
  "base_sale_price",
  "consumer_price",
  "rating",
  "naver_rating",
  "post_date",
  "date",
];

function rowMeta(row: Record<string, JsonValue>) {
  const parts: string[] = [];

  for (const key of META_KEYS) {
    const value = row[key];
    if (value === undefined || value === null || value === "") continue;

    parts.push(typeof value === "number" ? value.toLocaleString() : String(value));
    if (parts.length === 2) break;
  }

  return parts.join(" · ");
}

/** 접힌 블록 오른쪽에 붙일 규모 표시 */
function describe(value: JsonValue) {
  if (Array.isArray(value)) return `${value.length}개`;
  if (value && typeof value === "object") {
    return `${Object.keys(value).length}개 항목`;
  }
  return undefined;
}

export function DataInspector({
  data,
  onChange,
}: {
  data: JsonValue;
  onChange: (next: JsonValue) => void;
}) {
  function setValue(path: Path, value: JsonValue) {
    onChange(updateAtPath(data, path, value));
  }

  if (isPrimitive(data)) {
    return <ValueEditor value={data} path={[]} onCommit={setValue} />;
  }

  if (Array.isArray(data)) {
    return <NodeBody value={data} path={[]} onCommit={setValue} />;
  }

  const entries = Object.entries(data as Record<string, JsonValue>);
  const primitives = entries.filter(([, value]) => isPrimitive(value));
  const groups = entries.filter(([, value]) => !isPrimitive(value));

  return (
    <div className="flex flex-col gap-2">
      {primitives.length > 0 && (
        <Block
          title="기본 정보"
          meta={`${primitives.length}개 항목`}
          defaultOpen
        >
          <dl className="divide-y">
            {primitives.map(([key, value]) => (
              <FieldRow
                key={key}
                label={key}
                value={value}
                path={[key]}
                onCommit={setValue}
              />
            ))}
          </dl>
        </Block>
      )}

      {/* 최상위 그룹만 펼친 채로 시작하고, 그 안쪽은 전부 접어 둔다 */}
      {groups.map(([key, value]) => (
        <Block
          key={key}
          title={humanize(key)}
          meta={describe(value)}
          defaultOpen
        >
          <NodeBody value={value} path={[key]} onCommit={setValue} />
        </Block>
      ))}
    </div>
  );
}

function Block({
  title,
  meta,
  defaultOpen = false,
  children,
}: {
  title: string;
  meta?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="overflow-hidden rounded-md border bg-card">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 bg-muted/40 px-3 py-2 text-left hover:bg-muted"
      >
        <ChevronRight
          className={cn(
            "size-3.5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
        />
        <span className="truncate text-sm">{title}</span>
        {meta && (
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {meta}
          </span>
        )}
      </button>

      {open && children}
    </div>
  );
}

/** 객체/배열/원시값을 각각의 모양에 맞게 그린다. */
function NodeBody({
  value,
  path,
  onCommit,
}: {
  value: JsonValue;
  path: Path;
  onCommit: (path: Path, value: JsonValue) => void;
}) {
  // 같은 모양의 객체 배열 → 한 줄 요약 목록. 클릭해야 내용이 열린다.
  if (isObjectArray(value)) {
    const columns = Array.from(
      new Set(value.flatMap((row) => Object.keys(row))),
    );

    return (
      <div className="flex flex-col gap-1.5 p-2">
        {value.map((row, index) => (
          <Block
            key={index}
            title={`${index + 1}. ${rowTitle(row, index)}`}
            meta={rowMeta(row)}
          >
            <dl className="divide-y">
              {columns.map((column) => (
                <FieldRow
                  key={column}
                  label={column}
                  value={row[column] ?? null}
                  path={[...path, index, column]}
                  onCommit={onCommit}
                />
              ))}
            </dl>
          </Block>
        ))}
      </div>
    );
  }

  // 원시값 배열 → 번호 붙인 목록
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <EmptyNote>항목이 없습니다</EmptyNote>;
    }

    return (
      <dl className="divide-y">
        {value.map((item, index) => (
          <FieldRow
            key={index}
            label={`${index + 1}`}
            value={item}
            path={[...path, index]}
            onCommit={onCommit}
          />
        ))}
      </dl>
    );
  }

  // 중첩 객체 → 키/값 행
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, JsonValue>);

    if (entries.length === 0) {
      return <EmptyNote>내용이 없습니다</EmptyNote>;
    }

    return (
      <dl className="divide-y">
        {entries.map(([key, child]) => (
          <FieldRow
            key={key}
            label={key}
            value={child}
            path={[...path, key]}
            onCommit={onCommit}
          />
        ))}
      </dl>
    );
  }

  return <ValueEditor value={value} path={path} onCommit={onCommit} />;
}

function FieldRow({
  label,
  value,
  path,
  onCommit,
}: {
  label: string;
  value: JsonValue;
  path: Path;
  onCommit: (path: Path, value: JsonValue) => void;
}) {
  // 중첩 구조는 접힌 블록으로 두고, 눌렀을 때만 펼친다
  if (!isPrimitive(value)) {
    return (
      <div className="p-2">
        <Block title={humanize(label)} meta={describe(value)}>
          <NodeBody value={value} path={path} onCommit={onCommit} />
        </Block>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[minmax(80px,150px)_1fr] items-start gap-3 px-3 py-2">
      <dt className="pt-2 text-xs break-words text-muted-foreground">
        {humanize(label)}
      </dt>
      <dd>
        <ValueEditor value={value} path={path} onCommit={onCommit} />
      </dd>
    </div>
  );
}

function ValueEditor({
  value,
  path,
  onCommit,
}: {
  value: JsonValue;
  path: Path;
  onCommit: (path: Path, value: JsonValue) => void;
}) {
  if (typeof value === "boolean") {
    return (
      <button
        type="button"
        onClick={() => onCommit(path, !value)}
        className={cn(
          "rounded-md border px-2.5 py-1 text-xs transition-colors",
          value
            ? "border-primary/30 bg-primary/10 text-foreground"
            : "text-muted-foreground",
        )}
      >
        {value ? "예" : "아니오"}
      </button>
    );
  }

  if (isImageUrl(value)) {
    return <ImageField value={value} path={path} onCommit={onCommit} />;
  }

  const text = value === null ? "" : String(value);
  const isNumber = typeof value === "number";

  // 값의 원래 타입이 숫자면 숫자로 되돌려 저장한다
  function commit(next: string) {
    if (isNumber) {
      const parsed = Number(next);
      onCommit(path, next.trim() !== "" && !Number.isNaN(parsed) ? parsed : next);
      return;
    }

    onCommit(path, next);
  }

  if (text.length > 60) {
    return (
      <Textarea
        value={text}
        onChange={(event) => commit(event.target.value)}
        className="min-h-[72px] resize-y text-sm"
      />
    );
  }

  return (
    <Input
      value={text}
      inputMode={isNumber ? "numeric" : undefined}
      onChange={(event) => commit(event.target.value)}
      placeholder={value === null ? "비어 있음" : undefined}
      className="h-8 text-sm"
    />
  );
}

function ImageField({
  value,
  path,
  onCommit,
}: {
  value: string;
  path: Path;
  onCommit: (path: Path, value: JsonValue) => void;
}) {
  const [broken, setBroken] = useState(false);

  return (
    <div className="flex items-start gap-2">
      <div className="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-md border bg-muted">
        {broken ? (
          <ImageOff className="size-4 text-muted-foreground" />
        ) : (
          /* 외부 이미지라 next/image 대신 img 를 쓴다 */
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={value}
            alt=""
            className="size-full object-cover"
            onError={() => setBroken(true)}
          />
        )}
      </div>
      <Input
        value={value}
        onChange={(event) => {
          setBroken(false);
          onCommit(path, event.target.value);
        }}
        className="h-8 text-sm"
      />
    </div>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="px-3 py-4 text-center text-xs text-muted-foreground">
      {children}
    </p>
  );
}
