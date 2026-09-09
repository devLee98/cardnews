"use client";

import { useState } from "react";
import { ChevronUp } from "lucide-react";

import { DataInspector } from "@/components/data-inspector";
import type { JsonValue } from "@/lib/json";
import { cn } from "@/lib/utils";

/** 업로드한 공구 데이터를 펼쳐 보여준다. 값은 읽기만 한다. */
export function DataPanel({ data }: { data: JsonValue }) {
  const [open, setOpen] = useState(true);

  return (
    <section className="rounded-xl border bg-card">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2.5 px-5 py-4 text-left"
      >
        <h2 className="text-sm font-semibold">공구 데이터</h2>
        <span className="text-xs text-muted-foreground">
          올린 파일의 값을 그대로 사용합니다 · 고치려면 JSON을 수정해 다시
          올려주세요
        </span>
        <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
          {open ? "접기" : "펼치기"}
          <ChevronUp
            className={cn("size-3.5 transition-transform", !open && "rotate-180")}
          />
        </span>
      </button>

      {open && (
        <div className="px-5 pb-5">
          <DataInspector data={data} />
        </div>
      )}
    </section>
  );
}
