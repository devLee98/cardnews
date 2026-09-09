import { zip } from "fflate";

import type { DraftCard } from "@/components/card-draft";

/* 완성된 카드를 압축파일 하나로 내려받는다.

   한 장씩 따로 내려받으면 브라우저가 "여러 파일을 받으시겠습니까" 를 묻거나
   중간부터 조용히 막는다. 카드가 9~10장이라 묶어서 한 번에 주는 편이 낫다.

   형식은 카드마다 다르다.
     생성된 카드 : 서버가 data:image/png 로 돌려주므로 그대로 png
     움짤 카드   : 브랜드 서버의 원본을 그대로 쓴다. gif 일 수도 webp 일 수도 있어서
                   받아 본 형식 그대로 넣는다. png 로 바꾸면 움직임이 사라진다.

   움짤은 브랜드 서버가 CORS 를 열어 주지 않아 브라우저가 직접 받지 못한다.
   백엔드(/api/cardnews/asset)가 대신 받아 넘겨준다. 예전에는 여기서 실패해서
   움짤 카드만 빠진 채 나머지만 저장됐다. */

export type ExportResult = {
  saved: number;
  /** 내려받지 못한 카드 이름 */
  failed: string[];
  /** 아직 만들어지는 중이거나 실패해서 건너뛴 카드 수 */
  skipped: number;
};

/** 파일명에 쓸 수 없는 글자를 걷어낸다. */
function safeName(text: string) {
  return text.replace(/[\\/:*?"<>|]/g, "").trim() || "카드";
}

const EXTENSION: Record<string, string> = {
  "image/gif": "gif",
  "image/webp": "webp",
  "image/png": "png",
  "image/jpeg": "jpg",
};

function save(blob: Blob, name: string) {
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = href;
  link.download = name;

  document.body.appendChild(link);
  link.click();
  link.remove();

  // 저장이 시작되기 전에 지우면 빈 파일이 된다
  setTimeout(() => URL.revokeObjectURL(href), 10_000);
}

/** data:image/png;base64,... → 바이트 */
function fromDataUrl(value: string) {
  const binary = atob(value.slice(value.indexOf(",") + 1));
  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }

  return bytes;
}

/** 움짤 원본을 백엔드를 거쳐 받아 온다. 형식은 응답 헤더가 알려준다. */
async function fetchOriginal(url: string) {
  const response = await fetch(`/api/cardnews/asset?url=${encodeURIComponent(url)}`);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const type = (response.headers.get("content-type") ?? "").split(";")[0].trim();
  const bytes = new Uint8Array(await response.arrayBuffer());

  return { bytes, extension: EXTENSION[type] ?? "img" };
}

function toZip(files: Record<string, Uint8Array>) {
  return new Promise<Uint8Array>((resolve, reject) => {
    // 카드 이미지는 이미 압축된 형식이라 다시 압축해도 거의 줄지 않는다.
    // level 0 으로 담기만 하면 9~10장을 묶는 데 시간이 들지 않는다.
    zip(files, { level: 0 }, (error, data) =>
      error ? reject(error) : resolve(data),
    );
  });
}

/** 파일 이름이 겹치면 뒤엣것이 덮어써지므로 번호를 붙여 피한다. */
function unique(files: Record<string, Uint8Array>, name: string) {
  if (!(name in files)) return name;

  const dot = name.lastIndexOf(".");
  const base = name.slice(0, dot);
  const extension = name.slice(dot);

  let index = 2;
  while (`${base}-${index}${extension}` in files) index += 1;

  return `${base}-${index}${extension}`;
}

function stamp() {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");

  return (
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
    `-${pad(now.getHours())}${pad(now.getMinutes())}`
  );
}

export async function downloadCards(cards: DraftCard[]): Promise<ExportResult> {
  const files: Record<string, Uint8Array> = {};
  const failed: string[] = [];
  let skipped = 0;

  for (const [index, card] of cards.entries()) {
    if (card.imageStatus !== "ready" || !card.image) {
      skipped += 1;
      continue;
    }

    // 카드 순서가 파일 이름 순서로 남게 한다
    const base = `${String(index + 1).padStart(2, "0")}-${safeName(card.section)}`;

    try {
      if (card.image.startsWith("data:")) {
        files[unique(files, `${base}.png`)] = fromDataUrl(card.image);
      } else {
        const { bytes, extension } = await fetchOriginal(card.image);
        files[unique(files, `${base}.${extension}`)] = bytes;
      }
    } catch {
      failed.push(`${index + 1}. ${card.section}`);
    }
  }

  const saved = Object.keys(files).length;

  // 한 장도 담기지 않았으면 빈 압축파일을 떨어뜨리지 않는다
  if (saved > 0) {
    const archive = await toZip(files);

    save(
      new Blob([archive as BlobPart], { type: "application/zip" }),
      `카드뉴스-${stamp()}.zip`,
    );
  }

  return { saved, failed, skipped };
}
