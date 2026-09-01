"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import { Download, FileJson, Sparkles, Upload } from "lucide-react";

import {
  CardDraftGrid,
  CardDraftSkeleton,
  type DraftCard,
} from "@/components/card-draft";
import { CardPlan } from "@/components/card-plan";
import { EventPicker } from "@/components/event-picker";
import { GifPicker } from "@/components/gif-picker";
import { DataPanel } from "@/components/data-panel";
import { InstructionBox } from "@/components/instruction-box";
import { StepCard, type StepState } from "@/components/step-card";
import { Button } from "@/components/ui/button";
import {
  requestCardAssets,
  requestCardDraft,
  requestCardImage,
  requestCardPlan,
  runWithLimit,
  type CardAsset,
  type CardPlanItem,
} from "@/lib/api";
import { downloadCards } from "@/lib/download";
import { pickEvent, readEvents, type EventOption } from "@/lib/events";
import type { JsonValue } from "@/lib/json";
import { cn } from "@/lib/utils";

/** 배경 이미지를 동시에 몇 개까지 만들지 */
const IMAGE_CONCURRENCY = 3;

export default function CardNewsPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  // 공구를 연달아 바꾸면 늦게 온 응답이 최신 요청을 덮어쓸 수 있어 번호로 구분한다.
  // 구성안과 상세 이미지는 따로 다시 부를 수 있어 번호도 따로 센다.
  const planIdRef = useRef(0);
  const assetIdRef = useRef(0);

  // 업로드한 파일 원본. 공구가 여러 건 들어 있을 수 있다.
  const [source, setSource] = useState<JsonValue | null>(null);
  const [events, setEvents] = useState<EventOption[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<number | null>(null);
  // 고른 공구 한 건만 남긴 데이터. 서버로 나가는 것은 항상 이쪽이다.
  const [data, setData] = useState<JsonValue | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState(0);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const [cardPlan, setCardPlan] = useState<CardPlanItem[] | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  const [instruction, setInstruction] = useState("");

  const [assets, setAssets] = useState<CardAsset[]>([]);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [assetsError, setAssetsError] = useState<string | null>(null);
  // 사용자가 직접 고른 움직이는 상세컷. 고른 것만 카드에 쓰인다.
  const [pickedGifs, setPickedGifs] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<DraftCard[] | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  // 문구부터 이미지까지 전 과정이 끝날 때까지 참이다.
  // draftLoading 은 문구 단계에서만 참이라 버튼 상태로는 부족하다.
  const [generating, setGenerating] = useState(false);

  const [exporting, setExporting] = useState(false);
  const [exportNote, setExportNote] = useState<string | null>(null);

  const hasFile = source !== null;
  const hasData = data !== null;
  // 다 만들어지기를 기다릴 필요는 없다. 한 장이라도 완성됐으면 내보낼 수 있다.
  // 아직 만들어지는 중인 카드가 하나도 없고, 내려받을 것이 있을 때만 연다.
  // 한 장이 실패했다고 나머지까지 못 받게 하지는 않는다.
  const pendingCards =
    drafts?.filter((card) => card.imageStatus === "loading").length ?? 0;
  const readyCards =
    drafts?.filter((card) => card.imageStatus === "ready" && card.image).length ??
    0;
  const exportable = pendingCards === 0 && readyCards > 0;

  /** AI 생성하기: 문구를 한 번에 받고, 배경은 카드마다 따로 받아 채워 넣는다. */
  async function handleGenerate() {
    if (!data || !cardPlan) return;

    // 문구부터 이미지까지 전부 끝나야 내려간다. 버튼도 그동안 잠긴다.
    setGenerating(true);
    setDraftLoading(true);
    setDraftError(null);
    setDrafts(null);
    setExportNote(null);

    let cards: DraftCard[];

    try {
      // 정지 상세컷은 모두 넘기고, 움짤은 사용자가 고른 것만 넘긴다.
      const usable = assets.filter(
        (asset) => !asset.animated || pickedGifs.includes(asset.url),
      );

      const result = await requestCardDraft(data, cardPlan, instruction, usable);

      cards = result.cards.map((card, index) => ({
        ...card,
        sourceKeys: cardPlan[index]?.sourceKeys ?? [],
        // 움직이는 상세컷을 쓰는 카드는 만들 것 없이 원본을 그대로 쓴다
        image: card.animatedUrl || null,
        imageStatus: (card.animatedUrl ? "ready" : "loading") as
          | "ready"
          | "loading",
      }));

      setDrafts(cards);
    } catch (error) {
      setDraftError(
        error instanceof Error ? error.message : "문구 생성에 실패했습니다.",
      );
      setGenerating(false);
      return;
    } finally {
      setDraftLoading(false);
    }

    // 문구가 먼저 화면에 뜨고, 카드는 만들어지는 대로 한 장씩 채워진다
    const pending = cards.filter((card) => !card.animatedUrl);

    try {
      await runWithLimit(pending, IMAGE_CONCURRENCY, async (card) => {
        const index = cards.indexOf(card);

        try {
          const image = await requestCardImage(data, card);
          patchDraft(index, { image: image.imageBase64, imageStatus: "ready" });
        } catch (error) {
          patchDraft(index, {
            imageStatus: "error",
            imageError:
              error instanceof Error ? error.message : "이미지 생성 실패",
          });
        }
      });
    } finally {
      setGenerating(false);
    }
  }

  /** 완성된 카드를 한 장씩 파일로 내려받는다. */
  async function handleExport() {
    if (!drafts) return;

    setExporting(true);
    setExportNote(null);

    try {
      const { saved, failed, skipped } = await downloadCards(drafts);

      const notes = [`${saved}장 저장`];
      if (skipped) notes.push(`${skipped}장은 아직 안 만들어져 건너뜀`);
      if (failed.length) notes.push(`받지 못한 카드: ${failed.join(", ")}`);

      setExportNote(notes.join(" · "));
    } finally {
      setExporting(false);
    }
  }

  function patchDraft(index: number, patch: Partial<DraftCard>) {
    setDrafts((prev) =>
      prev
        ? prev.map((card, i) => (i === index ? { ...card, ...patch } : card))
        : prev,
    );
  }

  async function generatePlan(picked: JsonValue) {
    const requestId = ++planIdRef.current;

    setPlanLoading(true);
    setPlanError(null);
    setCardPlan(null);

    try {
      const result = await requestCardPlan(picked);
      if (requestId !== planIdRef.current) return;

      setCardPlan(result.cards);
    } catch (error) {
      if (requestId !== planIdRef.current) return;

      setPlanError(
        error instanceof Error
          ? error.message
          : "구성안을 만드는 중 알 수 없는 오류가 발생했습니다.",
      );
    } finally {
      if (requestId === planIdRef.current) setPlanLoading(false);
    }
  }

  async function loadAssets(picked: JsonValue) {
    const requestId = ++assetIdRef.current;

    setAssets([]);
    setPickedGifs([]);
    setAssetsError(null);
    setAssetsLoading(true);

    try {
      const result = await requestCardAssets(picked);
      if (requestId !== assetIdRef.current) return;

      setAssets(result.images);
    } catch (error) {
      if (requestId !== assetIdRef.current) return;

      setAssetsError(
        error instanceof Error
          ? error.message
          : "상세 이미지를 불러오지 못했습니다.",
      );
    } finally {
      if (requestId === assetIdRef.current) setAssetsLoading(false);
    }
  }

  /**
   * 공구를 고른다. 고른 공구 한 건만 남긴 데이터로 분석을 다시 시작한다.
   * 구성안과 상세 이미지 살펴보기는 서로 기다릴 필요가 없어 나란히 돌린다.
   */
  function selectEvent(root: JsonValue, index: number) {
    const picked = pickEvent(root, index);

    setSelectedEvent(index);
    setData(picked);

    // 앞서 고른 공구로 만든 카드는 더 이상 맞지 않으므로 비운다
    setDrafts(null);
    setDraftError(null);

    void generatePlan(picked);
    void loadAssets(picked);
  }

  /** 새 파일을 올리면 이전 파일로 만든 것은 모두 버린다. */
  function clearResults() {
    // 아직 돌아오지 않은 응답이 새 화면을 덮어쓰지 않도록 번호를 넘긴다
    planIdRef.current += 1;
    assetIdRef.current += 1;

    setSelectedEvent(null);
    setData(null);

    setCardPlan(null);
    setPlanLoading(false);
    setPlanError(null);

    setAssets([]);
    setPickedGifs([]);
    setAssetsLoading(false);
    setAssetsError(null);

    setDrafts(null);
    setDraftError(null);
    setExportNote(null);
  }

  async function readFile(file: File) {
    setFileError(null);

    // 확장자가 .json 이 아니면 파일을 읽지 않고 여기서 끝낸다.
    // input 의 accept 는 파일 탐색기 필터일 뿐이라 끌어다 놓는 경로는 막지 못한다.
    if (!/\.json$/i.test(file.name)) {
      setFileError("파일 형태 확인 후 다시 업로드해 주세요!");
      return;
    }

    let parsed: JsonValue;

    try {
      parsed = JSON.parse(await file.text()) as JsonValue;
    } catch {
      // 이미 올려둔 데이터가 있으면 그대로 두고 실패만 알린다
      setFileError("파일이 손상되어 읽지 못했습니다. 확인 후 다시 올려주세요.");
      return;
    }

    const list = readEvents(parsed);

    // 공구가 하나도 없으면 뒤 단계가 전부 빈손이 된다. 여기서 끊는다.
    if (list.length === 0) {
      setFileError(
        "공구(events) 데이터를 찾지 못했습니다. 파일 구조를 확인 후 다시 올려주세요.",
      );
      return;
    }

    clearResults();
    setSource(parsed);
    setEvents(list);
    setFileName(file.name);
    setFileSize(file.size);

    // 공구가 한 건뿐이면 고를 것이 없으므로 바로 분석으로 넘어간다
    if (list.length === 1) selectEvent(parsed, 0);
  }

  const uploadState: StepState = hasFile ? "done" : "active";
  const eventState: StepState = !hasFile ? "idle" : hasData ? "done" : "active";
  const planState: StepState = !hasData ? "idle" : cardPlan ? "done" : "active";
  const instructionState: StepState = cardPlan ? "active" : "idle";

  function eventSubtitle() {
    if (!hasFile) return undefined;
    if (selectedEvent !== null) return events[selectedEvent]?.name;
    return `공구 ${events.length}건 · 만들 공구를 골라주세요`;
  }

  function planSubtitle() {
    if (!hasData) return undefined;
    if (planLoading) return "AI가 구성안을 짜는 중…";
    if (planError) return "구성안 생성 실패";
    if (cardPlan) return `${cardPlan.length}단 구성안`;
    return undefined;
  }

  return (
    <div className="min-h-screen bg-muted/40">
      {/* ── 헤더 ── */}
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-6">
          {/* 로고 원본이 327x84 라 그 비율(3.89:1)을 지켜 높이 22px 로 줄인다 */}
          <Image
            src="/logo.png"
            alt="Quedot"
            width={86}
            height={22}
            priority
          />
          <span className="text-sm font-semibold text-muted-foreground">
            카드뉴스
          </span>

          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            disabled={!exportable || exporting}
            onClick={handleExport}
            title={
              pendingCards > 0
                ? `카드 ${pendingCards}장이 아직 만들어지는 중입니다`
                : undefined
            }
          >
            <Download className={cn(exporting && "animate-pulse")} />
            {exporting ? "내보내는 중…" : "내보내기"}
          </Button>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1400px] grid-cols-1 items-start gap-6 p-6 lg:grid-cols-[360px_1fr]">
        {/* ── 좌측 단계 메뉴 ──
            넓은 화면에서는 화면에 붙여 둔다. 오른쪽 결과가 길어서 스크롤을 내리면
            지금 몇 단계인지와 생성 버튼이 화면 밖으로 사라지기 때문이다.
            top-20 = 헤더 높이(3.5rem) + 본문 여백(1.5rem).
            창이 낮아 메뉴가 다 안 들어가면 그때만 메뉴 안에서 스크롤된다. */}
        <aside className="flex flex-col gap-3 lg:sticky lg:top-20 lg:max-h-[calc(100vh-5.5rem)] lg:overflow-y-auto">
          {/* 1. 공구 데이터 업로드 */}
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);

              const file = event.dataTransfer.files[0];
              if (file) void readFile(file);
            }}
            className={cn("rounded-xl", dragging && "ring-2 ring-primary")}
          >
            <StepCard
              num={1}
              title="공구 데이터 업로드"
              state={uploadState}
              subtitle={
                hasFile
                  ? `${fileName} · ${Math.max(1, Math.round(fileSize / 1024))}KB`
                  : "JSON 파일을 끌어다 놓거나 눌러서 선택"
              }
              action={hasFile ? "다시 올리기" : undefined}
              onAction={() => fileInputRef.current?.click()}
              onClick={hasFile ? undefined : () => fileInputRef.current?.click()}
            />
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void readFile(file);
            }}
          />

          {fileError && (
            <p className="px-1 text-xs text-destructive">{fileError}</p>
          )}

          {/* 2. 공구 선택 — 한 파일에 공구가 여러 건 들어 있다 */}
          <StepCard
            num={2}
            title="공구 선택"
            state={eventState}
            subtitle={eventSubtitle()}
          />

          {/* 3. 카드 구성 확인 */}
          <StepCard
            num={3}
            title="카드 구성 확인"
            state={planState}
            subtitle={planSubtitle()}
          />

          {/* 4. 추가 인스트럭션 */}
          <StepCard
            num={4}
            title="추가 인스트럭션"
            state={instructionState}
            subtitle="(선택)"
          />

          <Button
            size="lg"
            className="mt-1 w-full"
            disabled={!cardPlan || generating}
            onClick={handleGenerate}
          >
            <Sparkles className={cn(generating && "animate-pulse")} />
            {generating ? "AI 카드뉴스 생성중…" : "AI 생성하기"}
          </Button>
        </aside>

        {/* ── 우측 결과 영역 ── */}
        <section>
          {source ? (
            <div className="flex flex-col gap-5">
              {/* 공구가 여러 건일 때만 고르는 화면을 둔다 */}
              {events.length > 1 && (
                <EventPicker
                  events={events}
                  selected={selectedEvent}
                  onSelect={(index) => selectEvent(source, index)}
                />
              )}

              {data ? (
                <>
                  <DataPanel data={data} onChange={setData} />

                  <CardPlan
                    plan={cardPlan}
                    loading={planLoading}
                    error={planError}
                    onRetry={() => void generatePlan(data)}
                  />

                  <GifPicker
                    gifs={assets.filter((asset) => asset.animated)}
                    selected={pickedGifs}
                    onChange={setPickedGifs}
                    loading={assetsLoading}
                    error={assetsError}
                  />

                  {/* 추가 인스트럭션 — 구성안을 확인한 뒤에 적는다 */}
                  <InstructionBox
                    value={instruction}
                    onChange={setInstruction}
                  />

                  {/* 카드 초안 */}
                  {drafts ? (
                    <div className="flex flex-col gap-2">
                      {exportNote && (
                        <p className="px-1 text-xs text-muted-foreground">
                          {exportNote}
                        </p>
                      )}
                      <CardDraftGrid cards={drafts} />
                    </div>
                  ) : draftLoading && cardPlan ? (
                    // 몇 장을 만들지는 구성안에 이미 정해져 있다. 그 수만큼 자리를 깔아 둔다.
                    <CardDraftSkeleton count={cardPlan.length} />
                  ) : (
                    <div className="rounded-xl border border-dashed px-5 py-10 text-center text-sm text-muted-foreground">
                      {draftError ?? "생성하면 이 자리에 카드가 표시됩니다"}
                    </div>
                  )}
                </>
              ) : (
                <div className="rounded-xl border border-dashed px-5 py-16 text-center text-sm text-muted-foreground">
                  위에서 카드뉴스를 만들 공구를 골라주세요
                </div>
              )}
            </div>
          ) : (
            <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-card">
              <div className="flex size-12 items-center justify-center rounded-full bg-muted">
                <FileJson className="size-5 text-muted-foreground" />
              </div>
              <p className="text-center text-sm text-muted-foreground">
                아직 업로드된 데이터가 없습니다
                <br />
                왼쪽 1단계에서 공구 JSON을 올려주세요
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-1"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload />
                파일 선택
              </Button>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
