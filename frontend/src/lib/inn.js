/**
 * Проверка ИНН по алгоритму контрольного числа ФНС.
 *
 * Повторяет app/inn.py на сервере. Дублирование здесь осознанное: клиентская
 * проверка показывает опечатку мгновенно, серверная остаётся единственной
 * защитой, поскольку клиент можно обойти прямым запросом к API.
 */

const WEIGHTS_10 = [2, 4, 10, 3, 5, 9, 4, 6, 8];
const WEIGHTS_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8];
const WEIGHTS_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8];

const LENGTH_BY_TYPE = { OOO: 10, IP: 12, NKO: 12, SMZ: 12 };

function controlDigit(digits, weights) {
  const sum = weights.reduce((total, weight, index) => total + weight * Number(digits[index]), 0);
  return (sum % 11) % 10;
}

/** Возвращает текст ошибки или null, если ИНН корректен. */
export function validateInn(inn, orgType) {
  if (!/^\d+$/.test(inn)) return "ИНН должен содержать только цифры";

  const expected = LENGTH_BY_TYPE[orgType];
  if (!expected) return "Выберите тип организации";
  if (inn.length !== expected) return `ИНН должен содержать ${expected} цифр`;

  const valid =
    expected === 10
      ? controlDigit(inn, WEIGHTS_10) === Number(inn[9])
      : controlDigit(inn, WEIGHTS_11) === Number(inn[10]) &&
        controlDigit(inn, WEIGHTS_12) === Number(inn[11]);

  return valid ? null : "Неверный ИНН: контрольное число не сходится";
}
