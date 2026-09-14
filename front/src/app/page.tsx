"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import { Check, Download, FileJson, Loader2, Sparkles, Upload } from "lucide-react";

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
import { Panel, PanelStack } from "@/components/panel";
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
  // 사용자가 직접 고른 움직이는 상세컷. 고른 것만 카드에 쓰이며 하나만 고른다.
  const [pickedGif, setPickedGif] = useState<string | null>(null);
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
        (asset) => !asset.animated || asset.url === pickedGif,
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
          const image = await requestCardImage(data, card, instruction);
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

  /** 완성된 카드를 압축파일 하나로 내려받는다. */
  async function handleExport() {
    if (!drafts) return;

    setExporting(true);
    setExportNote(null);

    try {
      const { saved, failed, skipped } = await downloadCards(drafts);

      const notes = [
        saved > 0 ? `압축파일에 ${saved}장 담았습니다` : "내려받을 카드가 없습니다",
      ];
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
    setPickedGif(null);
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
    setPickedGif(null);
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

  /* 워크스페이스 머리글. 지금 무엇을 보고 있는지 한 줄로 알린다.
     카드 장수는 초안이 있으면 초안 기준, 없으면 구성안 기준이다. */
  const cardCount = drafts?.length ?? cardPlan?.length ?? 0;

  function workspaceTitle() {
    // 공구를 고르는 중에는 아래 구획 제목이 "공구 선택"이라 머리글까지 같은 말을
    // 쓰면 두 번 읽힌다. 구성안이 나온 뒤부터만 장수를 붙인다.
    return cardCount ? `카드뉴스 초안 · ${cardCount}장` : "카드뉴스 만들기";
  }

  /* 머리글 오른쪽 진행 표시.
     문구 → 이미지 순으로 진행되므로 늦은 단계부터 확인한다. */
  function workspaceStatus() {
    if (draftLoading) return { done: false, text: "AI가 카드 문구를 쓰는 중" };

    if (generating && drafts) {
      return {
        done: false,
        text: `카드 만드는 중 ${readyCards}/${drafts.length}`,
      };
    }

    if (drafts) return { done: true, text: "AI 카드뉴스 생성 완료" };
    if (planLoading) return { done: false, text: "AI가 구성안을 짜는 중" };

    return null;
  }

  const status = workspaceStatus();

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* ── 헤더 ── */}
      <header className="sticky top-0 z-20 flex h-[61px] shrink-0 items-center gap-2.5 border-b bg-background/90 px-5 backdrop-blur lg:px-[35px]">
        {/* 로고 원본이 327x84 라 그 비율(3.89:1)을 지켜 높이 22px 로 줄인다 */}
        <Image src="/logo.png" alt="Quedot" width={86} height={22} priority />
        <span className="text-[15px] font-medium text-muted-foreground">
          카드뉴스
        </span>
      </header>

      <div className="flex flex-1 flex-col lg:flex-row">
        {/* ── 좌측 단계 메뉴 ──
            넓은 화면에서는 화면에 붙여 둔다. 오른쪽 결과가 길어서 스크롤을 내리면
            지금 몇 단계인지와 생성 버튼이 화면 밖으로 사라지기 때문이다.
            top/height 의 61px 은 헤더 높이다. 메뉴가 창보다 길면 메뉴 안에서만
            스크롤되고 회색 바탕은 창 끝까지 채운다.
            좁은 화면에서는 위로 올라와 단계가 두 칸씩 나란히 눕는다. */}
        <aside className="w-full shrink-0 bg-sidebar px-5 py-4 lg:sticky lg:top-[61px] lg:h-[calc(100vh-61px)] lg:w-[330px] lg:overflow-y-auto lg:px-[34px] lg:py-[23px] lg:pb-10">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1 lg:gap-3.5">
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
                onClick={
                  hasFile ? undefined : () => fileInputRef.current?.click()
                }
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
              <p className="px-1 text-xs text-destructive sm:col-span-2 lg:col-span-1">
                {fileError}
              </p>
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

            {/* 만들기와 내보내기는 한 덩어리로 둔다.
                좁은 화면에서 단계가 두 칸으로 눕더라도 둘은 폭을 다 쓴다. */}
            <div className="flex flex-col gap-3 sm:col-span-2 lg:col-span-1">
              <Button
                size="lg"
                className="h-[43px] w-full font-bold"
                disabled={!cardPlan || generating}
                onClick={handleGenerate}
              >
                <Sparkles className={cn(generating && "animate-pulse")} />
                {generating ? "AI 카드뉴스 생성중…" : "AI 생성하기"}
              </Button>

              <Button
                variant="outline"
                size="lg"
                className="h-[42px] w-full bg-card"
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

              {exportNote && (
                <p className="px-1 text-xs text-muted-foreground">
                  {exportNote}
                </p>
              )}
            </div>
          </div>
        </aside>

        {/* ── 우측 워크스페이스 ── */}
        <main className="min-w-0 flex-1 p-4 lg:py-[29px] lg:pr-[35px] lg:pl-[21px]">
          <section className="rounded-xl border bg-card p-5 shadow-[0_1px_3px_rgba(0,0,0,0.025)] lg:min-h-[calc(100vh-119px)] lg:px-[27px] lg:pt-[26px] lg:pb-[35px]">
            <div className="mb-4 flex min-h-7 flex-wrap items-center justify-between gap-x-3 gap-y-1">
              <h1 className="text-[17px] font-bold tracking-[-0.5px]">
                {workspaceTitle()}
              </h1>

              {status && (
                <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
                  {status.done ? (
                    <Check className="size-3.5 text-primary" />
                  ) : (
                    <Loader2 className="size-3.5 animate-spin text-primary" />
                  )}
                  {status.text}
                </p>
              )}
            </div>

            {source ? (
              data ? (
                <PanelStack>
                  {/* 공구가 여러 건일 때만 고르는 구획을 둔다 */}
                  {events.length > 1 && (
                    <EventPicker
                      events={events}
                      selected={selectedEvent}
                      onSelect={(index) => selectEvent(source, index)}
                    />
                  )}

                  <DataPanel data={data} />

                  <CardPlan
                    plan={cardPlan}
                    loading={planLoading}
                    error={planError}
                    onRetry={() => void generatePlan(data)}
                  />

                  <GifPicker
                    gifs={assets.filter((asset) => asset.animated)}
                    selected={pickedGif}
                    onChange={setPickedGif}
                    loading={assetsLoading}
                    error={assetsError}
                  />

                  {/* 추가 인스트럭션 — 구성안을 확인한 뒤에 적는다 */}
                  <InstructionBox value={instruction} onChange={setInstruction} />

                  {/* 카드 초안 — 장수와 진행 상황은 위 머리글이 맡는다 */}
                  <Panel title="카드뉴스 초안">
                    {drafts ? (
                      <CardDraftGrid cards={drafts} />
                    ) : draftLoading && cardPlan ? (
                      // 몇 장을 만들지는 구성안에 이미 정해져 있다. 그 수만큼 자리를 깔아 둔다.
                      <CardDraftSkeleton count={cardPlan.length} />
                    ) : (
                      <div className="rounded-xl border border-dashed px-5 py-10 text-center text-sm text-muted-foreground">
                        {draftError ?? "생성하면 이 자리에 카드가 표시됩니다"}
                      </div>
                    )}
                  </Panel>
                </PanelStack>
              ) : (
                <PanelStack>
                  <EventPicker
                    events={events}
                    selected={selectedEvent}
                    onSelect={(index) => selectEvent(source, index)}
                  />
                </PanelStack>
              )
            ) : (
              <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed">
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
    </div>
  );
}
