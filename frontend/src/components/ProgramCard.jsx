import { Link } from "react-router-dom";

const APPLICANT_NAMES = {
  IP: "ИП",
  OOO: "ООО",
  NKO: "НКО",
  SMZ: "Самозанятые",
};

export function formatAmount(amount) {
  if (amount === null || amount === undefined) return "не указана";
  return `${Number(amount).toLocaleString("ru-RU")} ₽`;
}

export function formatDate(value) {
  if (!value) return "не указан";
  const [year, month, day] = value.split("-");
  return `${day}.${month}.${year}`;
}

/**
 * Оставшиеся дни подсвечиваются, когда срок меньше недели (FR-014).
 * Цвет — не единственный признак: рядом стоит текст, иначе подсказка
 * пропадала бы для тех, кто не различает оттенки.
 */
function DaysLeft({ days }) {
  if (days === null || days === undefined) return null;
  if (days < 0) return <span className="text-ink-soft">приём завершён</span>;

  const urgent = days <= 7;
  return (
    <span className={urgent ? "font-medium text-warning" : "text-ink-soft"}>
      {urgent && "⚠ "}
      осталось {days} {pluralDays(days)}
    </span>
  );
}

function pluralDays(days) {
  const tail = days % 100;
  if (tail > 10 && tail < 20) return "дней";
  switch (days % 10) {
    case 1:
      return "день";
    case 2:
    case 3:
    case 4:
      return "дня";
    default:
      return "дней";
  }
}

export default function ProgramCard({ program }) {
  return (
    <article className="flex h-full flex-col rounded border border-line p-4 transition-colors hover:border-ink">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
        {program.category && (
          <span className="rounded bg-surface px-2 py-0.5">{program.category}</span>
        )}
        {program.match !== null && program.match !== undefined && (
          <span className="rounded bg-ink px-2 py-0.5 text-white">
            соответствие {program.match}%
          </span>
        )}
      </div>

      <h2 className="mb-1 text-base font-medium">
        <Link to={`/programs/${program.program_id}`} className="hover:underline">
          {program.title}
        </Link>
      </h2>

      <p className="mb-3 text-sm text-ink-soft">{program.organizer}</p>

      <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <dt className="text-ink-soft">Сумма</dt>
        <dd>{formatAmount(program.amount)}</dd>
        <dt className="text-ink-soft">Приём до</dt>
        <dd>{formatDate(program.deadline)}</dd>
      </dl>

      <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <DaysLeft days={program.days_left} />
        {program.applicant_types.length > 0 && (
          <span className="text-ink-soft">
            для {program.applicant_types.map((type) => APPLICANT_NAMES[type] ?? type).join(", ")}
          </span>
        )}
      </div>
    </article>
  );
}
