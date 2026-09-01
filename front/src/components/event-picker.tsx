"use client";

import { Check, Package } from "lucide-react";

import type { EventOption } from "@/lib/events";
import { cn } from "@/lib/utils";

/* 업로드한 JSON 에 공구가 여러 건 들어 있을 때 하나를 고르는 곳.

   카드뉴스는 공구 한 건 기준이라 반드시 하나만 고른다.
   고르는 순간 구성안과 움직이는 상세컷 찾기가 나란히 시작된다.
   공구가 한 건뿐이면 고를 것이 없으므로 이 화면은 나타나지 않는다. */

export function EventPicker({
  events,
  selected,
  onSelect,
}: {
  events: EventOption[];
  selected: number | null;
  onSelect: (index: number) => void;
}) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-center gap-3 px-5 pt-5">
        <h2 className="text-sm font-semibold">공구 선택</h2>
        <span className="text-xs text-muted-foreground">
          공구 {events.length}건이 들어 있습니다 · 카드뉴스를 만들 공구 하나를
          골라주세요
        </span>
      </div>

      {/* 공구명이 길어서 두 열로 두면 잘린다. 한 줄에 하나씩 편다. */}
      <div className="flex flex-col gap-2.5 px-5 pt-4 pb-5">
        {events.map((event) => {
          const picked = event.index === selected;

          return (
            <button
              key={event.index}
              type="button"
              onClick={() => onSelect(event.index)}
              className={cn(
                "flex items-start gap-2.5 rounded-lg border-2 px-3.5 py-3 text-left transition",
                picked
                  ? "border-primary bg-primary/5"
                  : "border-muted hover:border-muted-foreground/40",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border transition",
                  picked
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-muted-foreground/40",
                )}
              >
                {picked && <Check className="size-3" />}
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {event.name}
                </span>
                <span className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                  <Package className="size-3" />
                  상품 {event.productCount}종
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {selected !== null && (
        <p className="border-t px-5 py-3 text-xs text-muted-foreground">
          다른 공구를 고르면 지금까지 만든 구성안과 카드는 모두 새로
          만들어집니다.
        </p>
      )}
    </section>
  );
}
