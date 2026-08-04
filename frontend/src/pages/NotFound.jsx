/**
 * Страница «не найдено» (пункт 5.5 требований).
 *
 * Тупик без выхода бесполезен, поэтому страница предлагает то, зачем
 * пользователь и пришёл: поиск по каталогу программ.
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function NotFound() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  return (
    <div className="mx-auto max-w-lg py-12 text-center">
      <p className="mb-2 text-5xl font-light text-line">404</p>
      <h1 className="mb-2 text-xl font-semibold">Страница не найдена</h1>
      <p className="mb-6 text-sm text-ink-soft">
        Возможно, программа снята с публикации или адрес указан с ошибкой.
      </p>

      <form
        className="mb-6 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          navigate(`/programs?search=${encodeURIComponent(query.trim())}`);
        }}
        role="search"
      >
        <input
          type="search"
          className="field"
          placeholder="Поиск по каталогу программ"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Поиск по каталогу программ"
        />
        <button type="submit" className="btn-primary shrink-0">
          Найти
        </button>
      </form>

      <Link to="/programs" className="text-sm hover:underline">
        Перейти в каталог программ
      </Link>
    </div>
  );
}
