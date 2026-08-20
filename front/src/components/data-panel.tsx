"use client";

import { useState } from "react";
import { ChevronUp } from "lucide-react";

import { DataInspector } from "@/components/data-inspector";
import type { JsonValue } from "@/lib/json";
import { cn } from "@/lib/utils";

/** 업로드한 공구 데이터를 펼쳐 보여주고 값을 고칠 수 있게 한다. */
export function DataPanel({
  data,
  onChange,
}: {
  data: JsonValue;
  onChange: (next: JsonValue) => void;
}) {
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
          값을 눌러서 바로 고칠 수 있습니다
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
          <DataInspector data={data} onChange={onChange} />
        </div>
      )}
    </section>
  );
}
