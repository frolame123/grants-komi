/**
 * Перехват необработанных ошибок интерфейса (пункт 5.5 требований).
 *
 * Без него сбой в любом компоненте оставляет пользователя перед пустым белым
 * экраном без единого объяснения. Страница показывает, что делать дальше, и
 * даёт способ связаться с поддержкой.
 */

import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error("Сбой интерфейса:", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="mb-2 text-5xl font-light text-line">500</p>
        <h1 className="mb-2 text-xl font-semibold">Технические работы</h1>
        <p className="mb-6 text-sm text-ink-soft">
          Страница не отобразилась из-за ошибки. Мы уже знаем о ней. Попробуйте
          обновить страницу — если не поможет, напишите в поддержку.
        </p>

        <div className="flex flex-wrap justify-center gap-2">
          <button
            type="button"
            className="btn-primary"
            onClick={() => window.location.reload()}
          >
            Обновить страницу
          </button>
          <a className="btn-secondary" href="mailto:support@grantykomi.ru">
            Написать в поддержку
          </a>
        </div>
      </div>
    );
  }
}
