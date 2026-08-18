"use client";

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

/* 좌측 메뉴의 단계 항목.
   진행 상태만 보여주고, 실제 내용은 우측 영역에 쌓인다. */

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
        "rounded-xl border px-4 py-3.5 transition-colors",
        state === "done" && "border-solid bg-card",
        state === "active" &&
          "border-amber-500/60 bg-amber-50 dark:bg-amber-950/20",
        state === "idle" && "border-dashed text-muted-foreground",
        clickable && "cursor-pointer hover:border-foreground/30",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border text-xs",
            state === "done" && "border-foreground bg-foreground text-background",
            state === "active" && "border-amber-600 text-amber-700 dark:text-amber-500",
            state === "idle" && "border-dashed",
          )}
        >
          {state === "done" ? <Check className="size-3.5" /> : num}
        </span>

        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-sm font-medium",
              state === "idle" && "font-normal",
            )}
          >
            {title}
          </p>

          {subtitle && (
            <p className="mt-1 truncate text-xs text-muted-foreground">
              {subtitle}
            </p>
          )}

          {action && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onAction?.();
              }}
              className="mt-1.5 text-xs underline underline-offset-2 hover:text-foreground"
            >
              {action}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
