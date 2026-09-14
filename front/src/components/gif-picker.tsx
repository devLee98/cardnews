"use client";

import { Check, Clapperboard, Loader2, TriangleAlert } from "lucide-react";

import { Panel } from "@/components/panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CardAsset } from "@/lib/api";
import { cn } from "@/lib/utils";

/* 공구 데이터에 들어 있는 움직이는 상세컷을 골라 두는 곳.

   고른 것만 카드에 쓰인다. 어느 카드에 넣을지는 AI 가 정한다.
   움직이는 카드는 문구가 이미지 아래에 붙어서 다른 카드와 결이 조금 다르다.
   그래서 기본은 아무것도 고르지 않은 상태로 둔다.

   고를 수 있는 것은 하나뿐이다. 서버도 같은 값으로 막는다(MAX_ANIMATED).
   여러 장이 들어가면 결이 다른 카드가 늘어나 카드뉴스 전체 흐름이 깨진다. */

export function GifPicker({
  gifs,
  selected,
  onChange,
  loading,
  error,
}: {
  gifs: CardAsset[];
  selected: string | null;
  onChange: (url: string | null) => void;
  loading: boolean;
  error: string | null;
}) {
  // 찾는 데 1분 남짓 걸린다. 그동안 아무것도 안 보이면 없는 줄 알게 되므로
  // 자리를 잡아 두고 진행 중이라는 것을 알린다.
  if (loading) {
    return (
      <Panel
        title="움직이는 상세컷"
        hint="공구 데이터에서 찾는 중입니다 · 1분 정도 걸립니다"
      >
        <div className="flex items-center justify-center py-8">
          <Loader2 className="size-6 animate-spin text-primary" />
        </div>
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel
        title="움직이는 상세컷"
        hint={
          <span className="flex items-center gap-1.5">
            <TriangleAlert className="size-3.5 text-amber-600" />
            {error}
          </span>
        }
      >
        {null}
      </Panel>
    );
  }

  if (gifs.length === 0) return null;

  // 고른 것을 다시 누르면 해제하고, 다른 것을 누르면 그쪽으로 갈아탄다.
  // 하나만 고를 수 있다고 해서 나머지를 잠가 두면 바꿀 때마다 해제를 먼저
  // 눌러야 해서 번거롭다.
  function toggle(url: string) {
    onChange(selected === url ? null : url);
  }

  return (
    <Panel
      title="움직이는 상세컷"
      hint="고른 것은 반드시 쓰입니다 · 1개만 고를 수 있습니다 · 어느 카드에 넣을지는 AI가 정합니다"
      action={
        selected ? (
          <Button variant="ghost" size="sm" onClick={() => onChange(null)}>
            선택 해제
          </Button>
        ) : undefined
      }
    >
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 xl:grid-cols-5">
        {gifs.map((gif) => {
          const picked = selected === gif.url;

          return (
            <button
              key={gif.url}
              type="button"
              onClick={() => toggle(gif.url)}
              className={cn(
                "group relative overflow-hidden rounded-lg border-2 text-left transition",
                picked
                  ? "border-primary"
                  : "border-transparent hover:border-muted-foreground/30",
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

      <p className="mt-3 text-xs text-muted-foreground">
        {selected
          ? "1개 선택 · 첫 장과 마지막 장에는 들어가지 않습니다."
          : "고르지 않으면 모든 카드를 AI가 새로 만듭니다."}
      </p>
    </Panel>
  );
}
