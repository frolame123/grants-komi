-- Тестовые данные (разделы 4.x исходного скрипта grants_db_v2.sql)

-- ---------------------------------------------------------------------
-- 0. Очистка перед наполнением
--
-- Записи ссылаются друг на друга по номерам (профиль на пользователя 1,
-- программа на источник 2 и так далее), поэтому счётчики идентификаторов
-- обязаны начинаться с единицы. Обычное DELETE их не сбрасывает, а откат
-- неудачной транзакции — тем более: последовательности в PostgreSQL живут
-- вне транзакций. TRUNCATE ... RESTART IDENTITY делает скрипт повторяемым.
-- ---------------------------------------------------------------------
TRUNCATE TABLE
    audit_log, notification, moderation_queue, application_history, application,
    favorite, program_region, program_applicant_type, program, category, source,
    org_profile, password_reset_token, email_confirmation_token, refresh_token,
    app_user
RESTART IDENTITY CASCADE;

-- 4. НАПОЛНЕНИЕ ТЕСТОВЫМИ ДАННЫМИ
-- =====================================================================

-- 4.1. Пользователи: разные роли и статусы, разное состояние согласия на ПД
INSERT INTO app_user (email, password_hash, role, status, pd_consent_at) VALUES
    ('ivanov@sever-service.ru', '$2b$12$Xk3mQeR7uPvA1sD9fGh2Ie', 'applicant', 'active', '2026-06-01 10:15:00+03'),
    ('nko.parma@mail.ru',       '$2b$12$Lp8nWzY4tRcB2eF6gHj3Ko', 'applicant', 'active', '2026-06-02 11:20:00+03'),
    ('petrova@komi-eco.ru',     '$2b$12$Qr5vBnM1yUdC3hJ7kLm9Np', 'applicant', 'pending', NULL),
    ('moderator@grantykomi.ru', '$2b$12$Zs9cVbN6xEwD4gK8lPq2Rt', 'moderator', 'active', '2026-05-20 09:00:00+03'),
    ('admin@grantykomi.ru',     '$2b$12$Yt2dCxZ8wQaE5jL1mNr4Su', 'admin',     'active', '2026-05-20 09:00:00+03');

-- 4.2. Профили организаций: разные типы (ООО — 10 цифр, прочие — 12).
--      Контрольные числа ИНН пересчитаны по алгоритму ФНС: база проверяет
--      только длину, а приложение — контрольное число (FR-003)
--      Отрасль профиля назначается ниже, в разделе 4.4.1: справочник
--      категорий наполняется позже профилей
INSERT INTO org_profile (user_id, org_type, inn, city, street, house, org_size, goal) VALUES
    (1, 'OOO', '1101234568', 'Сыктывкар', 'ул. Коммунистическая', '25',  'small',
     'Закупка оборудования для мастерской'),
    (2, 'NKO', '110987654350', 'Ухта',      'ул. Мира',             '14а', 'micro',
     'Проведение фестиваля финно-угорской культуры'),
    (3, 'IP',  '110555666750', 'Воркута',   'ул. Ленина',           '7',   'micro',
     'Развитие пункта приёма дикоросов'),
    (4, 'SMZ', '110111222311', 'Печора',    'ул. Советская',        '3',   NULL,
     'Продвижение ремесленной продукции');

-- 4.3. Источники сведений
INSERT INTO source (name, url, schedule) VALUES
    ('Минэкономразвития Республики Коми', 'https://econom.rkomi.ru/', 'daily'),
    ('Фонд «Агентство регионального развития»', 'https://arrkomi.ru/', 'daily'),
    ('Цифровая платформа МСП.РФ', 'https://мсп.рф/', 'weekly'),
    ('Фонд президентских грантов', 'https://президентскиегранты.рф/', 'weekly');

-- 4.4. Категории программ
INSERT INTO category (name) VALUES
    ('Социальное предпринимательство'),
    ('Развитие производства'),
    ('Культура и творчество'),
    ('Экология и природопользование'),
    ('Молодёжные инициативы');

-- 4.4.1. Отрасль профилей организаций (колонка добавлена миграцией 0003)
--        Без заполненной отрасли персональный подбор недоступен: FR-005
--        требует её как обязательное условие и начисляет 40 баллов за
--        совпадение с категорией программы
UPDATE org_profile SET category_id = 1 WHERE user_id = 1;  -- социальное предпринимательство
UPDATE org_profile SET category_id = 3 WHERE user_id = 2;  -- культура и творчество
UPDATE org_profile SET category_id = 4 WHERE user_id = 3;  -- экология
UPDATE org_profile SET category_id = 5 WHERE user_id = 4;  -- молодёжные инициативы

-- 4.5. Программы: разные источники, категории и статусы
INSERT INTO program
    (source_id, category_id, title, organizer, amount, deadline, status,
     extra_json, content_hash, source_url)
