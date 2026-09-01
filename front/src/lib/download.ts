import type { DraftCard } from "@/components/card-draft";

/* 완성된 카드를 파일로 내려받는다.

   생성된 카드는 서버가 data:image/png 로 돌려주므로 그대로 저장하면 PNG 가 된다.
   움직이는 상세컷을 쓰는 카드만 예외다. 브랜드 서버의 원본을 그대로 쓰기 때문에
   받아와서 저장해야 하고, 움직임을 살리려면 gif 그대로 두어야 한다. */

/** 브라우저가 연달아 오는 다운로드를 막지 않도록 사이에 두는 간격 */
const GAP_MS = 300;

export type ExportResult = {
  saved: number;
  /** 내려받지 못한 카드 이름. 대부분 브랜드 서버가 막은 움짤이다. */
  failed: string[];
  /** 아직 만들어지는 중이거나 실패해서 건너뛴 카드 수 */
  skipped: number;
};

/** 파일명에 쓸 수 없는 글자를 걷어낸다. */
function safeName(text: string) {
  return text.replace(/[\\/:*?"<>|]/g, "").trim() || "카드";
}

function save(href: string, name: string) {
  const link = document.createElement("a");
  link.href = href;
  link.download = name;

  document.body.appendChild(link);
  link.click();
  link.remove();
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function downloadCards(cards: DraftCard[]): Promise<ExportResult> {
  const failed: string[] = [];
  let saved = 0;
  let skipped = 0;

  for (const [index, card] of cards.entries()) {
    if (card.imageStatus !== "ready" || !card.image) {
      skipped += 1;
      continue;
    }

    // 카드 순서가 파일 이름 순서로 남게 한다
    const base = `${String(index + 1).padStart(2, "0")}-${safeName(card.section)}`;

    if (card.image.startsWith("data:")) {
      save(card.image, `${base}.png`);
      saved += 1;
    } else {
      // 다른 도메인의 주소는 download 속성이 무시되어 새 탭으로 열려버린다.
      // 직접 받아서 내 쪽 데이터로 만든 뒤에 저장한다.
      try {
        const blob = await (await fetch(card.image)).blob();
        const href = URL.createObjectURL(blob);

        save(href, `${base}.gif`);
        saved += 1;

        // 저장이 시작되기 전에 지우면 빈 파일이 된다
        setTimeout(() => URL.revokeObjectURL(href), 10_000);
      } catch {
        failed.push(`${index + 1}. ${card.section}`);
      }
    }

    await wait(GAP_MS);
  }

  return { saved, failed, skipped };
}
