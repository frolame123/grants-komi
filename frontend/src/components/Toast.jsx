/**
 * Всплывающие уведомления о результате действия.
 *
 * Сообщение исчезает через пять секунд само, но остаётся закрываемым
 * вручную. Область объявлена как aria-live: экранный диктор прочитает
 * сообщение, не уводя фокус с текущего элемента.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const ToastContext = createContext(null);

const LIFETIME_MS = 5000;

const STYLES = {
  success: "border-success/40 bg-success/10 text-success",
  error: "border-alert/40 bg-alert/10 text-alert",
  info: "border-line bg-surface text-ink",
};

let nextId = 1;

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);

  const dismiss = useCallback((id) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const show = useCallback((message, kind = "info") => {
    const id = nextId++;
    setItems((current) => [...current, { id, message, kind }]);
    return id;
  }, []);

  const value = useMemo(
    () => ({
      show,
      success: (message) => show(message, "success"),
      error: (message) => show(message, "error"),
    }),
    [show],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4"
        aria-live="polite"
      >
        {items.map((item) => (
          <ToastItem key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ item, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(item.id), LIFETIME_MS);
    return () => clearTimeout(timer);
  }, [item.id, onDismiss]);

  return (
    <div
      className={`pointer-events-auto flex w-full max-w-md items-start gap-3 rounded border px-4 py-3 text-sm shadow-sm ${STYLES[item.kind]}`}
      role="status"
    >
      <span className="flex-1">{item.message}</span>
      <button
        type="button"
        onClick={() => onDismiss(item.id)}
        className="shrink-0 opacity-60 transition-opacity hover:opacity-100"
        aria-label="Закрыть уведомление"
      >
        ✕
      </button>
    </div>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast вызван вне ToastProvider");
  return context;
}
