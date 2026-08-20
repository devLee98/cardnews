"use client";

import { Check, Clapperboard, Loader2, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CardAsset } from "@/lib/api";
import { cn } from "@/lib/utils";

/* 공구 데이터에 들어 있는 움직이는 상세컷을 골라 두는 곳.

   고른 것만 카드에 쓰인다. 어느 카드에 넣을지는 AI 가 정한다.
   움직이는 카드는 문구가 이미지 아래에 붙어서 다른 카드와 결이 조금 다르다.
   그래서 기본은 아무것도 고르지 않은 상태로 둔다. */

/** 한 번에 고를 수 있는 최대 개수. 서버도 같은 값으로 막는다. */
const MAX_PICK = 3;

export function GifPicker({
  gifs,
  selected,
  onChange,
  loading,
  error,
}: {
  gifs: CardAsset[];
  selected: string[];
  onChange: (urls: string[]) => void;
  loading: boolean;
  error: string | null;
}) {
  // 찾는 데 1분 남짓 걸린다. 그동안 아무것도 안 보이면 없는 줄 알게 되므로
  // 자리를 잡아 두고 진행 중이라는 것을 알린다.
  if (loading) {
    return (
      <section className="rounded-xl border bg-card">
        <div className="flex items-center gap-3 px-5 pt-5">
          <h2 className="text-sm font-semibold">움직이는 상세컷</h2>
          <span className="text-xs text-muted-foreground">
            공구 데이터에서 찾는 중입니다 · 1분 정도 걸립니다
          </span>
        </div>

        <div className="flex items-center justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-xl border bg-card">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <TriangleAlert className="size-4 text-amber-600" />
          <h2 className="text-sm font-semibold">움직이는 상세컷</h2>
          <span className="text-xs text-muted-foreground">{error}</span>
        </div>
      </section>
    );
  }

  if (gifs.length === 0) return null;

  const full = selected.length >= MAX_PICK;

  function toggle(url: string) {
    if (selected.includes(url)) {
      onChange(selected.filter((item) => item !== url));
      return;
    }

    if (selected.length >= MAX_PICK) return;

    onChange([...selected, url]);
  }

  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-center gap-3 px-5 pt-5">
        <h2 className="text-sm font-semibold">움직이는 상세컷</h2>
        <span className="text-xs text-muted-foreground">
          고른 것은 반드시 쓰입니다 · 최대 {MAX_PICK}개 · 어느 카드에 넣을지는 AI가
          정합니다
        </span>

        {selected.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto h-7 text-xs"
            onClick={() => onChange([])}
          >
            선택 해제
          </Button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 px-5 pt-4 sm:grid-cols-4 xl:grid-cols-5">
        {gifs.map((gif) => {
          const picked = selected.includes(gif.url);
          const blocked = full && !picked;

          return (
            <button
              key={gif.url}
              type="button"
              onClick={() => toggle(gif.url)}
              disabled={blocked}
              title={blocked ? `최대 ${MAX_PICK}개까지 고를 수 있습니다` : undefined}
              className={cn(
                "group relative overflow-hidden rounded-lg border-2 text-left transition",
                picked
                  ? "border-primary"
                  : "border-transparent hover:border-muted-foreground/30",
                blocked && "cursor-not-allowed opacity-40",
              )}
            >
              <div className="relative aspect-square bg-white">
                {/* 외부 주소이고 움직여야 하므로 next/image 대신 img 를 쓴다 */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={gif.url}
                  alt={gif.scene}
                  className={cn(
                    "size-full object-contain transition",
                    !picked && "opacity-70 group-hover:opacity-100",
                  )}
                />

                <span
                  className={cn(
                    "absolute top-1.5 right-1.5 flex size-5 items-center justify-center rounded-full border transition",
                    picked
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-white/70 bg-black/25",
                  )}
                >
                  {picked && <Check className="size-3" />}
                </span>

                <Badge
                  variant="secondary"
                  className="absolute bottom-1.5 left-1.5 gap-1 text-[10px]"
                >
                  <Clapperboard className="size-3" />
                  움짤
                </Badge>
              </div>

              <p className="line-clamp-2 px-1 py-1.5 text-[11px] leading-snug text-muted-foreground">
                {gif.scene}
              </p>
            </button>
          );
        })}
      </div>

      <p className="px-5 py-4 text-xs text-muted-foreground">
        {selected.length === 0
          ? "고르지 않으면 모든 카드를 AI가 새로 만듭니다."
          : `${selected.length}/${MAX_PICK}개 선택 · 첫 장과 마지막 장에는 들어가지 않습니다.`}
      </p>
    </section>
  );
}
