"use client";

import { useState } from "react";
import { ChevronUp } from "lucide-react";

import { DataInspector } from "@/components/data-inspector";
import type { Analysis } from "@/lib/analyze-data";
import type { JsonValue } from "@/lib/json";
import { cn } from "@/lib/utils";

/** 분석 결과와 상세 데이터를 한 카드에 묶어서 보여준다. */
export function DataPanel({
  analysis,
  data,
  onChange,
}: {
  analysis: Analysis;
  data: JsonValue;
  onChange: (next: JsonValue) => void;
}) {
  const [showDetail, setShowDetail] = useState(true);

  return (
    <section className="rounded-xl border bg-card">
      <div className="px-5 pt-5">
        <h2 className="text-sm font-semibold">데이터 분석이 완료되었습니다!</h2>
      </div>

      <div className="grid gap-3 px-5 pt-4 sm:grid-cols-2">
        <IssueBox title="값이 비어 있는 Key" keys={analysis.emptyKeys} />
        <IssueBox
          title="형식 오류가 있는 Key"
          keys={analysis.invalidKeys}
          tone="warning"
        />
      </div>

      <div className="mx-5 mt-5 border-t border-dashed" />

      <button
        type="button"
        onClick={() => setShowDetail((prev) => !prev)}
        className="flex w-full items-center gap-2.5 px-5 py-4 text-left"
      >
        <h2 className="text-sm font-semibold">데이터 상세</h2>
        <span className="text-xs text-muted-foreground">
          값을 눌러서 바로 고칠 수 있습니다
        </span>
        <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
          {showDetail ? "접기" : "펼치기"}
          <ChevronUp
            className={cn(
              "size-3.5 transition-transform",
              !showDetail && "rotate-180",
            )}
          />
        </span>
      </button>

      {showDetail && (
        <div className="px-5 pb-5">
          <DataInspector data={data} onChange={onChange} />
        </div>
      )}
    </section>
  );
}

function IssueBox({
  title,
  keys,
  tone = "default",
}: {
  title: string;
  keys: string[];
  tone?: "default" | "warning";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-dashed px-4 py-3",
        tone === "warning" && keys.length > 0 && "border-amber-500/60",
      )}
    >
      <p className="text-xs text-muted-foreground">{title}</p>

      {keys.length > 0 ? (
        <p
          className={cn(
            "mt-1.5 font-mono text-sm break-all",
            tone === "warning" && "text-amber-700 dark:text-amber-500",
          )}
        >
          {keys.join(" · ")}
        </p>
      ) : (
        <p className="mt-1.5 text-sm text-muted-foreground/60">없습니다</p>
      )}
    </div>
  );
}
