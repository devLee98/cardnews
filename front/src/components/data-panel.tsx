"use client";

import { useState } from "react";
import { ChevronUp } from "lucide-react";

import { DataInspector } from "@/components/data-inspector";
import { Panel } from "@/components/panel";
import type { JsonValue } from "@/lib/json";
import { cn } from "@/lib/utils";

/** 업로드한 공구 데이터를 펼쳐 보여준다. 값은 읽기만 한다. */
export function DataPanel({ data }: { data: JsonValue }) {
  const [open, setOpen] = useState(true);

  return (
    <Panel
      title="공구 데이터"
      hint="올린 파일의 값을 그대로 사용합니다 · 고치려면 JSON을 수정해 다시 올려주세요"
      action={
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          {open ? "접기" : "펼치기"}
          <ChevronUp
            className={cn("size-3.5 transition-transform", !open && "rotate-180")}
          />
        </button>
      }
    >
      {/* 접었을 때 Panel 의 윗여백만 남지 않도록 내용이 없으면 통째로 비운다 */}
      {open ? <DataInspector data={data} /> : null}
    </Panel>
  );
}
