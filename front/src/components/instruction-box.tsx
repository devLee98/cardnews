"use client";

import { useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";

import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/* 관리자가 문구 생성에 덧붙일 지시를 적는 곳.

   이 지시는 ③번 문구·디자인 생성에만 들어간다.
   구성안(①)은 이 칸을 채우기 전에 이미 확정되어 있어서,
   "카드를 빼달라" 같은 요구는 반영될 수 없다.
   적기 전에 그 경계를 알 수 있도록 도움말을 접어서 붙여 둔다.
   서버(prompts.py) 도 같은 경계를 프롬프트에 못박아 두고 있다. */

/** 서버(prompts.MAX_INSTRUCTION) 와 같은 값으로 맞춘다. */
export const MAX_INSTRUCTION = 500;

/* 예시는 ③번이 언제나 지킬 수 있는 것만 넣는다.

   "가격보다 성분을 강조" 는 뺐다. 가격 카드는 구성안에 이미 확정되어 있고,
   구성안이 성분을 사용 데이터로 지목하지 않았으면 성분 값이 프롬프트에
   들어가지도 않는다.

   "사용 장면 사진 위주로" 도 뺐다. 사진 카탈로그는 매번 무작위 8장만
   보여주므로, 그 안에 없는 종류는 고를 수 없다.

   되다 말다 하는 예시는 없느니만 못하다. 왜 안 됐는지 알 방법이 없다. */
const ALLOWED: [string, string][] = [
  ["말투·톤", "“존댓말로” “차분한 톤으로”"],
  ["문장 길이·리듬", "“문장을 더 짧게 끊어주세요”"],
  ["표현 금지", "“‘초특가’라는 말은 쓰지 마세요”"],
  ["크게 보일 값", "“할인율 말고 마감일을 크게”"],
  ["카드 밝기·문구 위치", "“밝은 느낌으로” “글자를 위쪽에”"],
  ["배경·분위기", "“바다가 보이면 좋겠어요” “가을 느낌으로”"],
];

const BLOCKED: [string, string][] = [
  ["카드 추가·삭제·순서", "구성안은 위 단계에서 이미 확정됩니다"],
  ["카드에 쓸 데이터 바꾸기", "구성안이 지목한 값만 문구에 쓰입니다"],
  ["22자를 넘는 제목", "글자 수는 고정입니다"],
  ["데이터에 없는 내용", "없는 사실은 쓰지 않습니다"],
  ["사람이 나오는 장면", "얼굴·아이는 안전 필터에 막혀 카드가 실패합니다"],
];

export function InstructionBox({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-center gap-3 px-5 pt-5">
        <h2 className="text-sm font-semibold">추가 인스트럭션</h2>
        <span className="ml-auto text-xs text-muted-foreground">선택 입력</span>
      </div>

      <div className="px-5 pt-4 pb-4">
        <Textarea
          value={value}
          maxLength={MAX_INSTRUCTION}
          onChange={(event) => onChange(event.target.value)}
          placeholder="예) 존댓말로, 문장을 더 짧게 끊어주세요"
          className="min-h-[100px] resize-none"
        />
        <p className="mt-1.5 text-right text-xs text-muted-foreground">
          {value.length} / {MAX_INSTRUCTION}
        </p>
      </div>

      {/* 평소에는 접어 둔다. 적을 때 막히는 사람만 펼쳐 보면 된다. */}
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-1.5 border-t px-5 py-3 text-left text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronDown
          className={cn("size-3.5 transition-transform", open && "rotate-180")}
        />
        무엇을 적을 수 있나요?
      </button>

      {open && (
        <div className="grid gap-5 border-t px-5 py-4 sm:grid-cols-2">
          <div>
            <p className="flex items-center gap-1.5 text-xs font-medium">
              <Check className="size-3.5 text-emerald-600" />
              이런 건 반영됩니다
            </p>

            <dl className="mt-2.5 space-y-2">
              {ALLOWED.map(([label, example]) => (
                <div key={label}>
                  <dt className="text-xs font-medium">{label}</dt>
                  <dd className="text-xs text-muted-foreground">{example}</dd>
                </div>
              ))}
            </dl>

            <p className="mt-3 text-xs text-muted-foreground">
              문구를 <span className="font-medium">어떻게 쓸지</span>와 카드의{" "}
              <span className="font-medium">보이는 방식</span>을 바꿀 수
              있습니다. <span className="font-medium">무엇을 쓸지</span>는 위
              구성안에서 이미 정해집니다.
            </p>
          </div>

          <div>
            <p className="flex items-center gap-1.5 text-xs font-medium">
              <X className="size-3.5 text-destructive" />
              이런 건 반영되지 않습니다
            </p>

            <dl className="mt-2.5 space-y-2">
              {BLOCKED.map(([label, reason]) => (
                <div key={label}>
                  <dt className="text-xs font-medium">{label}</dt>
                  <dd className="text-xs text-muted-foreground">{reason}</dd>
                </div>
              ))}
            </dl>

            <p className="mt-3 text-xs text-muted-foreground">
              적어도 무시될 뿐 오류가 나지는 않습니다. 나머지 내용은 그대로
              반영됩니다.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
