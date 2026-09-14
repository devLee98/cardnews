"use client";

import { Loader2, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";

import { Panel, PanelNotice } from "@/components/panel";
import { Button } from "@/components/ui/button";
import type { CardPlanItem } from "@/lib/api";

/* AI가 제안한 카드 구성안.
   여기서는 확인만 하고, 내용 수정은 다음 단계에서 한다. */

export function CardPlan({
  plan,
  loading,
  error,
  onRetry,
}: {
  plan: CardPlanItem[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <Panel
      title={`AI가 제안한 카드 구성안${plan ? ` · ${plan.length}단` : ""}`}
      hint="고치고 싶은 점은 아래 추가 인스트럭션에 적어주세요"
      action={
        plan && !loading && !error ? (
          <Button variant="ghost" size="sm" onClick={onRetry}>
            <RefreshCw />
            다시 제안
          </Button>
        ) : undefined
      }
    >
      {loading ? (
        <PanelNotice icon={<Loader2 className="size-5 animate-spin text-primary" />}>
          AI가 데이터를 읽고 구성안을 짜고 있습니다
        </PanelNotice>
      ) : error ? (
        <>
          <PanelNotice
            icon={<TriangleAlert className="size-5 text-amber-600" />}
            detail={error}
          >
            구성안을 만들지 못했습니다
          </PanelNotice>
          <div className="mt-4 flex justify-end">
            <Button variant="outline" onClick={onRetry}>
              <RefreshCw />
              다시 시도
            </Button>
          </div>
        </>
      ) : plan ? (
        <ol className="flex flex-col gap-2.5">
          {plan.map((item, index) => (
            <li
              key={`${index}-${item.section}`}
              className="flex items-center gap-4 rounded-xl border border-dashed px-4 py-3"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-accent text-xs font-medium text-primary">
                {index + 1}
              </span>
              <span className="w-24 shrink-0 text-sm font-medium">
                {item.section}
              </span>
              <span className="text-sm text-muted-foreground">
                {item.description}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <PanelNotice icon={<Sparkles className="size-5 text-muted-foreground" />}>
          공구 데이터를 올리면 카드 구성안을 제안합니다
        </PanelNotice>
      )}
    </Panel>
  );
}
