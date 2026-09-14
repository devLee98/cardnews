"use client";

import { ImageOff, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { CardText } from "@/lib/api";
import { cn } from "@/lib/utils";

/* 완성된 카드.

   문구는 이미지 안에 함께 그려져 오므로 여기서 덧씌우지 않는다.

   움직이는 상세컷을 쓰는 카드는 문구가 아예 없다. gpt-image 가 gif 를 만들지 못해
   브랜드 원본을 그대로 쓰는데, 그러면 글자를 이미지 안에 그려 넣을 수가 없다.
   예전에는 이미지 아래에 문구 띠를 붙였지만, 그 글자는 화면에만 있고 파일에는 없어서
   내보내면 사라졌다. 미리 보던 카드와 저장된 카드가 달랐다.
   지금은 움직임 하나로 보여주는 카드로 두고, 서버가 4:5 로 맞춰 내보낸다. */

export type DraftCard = CardText & {
  sourceKeys: string[];
  image: string | null;
  imageStatus: "loading" | "ready" | "error";
  imageError?: string;
};

/** 문구를 쓰는 동안 만들어질 카드 수만큼 자리를 잡아 둔다. */
export function CardDraftSkeleton({ count }: { count: number }) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-center gap-3 px-5 pt-5">
        <h2 className="text-sm font-semibold">카드뉴스 초안 · {count}장</h2>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin text-primary" />
          AI가 카드 문구를 쓰는 중
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 p-5 xl:grid-cols-3">
        {Array.from({ length: count }, (_, index) => (
          <Skeleton key={index} className="aspect-4/5 rounded-lg" />
        ))}
      </div>
    </section>
  );
}

export function CardDraftGrid({ cards }: { cards: DraftCard[] }) {
  const done = cards.filter((card) => card.imageStatus === "ready").length;

  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-center gap-3 px-5 pt-5">
        <h2 className="text-sm font-semibold">
          카드뉴스 초안 · {cards.length}장
        </h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {done < cards.length
            ? `카드 만드는 중 ${done}/${cards.length}`
            : "생성 완료"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 p-5 xl:grid-cols-3">
        {cards.map((card, index) => (
          <CardView key={`${index}-${card.section}`} card={card} index={index} />
        ))}
      </div>
    </section>
  );
}

function CardView({ card, index }: { card: DraftCard; index: number }) {
  const animated = Boolean(card.animatedUrl);

  return (
    <figure className="relative flex aspect-4/5 flex-col overflow-hidden rounded-lg border bg-muted">
      <div className={cn("relative", animated ? "min-h-0 flex-1 bg-white" : "flex-1")}>
        {card.imageStatus === "ready" && card.image ? (
          /* base64 나 외부 주소라 next/image 대신 img 를 쓴다 */
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={card.image}
            alt={card.section}
            className={cn(
              "absolute inset-0 size-full",
              // 움직이는 원본은 잘리면 내용이 사라지므로 통째로 담는다.
              // 내보낼 때 서버가 같은 방식으로 4:5 여백을 채워서 이 모양 그대로 저장된다.
              animated ? "object-contain" : "object-cover",
            )}
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            {card.imageStatus === "loading" ? (
              <>
                <Skeleton className="absolute inset-0 rounded-none" />
                <Loader2 className="relative size-5 animate-spin text-muted-foreground" />
                <span className="relative text-[11px] text-muted-foreground">
                  카드 만드는 중
                </span>
              </>
            ) : (
              <>
                <ImageOff className="size-5 text-muted-foreground" />
                <span className="px-4 text-center text-[11px] text-muted-foreground">
                  {card.imageError ?? "카드를 만들지 못했습니다"}
                </span>
              </>
            )}
          </div>
        )}

        <Badge
          variant="secondary"
          className="absolute top-3 left-3 z-10 text-[10px] shadow-sm"
        >
          {index + 1}. {card.section}
        </Badge>
      </div>

    </figure>
  );
}
