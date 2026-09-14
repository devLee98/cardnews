"use client";

import { useState } from "react";
import { ChevronRight, ImageOff } from "lucide-react";

import { isPrimitive, type JsonValue } from "@/lib/json";
import { cn } from "@/lib/utils";

/* ────────────────────────────────────────────────
   업로드한 공구 JSON을 사람이 읽을 수 있는 형태로 펼쳐 보여주는 뷰어.

   값은 보여주기만 하고 고치지 못한다. 카드에 들어가는 내용은 올린 파일과
   언제나 같아야 하기 때문이다. 화면에서 고칠 수 있으면 원본 파일과 화면이
   어긋나고, 만들어진 카드가 어느 쪽을 따른 것인지 알 수 없게 된다.
   잘못된 값은 원본 JSON을 고쳐 다시 올린다.

   데이터가 길어서(상품 수십 개 + 리뷰) 한 번에 다 그리면 읽을 수 없기 때문에,
   목록은 한 줄 요약만 보여주고 클릭했을 때만 내용을 펼친다.
   ──────────────────────────────────────────────── */

/* 맨 바깥에서 감출 키.

   meta 는 공구가 아니라 파일에 대한 설명이다. 생성 시각, 원본 파일명, sha256 해시,
   내부 공지, 전체 집계 같은 것들이라 카드를 만드는 사람이 읽을 일이 없다.
   패널 맨 위를 18줄이나 차지하면서 정작 봐야 할 공구 정보를 아래로 밀어낸다.

   숫자도 맞지 않는다. 화면은 공구가 여러 건인 파일에서 하나만 골라 쓰는데
   meta 의 집계는 파일 전체 기준이라, 상품 16개짜리 공구를 보면서
   product count 154 를 읽게 된다.

   안쪽에 있는 events[].meta 같은 것은 공구에 딸린 값일 수 있으므로 건드리지 않는다. */
const HIDDEN_ROOT_KEYS = ["meta"];

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

export function DataInspector({ data }: { data: JsonValue }) {
  if (isPrimitive(data)) {
    return <ValueView value={data} />;
  }

  if (Array.isArray(data)) {
    return <NodeBody value={data} />;
  }

  const entries = Object.entries(data as Record<string, JsonValue>).filter(
    ([key]) => !HIDDEN_ROOT_KEYS.includes(key),
  );
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
              <FieldRow key={key} label={key} value={value} />
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
          <NodeBody value={value} />
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
function NodeBody({ value }: { value: JsonValue }) {
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
          <FieldRow key={index} label={`${index + 1}`} value={item} />
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
          <FieldRow key={key} label={key} value={child} />
        ))}
      </dl>
    );
  }

  return <ValueView value={value} />;
}

function FieldRow({ label, value }: { label: string; value: JsonValue }) {
  // 중첩 구조는 접힌 블록으로 두고, 눌렀을 때만 펼친다
  if (!isPrimitive(value)) {
    return (
      <div className="p-2">
        <Block title={humanize(label)} meta={describe(value)}>
          <NodeBody value={value} />
        </Block>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[minmax(80px,150px)_1fr] items-start gap-3 px-3 py-2">
      <dt className="text-xs break-words text-muted-foreground">
        {humanize(label)}
      </dt>
      <dd className="min-w-0">
        <ValueView value={value} />
      </dd>
    </div>
  );
}

function ValueView({ value }: { value: JsonValue }) {
  if (value === null || value === "") {
    return <p className="text-sm text-muted-foreground/60">비어 있음</p>;
  }

  if (typeof value === "boolean") {
    return (
      <span
        className={cn(
          "inline-block rounded-md border px-2.5 py-1 text-xs",
          value
            ? "border-primary/30 bg-primary/10 text-foreground"
            : "text-muted-foreground",
        )}
      >
        {value ? "예" : "아니오"}
      </span>
    );
  }

  if (isImageUrl(value)) {
    return <ImageView value={value} />;
  }

  // 숫자는 자릿수를 끊어 읽기 쉽게 한다 (가격, 리뷰 수가 대부분이다)
  const text = typeof value === "number" ? value.toLocaleString() : String(value);

  return (
    <p className="text-sm break-words whitespace-pre-wrap">{text}</p>
  );
}

function ImageView({ value }: { value: string }) {
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
      <p className="min-w-0 text-sm break-all text-muted-foreground">{value}</p>
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
