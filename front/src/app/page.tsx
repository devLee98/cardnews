"use client";

import { useRef, useState } from "react";
import {
  Check,
  Download,
  FileJson,
  LayoutGrid,
  Sparkles,
  Table2,
  Upload,
  X,
} from "lucide-react";

import { DataInspector, type JsonValue } from "@/components/data-inspector";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";

type PreviewMode = "data" | "cards";

const CARD_COUNTS = [6, 7, 8, 9, 10];
const MAX_INSTRUCTION = 500;

export default function CardNewsPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [openSteps, setOpenSteps] = useState<string[]>(["step-1"]);
  const [fileName, setFileName] = useState<string | null>(null);
  const [data, setData] = useState<JsonValue | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [cardCount, setCardCount] = useState(7);
  const [instruction, setInstruction] = useState("");
  const [preview, setPreview] = useState<PreviewMode>("data");

  const hasData = data !== null;

  const fieldCount =
    data && typeof data === "object" && !Array.isArray(data)
      ? Object.keys(data).length
      : 0;

  async function readFile(file: File) {
    setFileError(null);

    try {
      const parsed = JSON.parse(await file.text()) as JsonValue;

      setData(parsed);
      setFileName(file.name);
      setPreview("data");
      setOpenSteps((prev) =>
        prev.includes("step-2") ? prev : [...prev, "step-2"],
      );
    } catch {
      setData(null);
      setFileName(null);
      setFileError("JSON 형식이 아니거나 파일이 손상되었습니다.");
    }
  }

  function clearUpload() {
    setData(null);
    setFileName(null);
    setFileError(null);
    setPreview("data");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  return (
    <div className="min-h-screen bg-muted/40">
      {/* ── 헤더 ── */}
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-6">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm leading-tight font-semibold">
              큐닷 카드뉴스
            </span>
            <span className="text-xs leading-tight text-muted-foreground">
              공구 데이터로 카드뉴스 만들기
            </span>
          </div>

          <Button variant="outline" size="sm" disabled className="ml-auto">
            <Download />
            내보내기
          </Button>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1400px] grid-cols-1 items-start gap-6 p-6 lg:grid-cols-[380px_1fr]">
        {/* ── 좌측: 단계 패널 ── */}
        <div className="flex flex-col gap-4">
          <Card className="overflow-hidden py-0">
            <Accordion
              type="multiple"
              value={openSteps}
              onValueChange={setOpenSteps}
            >
              {/* 1. 공구 데이터 업로드 */}
              <AccordionItem value="step-1" className="px-5">
                <AccordionTrigger className="py-4 hover:no-underline">
                  <StepLabel num={1} label="공구 데이터 업로드" done={hasData} />
                </AccordionTrigger>
                <AccordionContent className="pb-5">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
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
                    className={cn(
                      "flex w-full flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-8 transition-colors",
                      dragging
                        ? "border-primary bg-accent"
                        : "hover:border-primary/50 hover:bg-accent/50",
                    )}
                  >
                    <Upload className="size-5 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      JSON 파일을 끌어다 놓기
                    </span>
                    <span className="text-xs text-muted-foreground">
                      또는 클릭해서 선택 (.json)
                    </span>
                  </button>

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

                  {fileName && (
                    <div className="mt-3 flex items-center gap-2 rounded-lg border bg-card p-3">
                      <FileJson className="size-4 shrink-0 text-muted-foreground" />
                      <span className="truncate text-sm">{fileName}</span>
                      <Badge variant="secondary" className="ml-auto shrink-0">
                        필드 {fieldCount}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-6 shrink-0"
                        onClick={clearUpload}
                        aria-label="업로드 취소"
                      >
                        <X />
                      </Button>
                    </div>
                  )}

                  {hasData && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      오른쪽에서 내용을 확인하고 잘못된 값은 바로 고칠 수
                      있습니다.
                    </p>
                  )}

                  {fileError && (
                    <p className="mt-2 text-xs text-destructive">{fileError}</p>
                  )}
                </AccordionContent>
              </AccordionItem>

              {/* 2. 카드 구성 제안 확인 */}
              <AccordionItem value="step-2" className="px-5">
                <AccordionTrigger className="py-4 hover:no-underline">
                  <StepLabel num={2} label="카드 구성 제안 확인" done={false} />
                </AccordionTrigger>
                <AccordionContent className="pb-5">
                  <p className="rounded-lg border border-dashed px-4 py-6 text-center text-xs leading-relaxed text-muted-foreground">
                    AI가 제안한 카드 구성이
                    <br />
                    여기에 표시됩니다
                  </p>
                </AccordionContent>
              </AccordionItem>

              {/* 3. 추가 인스트럭션 */}
              <AccordionItem value="step-3" className="border-b-0 px-5">
                <AccordionTrigger className="py-4 hover:no-underline">
                  <StepLabel
                    num={3}
                    label="추가 인스트럭션"
                    done={instruction.trim().length > 0}
                  />
                </AccordionTrigger>
                <AccordionContent className="pb-5">
                  <Textarea
                    value={instruction}
                    maxLength={MAX_INSTRUCTION}
                    onChange={(event) => setInstruction(event.target.value)}
                    placeholder="추가로 참고했으면 하는 내용을 적어주세요"
                    className="min-h-[110px] resize-none"
                  />
                  <p className="mt-1.5 text-right text-xs text-muted-foreground">
                    {instruction.length} / {MAX_INSTRUCTION}
                  </p>

                  <Separator className="my-4" />

                  <p className="mb-2.5 text-sm font-medium">카드뉴스 장수</p>
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    value={String(cardCount)}
                    onValueChange={(value) => {
                      if (value) setCardCount(Number(value));
                    }}
                    className="justify-start"
                  >
                    {CARD_COUNTS.map((count) => (
                      <ToggleGroupItem
                        key={count}
                        value={String(count)}
                        className="px-3"
                      >
                        {count}장
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </Card>

          {/* 4. AI 생성 */}
          <div>
            <Button size="lg" className="w-full" disabled={!hasData}>
              <Sparkles />
              AI 생성하기
            </Button>
            {!hasData && (
              <p className="mt-2 text-center text-xs text-muted-foreground">
                공구 데이터를 업로드하면 활성화됩니다
              </p>
            )}
          </div>
        </div>

        {/* ── 우측: 미리보기 ── */}
        <Card className="min-h-[720px]">
          <CardHeader className="border-b">
            <CardTitle className="text-base">
              {preview === "data" ? "공구 데이터 미리보기" : "카드 미리보기"}
            </CardTitle>
            <CardDescription>
              {preview === "data"
                ? hasData
                  ? "값을 클릭해서 바로 고칠 수 있습니다"
                  : "업로드한 공구 데이터가 여기에 표시됩니다"
                : "생성하면 여기에 카드가 표시됩니다"}
            </CardDescription>

            <CardAction>
              <ToggleGroup
                type="single"
                variant="outline"
                value={preview}
                onValueChange={(value) => {
                  if (value) setPreview(value as PreviewMode);
                }}
              >
                <ToggleGroupItem value="data" disabled={!hasData}>
                  <Table2 />
                  공구 데이터
                </ToggleGroupItem>
                <ToggleGroupItem value="cards">
                  <LayoutGrid />
                  카드
                </ToggleGroupItem>
              </ToggleGroup>
            </CardAction>
          </CardHeader>

          <CardContent>
            {preview === "data" ? (
              hasData ? (
                <DataInspector data={data} onChange={setData} />
              ) : (
                <EmptyState
                  icon={<FileJson className="size-5 text-muted-foreground" />}
                  message={
                    <>
                      아직 업로드된 데이터가 없습니다
                      <br />
                      왼쪽 1단계에서 공구 JSON을 올려주세요
                    </>
                  }
                />
              )
            ) : (
              <EmptyState
                icon={<LayoutGrid className="size-5 text-muted-foreground" />}
                message={
                  <>
                    아직 생성된 카드가 없습니다
                    <br />
                    왼쪽에서 데이터를 올리고 AI 생성하기를 눌러주세요
                  </>
                }
              />
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

function StepLabel({
  num,
  label,
  done,
}: {
  num: number;
  label: string;
  done: boolean;
}) {
  return (
    <span className="flex items-center gap-3">
      <span
        className={cn(
          "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs transition-colors",
          done
            ? "border-primary bg-primary text-primary-foreground"
            : "text-muted-foreground",
        )}
      >
        {done ? <Check className="size-3.5" /> : num}
      </span>
      <span className="text-sm font-medium">{label}</span>
    </span>
  );
}

function EmptyState({
  icon,
  message,
}: {
  icon: React.ReactNode;
  message: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[560px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted">
        {icon}
      </div>
      <p className="text-center text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
