/**
 * Главная страница (FR-004).
 *
 * Витрина проекта: коротко объясняет, что за система и для кого, и уводит в
 * каталог. Число действующих программ берётся из того же API, что и каталог —
 * отдельного счётчика на сервере не заводим.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const FEATURES = [
  [
    "Только Республика Коми",
    "Меры поддержки для бизнеса и НКО региона в одном месте — без федерального шума и завершённых конкурсов вперемешку с действующими.",
  ],
  [
    "Подбор под заявителя",
    "Фильтр по типу заявителя — ИП, ООО, НКО, самозанятый — сумме и сроку. Видно только то, на что вы имеете право претендовать.",
  ],
  [
    "Проверенные сведения",
    "Карточки собраны из открытых источников и проверены модератором. У каждой указан первоисточник и срок приёма заявок.",
  ],
];

const STEPS = [
  ["Выберите условия", "Задайте тип заявителя, категорию и сумму — или просто откройте весь каталог."],
  ["Найдите программу", "Сравните меры поддержки, откройте карточку и проверьте сроки и требования."],
  ["Перейдите к подаче", "По ссылке из карточки переходите к первоисточнику и подавайте заявку."],
];

export default function Home() {
  const { user } = useAuth();
  const [total, setTotal] = useState(null);

  useEffect(() => {
    api
      .get("/api/programs?page=1")
      .then((data) => setTotal(data.total))
      .catch(() => setTotal(null));
  }, []);

  return (
    <div className="flex flex-col gap-12">
      <section className="mx-auto max-w-3xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Гранты и меры поддержки для бизнеса и НКО Республики Коми
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-ink-soft">
          Действующие субсидии, гранты и конкурсы региона — собраны из открытых источников,
          отфильтрованы под ваш тип заявителя и проверены вручную.
        </p>

        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link to="/programs" className="btn-primary">
            Смотреть каталог
          </Link>
          <Link to={user ? "/matched" : "/register"} className="btn-secondary">
            Подобрать под себя
          </Link>
        </div>

        {total !== null && total > 0 && (
          <p className="mt-4 text-sm text-ink-soft">
            Сейчас в каталоге действующих программ: <span className="text-ink">{total}</span>
          </p>
        )}
      </section>

      <section>
        <ul className="grid gap-4 md:grid-cols-3">
          {FEATURES.map(([title, text]) => (
            <li key={title} className="rounded border border-line bg-surface p-5">
              <h2 className="mb-2 font-semibold">{title}</h2>
              <p className="text-sm text-ink-soft">{text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="mb-4 text-center text-xl font-semibold">Как это работает</h2>
        <ol className="grid gap-4 md:grid-cols-3">
          {STEPS.map(([title, text], index) => (
            <li key={title} className="rounded border border-line p-5">
              <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-ink text-sm font-semibold text-white">
                {index + 1}
              </div>
              <h3 className="mb-1 font-medium">{title}</h3>
              <p className="text-sm text-ink-soft">{text}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
