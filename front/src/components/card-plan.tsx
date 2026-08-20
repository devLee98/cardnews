"use client";

import { Loader2, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";

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
    <section className="rounded-xl border border-amber-500/60 bg-card pb-5">
      <div className="flex items-center gap-3 px-5 pt-5">
        <h2 className="text-sm font-semibold">
          AI가 제안한 카드 구성안
          {plan && ` · ${plan.length}단`}
        </h2>
        <span className="ml-auto text-xs text-muted-foreground">
          고치고 싶은 점은 아래 추가 인스트럭션에 적어주세요
        </span>
      </div>

      {loading ? (
        <Notice icon={<Loader2 className="size-5 animate-spin" />}>
          AI가 데이터를 읽고 구성안을 짜고 있습니다
        </Notice>
      ) : error ? (
        <>
          <Notice
            icon={<TriangleAlert className="size-5 text-amber-600" />}
            detail={error}
          >
            구성안을 만들지 못했습니다
          </Notice>
          <div className="flex justify-end px-5 pt-4">
            <Button variant="outline" onClick={onRetry}>
              <RefreshCw />
              다시 시도
            </Button>
          </div>
        </>
      ) : plan ? (
        <>
          <ol className="flex flex-col gap-2.5 px-5 pt-4">
            {plan.map((item, index) => (
              <li
                key={`${index}-${item.section}`}
                className="flex items-center gap-4 rounded-lg border border-dashed px-4 py-3"
              >
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full border text-xs">
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

          <div className="flex justify-end px-5 pt-4">
            <Button variant="ghost" onClick={onRetry}>
              <RefreshCw />
              다시 제안
            </Button>
          </div>
        </>
      ) : (
        <Notice icon={<Sparkles className="size-5 text-muted-foreground" />}>
          공구 데이터를 올리면 카드 구성안을 제안합니다
        </Notice>
      )}
    </section>
  );
}

function Notice({
  icon,
  detail,
  children,
}: {
  icon: React.ReactNode;
  detail?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mx-5 mt-4 flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-10">
      {icon}
      <p className="text-center text-sm text-muted-foreground">{children}</p>
      {detail && (
        <p className="max-w-md text-center text-xs text-muted-foreground/70">
          {detail}
        </p>
      )}
    </div>
  );
}
