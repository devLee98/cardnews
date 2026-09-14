import { cn } from "@/lib/utils";

/* 워크스페이스 한 틀 안에 쌓이는 구획.

   예전에는 구획마다 테두리를 두른 카드였는데, 시안처럼 바깥에 워크스페이스
   테두리가 하나 더 생기면서 테두리가 겹쳐 보였다. 지금은 테두리를 빼고
   구획 사이를 선 하나로만 나눈다. 선은 감싸는 쪽(PanelStack)이 긋는다. */

export function PanelStack({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col divide-y">{children}</div>;
}

export function Panel({
  title,
  hint,
  action,
  children,
}: {
  title: string;
  hint?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="py-5 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="text-sm font-semibold tracking-[-0.01em]">{title}</h2>
        {hint && (
          <span className="text-xs text-muted-foreground">{hint}</span>
        )}
        {action && <div className="ml-auto">{action}</div>}
      </div>

      {/* 접어 둔 구획처럼 내용이 없을 때 윗여백만 남지 않게 한다 */}
      {children ? <div className="mt-4">{children}</div> : null}
    </section>
  );
}

/** 구획 안에서 진행 중·실패·안내를 알리는 빈 자리 */
export function PanelNotice({
  icon,
  detail,
  className,
  children,
}: {
  icon?: React.ReactNode;
  detail?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-10",
        className,
      )}
    >
      {icon}
      <p className="text-center text-sm text-muted-foreground">{children}</p>
      {detail && (
        <p className="max-w-md text-center text-xs text-muted-foreground/70">
          {detail}
        </p>
      )}
    </div>
  );
}