VALUES
    (1, 1, 'Грант на развитие социального предпринимательства',
     'Минэкономразвития Республики Коми', 500000.00, DATE '2026-09-15', 'PUB',
     '{"co_financing": "не требуется", "reporting": "ежеквартально"}'::jsonb,
     'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
     'https://econom.rkomi.ru/grants/social-2026'),

    (2, 2, 'Субсидия на модернизацию оборудования',
     'Фонд «Агентство регионального развития»', 1000000.00, DATE '2026-10-01', 'PUB',
     '{"co_financing": "20%", "min_employees": 5}'::jsonb,
     'b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1',
     'https://arrkomi.ru/support/modernization-2026'),

    (4, 3, 'Президентский грант на культурные проекты',
     'Фонд президентских грантов', 3000000.00, DATE '2026-11-20', 'PUB',
     '{"co_financing": "10%", "project_duration_months": 12}'::jsonb,
     'c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2',
     'https://президентскиегранты.рф/public/application/2026-culture'),

    (3, 4, 'Поддержка экологических инициатив МСП',
     'Цифровая платформа МСП.РФ', 750000.00, DATE '2026-08-30', 'MOD',
     '{"co_financing": "не требуется"}'::jsonb,
     'd4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3',
     'https://мсп.рф/services/eco-2026'),

    (1, 5, 'Грант молодым предпринимателям (конкурс 2025 года)',
     'Минэкономразвития Республики Коми', 250000.00, DATE '2025-12-01', 'ARCH',
     '{"age_limit": 35}'::jsonb,
     'e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4',
     'https://econom.rkomi.ru/grants/youth-2025');

-- 4.6. Типы заявителей программ (многозначный атрибут)
INSERT INTO program_applicant_type (program_id, applicant_type) VALUES
    (1, 'IP'),  (1, 'OOO'),
    (2, 'OOO'),
    (3, 'NKO'),
    (4, 'IP'),  (4, 'OOO'), (4, 'NKO'),
    (5, 'IP'),  (5, 'SMZ');

-- 4.6.1. Регионы действия программ (многозначный атрибут, миграция 0003)
--        Используется при подборе: совпадение региона даёт 30 баллов (FR-005)
INSERT INTO program_region (program_id, region) VALUES
    (1, 'Республика Коми'),
    (2, 'Республика Коми'),
    (3, 'Республика Коми'), (3, 'Российская Федерация'),
    (4, 'Республика Коми'),
    (5, 'Республика Коми');

-- 4.7. Избранное
INSERT INTO favorite (user_id, program_id) VALUES
    (1, 1),
    (1, 2),
    (2, 3),
    (3, 4);

-- 4.8. Заявки: все статусы статусной модели, результат только для RES
INSERT INTO application (user_id, program_id, status, status_date, result) VALUES
    (1, 1, 'SENT', DATE '2026-07-05', NULL),
    (1, 2, 'PREP', DATE '2026-07-08', NULL),
    (2, 3, 'RES',  DATE '2026-06-30', 'APPROVED'),
    (3, 4, 'DRAFT', DATE '2026-07-09', NULL),
    (2, 1, 'RES',  DATE '2026-06-15', 'REJECTED');

-- 4.9. Очередь модерации: новые и изменённые записи
--      Причина отклонения обязательна при статусе rejected, снимок прежнего
--      состояния даёт представление «было / стало» (миграция 0008)
INSERT INTO moderation_queue (program_id, change_type, status, reason, prev_snapshot)
VALUES
    (4, 'NEW', 'waiting', NULL, NULL),
    (2, 'UPD', 'waiting', NULL,
     '{"title": "Субсидия на модернизацию оборудования",
       "organizer": "Фонд «Агентство регионального развития»",
       "amount": "800000.00", "deadline": "2026-10-01",
       "applicant_types": ["OOO"], "category_id": 2,
       "source_url": "https://arrkomi.ru/support/modernization-2026"}'::jsonb),
    (1, 'UPD', 'approved', NULL, NULL),
    (5, 'UPD', 'rejected',
     'Срок подачи не определён в первоисточнике, требуется уточнение у организатора',
     NULL);

-- 4.10. Уведомления: разные типы, прочитанные и нет
INSERT INTO notification (user_id, program_id, type, is_read) VALUES
    (1, 1, 'DL7',  TRUE),
    (1, 1, 'DL1',  FALSE),
    (2, 3, 'DL7',  FALSE),
    (3, 4, 'NEWP', FALSE);

-- 4.11. Журнал аудита: действия разных ролей, с указанием IP
INSERT INTO audit_log (user_id, action, entity, entity_id, ip_address) VALUES
    (1, 'login',           'app_user', 1, '95.24.11.8'),
    (4, 'program_publish', 'program',  1, '10.20.0.14'),
    (4, 'program_archive', 'program',  5, '10.20.0.14'),
    (5, 'role_change',     'app_user', 4, '10.20.0.5'),
    (2, 'password_reset',  'app_user', 2, '178.66.4.201');

-- 4.12. Токены подтверждения email: непросроченный и уже использованный
INSERT INTO email_confirmation_token (user_id, token, expires_at, used) VALUES
    (3, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85', CURRENT_TIMESTAMP + INTERVAL '24 hours', FALSE),
    (1, '4d967a30111bf29f0eba01c448b375c1629b2fed01cdfcd3fded20d0efc8807', CURRENT_TIMESTAMP - INTERVAL '10 days', TRUE);

-- 4.13. Токены восстановления пароля: активный и просроченный
INSERT INTO password_reset_token (user_id, token, expires_at, used) VALUES
    (2, '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08', CURRENT_TIMESTAMP + INTERVAL '1 hour', FALSE),
    (1, '2c624232cdd221771294dfbb310aca000a0df6ac8b66b696d90ef06fdefb64a', CURRENT_TIMESTAMP - INTERVAL '2 hours', FALSE);
