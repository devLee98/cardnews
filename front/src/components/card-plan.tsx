"use client";

import { Loader2, RefreshCw, Sparkles, TriangleAlert, X } from "lucide-react";

import { Panel, PanelNotice } from "@/components/panel";
import { Button } from "@/components/ui/button";
import type { CardPlanItem } from "@/lib/api";
import { cn } from "@/lib/utils";

/* AI가 제안한 카드 구성안.

   카드마다 그 장만 다시 제안받거나 뺄 수 있다. 전체를 다시 제안받는 버튼은
   일부러 두지 않는다. 마음에 들던 카드까지 같이 바뀌어서 한 장씩 고친 것이
   날아간다. 문구 수준의 수정은 다음 단계 추가 인스트럭션에서 한다.

   한 장을 다시 제안받는 동안에는 다른 장의 버튼도 잠근다. 그 사이에 한 장을
   빼면 자리(index)가 밀려서 돌아온 결과가 엉뚱한 카드에 들어간다. */

/** 명세상 최소 장수. 서버 card_spec.MIN_CARDS 와 같은 값이어야 한다. */
const MIN_CARDS = 6;

export function CardPlan({
  plan,
  loading,
  error,
  busyIndex,
  itemError,
  onRetry,
  onRefreshItem,
  onRemoveItem,
}: {
  plan: CardPlanItem[] | null;
  loading: boolean;
  error: string | null;
  /** 지금 다시 제안받는 중인 카드 자리. 없으면 null */
  busyIndex: number | null;
  /** 한 장 다시 제안이 실패했을 때의 이유 */
  itemError: string | null;
  /** 구성안 생성 자체가 실패했을 때 처음부터 다시 받는다 */
  onRetry: () => void;
  onRefreshItem: (index: number) => void;
  onRemoveItem: (index: number) => void;
}) {
  const busy = busyIndex !== null;

  return (
    <Panel
      title={`AI가 제안한 카드 구성안${plan ? ` · ${plan.length}단` : ""}`}
      hint="카드마다 다시 제안받거나 뺄 수 있습니다 · 세부 수정은 아래 추가 인스트럭션에"
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
        <>
          <ol className="flex flex-col gap-2.5">
            {plan.map((item, index) => {
              const refreshing = busyIndex === index;

              return (
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
                  <span
                    className={cn(
                      "min-w-0 flex-1 text-sm text-muted-foreground",
                      refreshing && "animate-pulse",
                    )}
                  >
                    {refreshing
                      ? "AI가 이 카드를 다시 제안하는 중…"
                      : item.description}
                  </span>

                  <span className="flex shrink-0 items-center gap-0.5">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-muted-foreground"
                      title="이 카드만 다시 제안"
                      aria-label={`${item.section} 카드만 다시 제안`}
                      disabled={busy}
                      onClick={() => onRefreshItem(index)}
                    >
                      {refreshing ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <RefreshCw />
                      )}
                    </Button>
                    {/* 마지막 한 장은 못 뺀다. 빈 구성안으로는 카드를 만들 수 없다. */}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-muted-foreground hover:text-destructive"
                      title="이 카드 빼기"
                      aria-label={`${item.section} 카드 빼기`}
                      disabled={busy || plan.length <= 1}
                      onClick={() => onRemoveItem(index)}
                    >
                      <X />
                    </Button>
                  </span>
                </li>
              );
            })}
          </ol>

          {itemError && (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-destructive">
              <TriangleAlert className="size-3.5" />
              {itemError}
            </p>
          )}

          {plan.length < MIN_CARDS && (
            <p className="mt-3 text-xs text-muted-foreground">
              카드뉴스는 {MIN_CARDS}장 이상을 권장합니다 · 지금 {plan.length}장
            </p>
          )}
        </>
      ) : (
        <PanelNotice icon={<Sparkles className="size-5 text-muted-foreground" />}>
          공구 데이터를 올리면 카드 구성안을 제안합니다
        </PanelNotice>
      )}
    </Panel>
  );
}
