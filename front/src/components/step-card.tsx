"use client";

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

/* 좌측 메뉴의 단계 항목.
   진행 상태만 보여주고, 실제 내용은 우측 워크스페이스에 쌓인다.

   회색 바탕 위에 흰 카드가 얹히는 구조라 끝난 단계는 테두리를 두르지 않는다.
   지금 할 단계만 옅은 파랑 바탕과 파란 테두리로 한 장 띄워 둔다. */

export type StepState = "idle" | "active" | "done";

export function StepCard({
  num,
  title,
  state,
  subtitle,
  action,
  onAction,
  onClick,
}: {
  num: number;
  title: string;
  state: StepState;
  subtitle?: string;
  action?: string;
  onAction?: () => void;
  onClick?: () => void;
}) {
  const clickable = Boolean(onClick) && state !== "idle";

  return (
    <div
      onClick={clickable ? onClick : undefined}
      className={cn(
        "rounded-xl border border-transparent px-4 py-3.5 transition-colors",
        state === "done" && "bg-card",
        state === "active" && "border-sidebar-border bg-sidebar-accent",
        state === "idle" && "bg-card/55 text-muted-foreground",
        clickable && "cursor-pointer hover:border-primary/40",
      )}
    >
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "flex size-[23px] shrink-0 items-center justify-center rounded-full border-[1.5px] text-xs font-bold",
            // 끝난 단계는 브랜드 색으로 채우고, 지금 할 단계는 테두리만 준다.
            // 채운 쪽이 더 눈에 띄어서 어디까지 왔는지가 먼저 읽힌다.
            state === "done" &&
              "border-primary bg-primary text-primary-foreground",
            state === "active" && "border-primary bg-background text-primary",
            state === "idle" && "border-dashed border-muted-foreground/40",
          )}
        >
          {state === "done" ? <Check className="size-3.5" /> : num}
        </span>

        <p
          className={cn(
            "min-w-0 flex-1 truncate text-[15px] font-bold tracking-[-0.3px]",
            state === "idle" && "font-medium",
          )}
        >
          {title}
        </p>
      </div>

      {/* 아이콘(23px) + 간격(10px) 만큼 들여써 제목 첫 글자에 맞춘다 */}
      {(subtitle || action) && (
        <div className="mt-2.5 ml-[33px] text-[13px] leading-[1.45] tracking-[-0.2px] text-muted-foreground">
          {subtitle && <p className="truncate">{subtitle}</p>}

          {action && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onAction?.();
              }}
              className="mt-1 underline underline-offset-2 hover:text-foreground"
            >
              {action}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
