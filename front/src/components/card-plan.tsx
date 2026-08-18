"use client";

import { Check, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

/* AI가 제안한 카드 구성안.
   여기서는 확인만 하고, 내용 수정은 다음 단계에서 한다. */

export type CardPlanItem = {
  /** 카드 역할 이름 (인트로, 문제 제기 …) */
  section: string;
  /** 이 카드가 참조하는 JSON Key */
  sourceKeys: string[];
  /** 이 카드가 무엇을 하는 카드인지 */
  description: string;
};

export function CardPlan({
  plan,
  confirmed,
  onConfirm,
}: {
  plan: CardPlanItem[] | null;
  confirmed: boolean;
  onConfirm: () => void;
}) {
  return (
    <section className="rounded-xl border border-amber-500/60 bg-card">
      <div className="flex items-center gap-3 px-5 pt-5">
        <h2 className="text-sm font-semibold">
          AI가 제안한 카드 구성안
          {plan && ` · ${plan.length}단`}
        </h2>
        <span className="ml-auto text-xs text-muted-foreground">
          확인만 가능 · 수정은 다음 단계에서
        </span>
      </div>

      {plan ? (
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
                <span className="w-20 shrink-0 text-sm font-medium">
                  {item.section}
                </span>
                <span className="w-44 shrink-0 font-mono text-xs break-all text-muted-foreground">
                  {item.sourceKeys.join(" · ")}
                </span>
                <span className="text-xs text-muted-foreground">
                  {item.description}
                </span>
              </li>
            ))}
          </ol>

          <div className="flex justify-end px-5 pt-4">
            <Button
              variant="outline"
              disabled={confirmed}
              onClick={onConfirm}
              className="border-amber-500/60 text-amber-700 hover:bg-amber-50 dark:text-amber-500 dark:hover:bg-amber-950/20"
            >
              {confirmed ? <Check /> : null}
              {confirmed ? "확인함" : "확인"}
            </Button>
          </div>
        </>
      ) : (
        <div className="mx-5 mt-4 flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-10">
          <Sparkles className="size-5 text-muted-foreground" />
          <p className="text-center text-sm text-muted-foreground">
            AI가 데이터를 읽고 카드 구성안을 제안합니다
          </p>
          <p className="text-xs text-muted-foreground/70">
            아직 AI를 연결하지 않았습니다
          </p>
        </div>
      )}

      <p className="px-5 py-4 text-xs text-muted-foreground">
        확인하면 추가 인스트럭션 단계가 열립니다
      </p>
    </section>
  );
}
