/**
 * Столбчатая диаграмма на SVG без сторонних библиотек.
 *
 * Библиотека графиков весит сотни килобайт и тянет свои зависимости, а
 * задача здесь простая: показать ряд значений с подписями. Разметка SVG
 * решает её десятком строк и остаётся доступной для чтения с экрана —
 * значения дублируются текстом под диаграммой.
 */

const HEIGHT = 120;

export default function BarChart({ points, caption, unit = "" }) {
  const max = Math.max(1, ...points.map((point) => point.value));
  const width = Math.max(points.length * 12, 240);
  const step = width / points.length;

  return (
    <figure>
      {caption && <figcaption className="mb-2 text-sm font-medium">{caption}</figcaption>}

      <svg
        viewBox={`0 0 ${width} ${HEIGHT}`}
        className="h-32 w-full"
        role="img"
        aria-label={`${caption}: максимум ${max}${unit}`}
        preserveAspectRatio="none"
      >
        {points.map((point, index) => {
          const barHeight = (point.value / max) * (HEIGHT - 4);
          return (
            <rect
              key={index}
              x={index * step + step * 0.15}
              y={HEIGHT - barHeight}
              width={step * 0.7}
              height={barHeight}
              className="fill-ink"
            >
              <title>{`${point.label}: ${point.value}${unit}`}</title>
            </rect>
          );
        })}
      </svg>

      <div className="mt-1 flex justify-between text-[10px] text-ink-soft">
        <span>{points[0]?.label}</span>
        <span>максимум {max}</span>
        <span>{points[points.length - 1]?.label}</span>
      </div>
    </figure>
  );
}

/** Горизонтальные полосы для распределений: подписи длинные, столбцы не годятся. */
export function BarList({ points, caption }) {
  const max = Math.max(1, ...points.map((point) => point.value));

  return (
    <section>
      {caption && <h3 className="mb-2 text-sm font-medium">{caption}</h3>}
      <dl className="space-y-1">
        {points.map((point) => (
          <div key={point.label} className="grid grid-cols-[9rem_1fr_2.5rem] items-center gap-2">
            <dt className="truncate text-xs text-ink-soft" title={point.label}>
              {point.label}
            </dt>
            <dd className="h-2 rounded bg-surface">
              <div
                className="h-2 rounded bg-ink"
                style={{ width: `${(point.value / max) * 100}%` }}
              />
            </dd>
            <dd className="text-right text-xs tabular-nums">{point.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
