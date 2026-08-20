"use client";

import { useMemo, useRef, useState } from "react";
import { Download, FileJson, Sparkles, Upload } from "lucide-react";

import { CardPlan } from "@/components/card-plan";
import { DataPanel } from "@/components/data-panel";
import { StepCard, type StepState } from "@/components/step-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { analyzeData } from "@/lib/analyze-data";
import { requestCardPlan, type CardPlanItem } from "@/lib/api";
import type { JsonValue } from "@/lib/json";
import { cn } from "@/lib/utils";

const MAX_INSTRUCTION = 500;

export default function CardNewsPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  // 업로드를 연달아 하면 늦게 온 응답이 최신 요청을 덮어쓸 수 있어 번호로 구분한다
  const requestIdRef = useRef(0);

  const [data, setData] = useState<JsonValue | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState(0);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const [cardPlan, setCardPlan] = useState<CardPlanItem[] | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planConfirmed, setPlanConfirmed] = useState(false);

  const [instruction, setInstruction] = useState("");

  const analysis = useMemo(() => (data ? analyzeData(data) : null), [data]);
  const hasData = data !== null;

  async function generatePlan(source: JsonValue) {
    const requestId = ++requestIdRef.current;

    setPlanLoading(true);
    setPlanError(null);
    setCardPlan(null);
    setPlanConfirmed(false);

    try {
      const result = await requestCardPlan(source);
      if (requestId !== requestIdRef.current) return;

      setCardPlan(result.cards);
    } catch (error) {
      if (requestId !== requestIdRef.current) return;

      setPlanError(
        error instanceof Error
          ? error.message
          : "구성안을 만드는 중 알 수 없는 오류가 발생했습니다.",
      );
    } finally {
      if (requestId === requestIdRef.current) setPlanLoading(false);
    }
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

    setData(parsed);
    setFileName(file.name);
    setFileSize(file.size);

    // 별도 지시 없이 바로 분석과 구성안 생성으로 넘어간다
    void generatePlan(parsed);
  }

  const uploadState: StepState = hasData ? "done" : "active";
  const planState: StepState = !hasData
    ? "idle"
    : planConfirmed
      ? "done"
      : "active";
  const instructionState: StepState = planConfirmed ? "active" : "idle";

  function planSubtitle() {
    if (!hasData) return undefined;
    if (planLoading) return "AI가 구성안을 짜는 중…";
    if (planError) return "구성안 생성 실패";
    if (planConfirmed) return "구성안 확인 완료";
    if (cardPlan) return `${cardPlan.length}단 구성안 검토 중 →`;
    return undefined;
  }

  return (
    <div className="min-h-screen bg-muted/40">
      {/* ── 헤더 ── */}
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-6">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </div>
          <span className="text-sm font-semibold">큐닷 카드뉴스</span>

          <Button variant="outline" size="sm" disabled className="ml-auto">
            <Download />
            내보내기
          </Button>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1400px] grid-cols-1 items-start gap-6 p-6 lg:grid-cols-[360px_1fr]">
        {/* ── 좌측 단계 메뉴 ── */}
        <aside className="flex flex-col gap-3">
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
            className={cn("rounded-xl", dragging && "ring-2 ring-amber-500/60")}
          >
            <StepCard
              num={1}
              title="공구 데이터 업로드"
              state={uploadState}
              subtitle={
                hasData
                  ? `${fileName} · ${Math.max(1, Math.round(fileSize / 1024))}KB`
                  : "JSON 파일을 끌어다 놓거나 눌러서 선택"
              }
              action={hasData ? "다시 올리기" : undefined}
              onAction={() => fileInputRef.current?.click()}
              onClick={hasData ? undefined : () => fileInputRef.current?.click()}
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

          {/* 2. 카드 구성 확인 */}
          <StepCard
            num={2}
            title="카드 구성 확인"
            state={planState}
            subtitle={planSubtitle()}
          />

          {/* 3. 추가 인스트럭션 */}
          <StepCard
            num={3}
            title="추가 인스트럭션"
            state={instructionState}
            subtitle="(선택)"
          />

          <Button size="lg" className="mt-1 w-full" disabled={!planConfirmed}>
            <Sparkles />
            AI 생성하기
          </Button>
        </aside>

        {/* ── 우측 결과 영역 ── */}
        <section>
          {analysis && data ? (
            <div className="flex flex-col gap-5">
              <DataPanel analysis={analysis} data={data} onChange={setData} />

              <CardPlan
                plan={cardPlan}
                loading={planLoading}
                error={planError}
                confirmed={planConfirmed}
                onConfirm={() => setPlanConfirmed(true)}
                onRetry={() => void generatePlan(data)}
              />

              {/* 추가 인스트럭션 — 구성안을 확인해야 열린다 */}
              <section
                className={cn(
                  "rounded-xl border bg-card",
                  !planConfirmed && "opacity-60",
                )}
              >
                <div className="flex items-center gap-3 px-5 pt-5">
                  <h2 className="text-sm font-semibold">추가 인스트럭션</h2>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {planConfirmed
                      ? "선택 입력"
                      : "카드 구성안을 확인하면 열립니다"}
                  </span>
                </div>

                <div className="px-5 pt-4 pb-5">
                  <Textarea
                    value={instruction}
                    disabled={!planConfirmed}
                    maxLength={MAX_INSTRUCTION}
                    onChange={(event) => setInstruction(event.target.value)}
                    placeholder="추가로 참고했으면 하는 내용을 적어주세요"
                    className="min-h-[100px] resize-none"
                  />
                  <p className="mt-1.5 text-right text-xs text-muted-foreground">
                    {instruction.length} / {MAX_INSTRUCTION}
                  </p>
                </div>
              </section>

              {/* 카드 초안 자리 */}
              <div className="rounded-xl border border-dashed px-5 py-10 text-center text-sm text-muted-foreground">
                생성하면 이 자리에 카드가 표시됩니다
              </div>
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
