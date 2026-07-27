-- =====================================================================
--  Информационная система «Гранты Коми»
--  Агрегация и подбор мер грантовой поддержки для субъектов МСП и НКО
--  Республики Коми
--
--  СУБД: PostgreSQL 16
--  Даталогическая модель, 3-я нормальная форма
--
--  Стандарт именования (style_sheet):
--    - имена таблиц       : единственное число, snake_case, нижний регистр
--    - имена полей        : snake_case, нижний регистр
--    - первичные ключи    : pk_<таблица>
--    - внешние ключи      : fk_<таблица>_<поле>
--    - ограничения CHECK  : chk_<таблица>_<поле>
--    - ограничения UNIQUE : uniq_<таблица>_<поля>
--    - индексы            : idx_<таблица>_<поля>
--
--  Примечание: таблица пользователей названа app_user, поскольку
--  идентификатор user является зарезервированным словом в PostgreSQL.
--
--  Версия 2 — по замечаниям технического ревью (Ельцов М.Е.):
--    1. Добавлены таблицы email_confirmation_token и
--       password_reset_token для FR-002 / FR-009 (были невозможны
--       без хранения токена и срока его действия).
--    2. В app_user добавлено поле pd_consent_at — фиксация факта и
--       времени согласия на обработку персональных данных (152-ФЗ,
--       FR-001), а также deleted_at — отметка обезличивания записи.
--    3. Добавлена функция fn_anonymize_user — мягкое удаление
--       (обезличивание) учётной записи вместо физического удаления,
--       требуемое 152-ФЗ (FR-013).
--    4. В audit_log добавлено поле ip_address — фиксация адреса,
--       с которого выполнено действие.
--    5. Добавлены комментарии COMMENT ON для всех таблиц и ключевых
--       полей, включая пометку полей, содержащих персональные данные.
--    6. Проверка формата email усилена: регулярное выражение вместо
--       LIKE.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. Очистка (для повторного запуска скрипта)
-- ---------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_anonymize_user(INTEGER);
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS notification CASCADE;
DROP TABLE IF EXISTS moderation_queue CASCADE;
DROP TABLE IF EXISTS application CASCADE;
DROP TABLE IF EXISTS favorite CASCADE;
DROP TABLE IF EXISTS program_applicant_type CASCADE;
DROP TABLE IF EXISTS program CASCADE;
DROP TABLE IF EXISTS category CASCADE;
DROP TABLE IF EXISTS source CASCADE;
DROP TABLE IF EXISTS org_profile CASCADE;
DROP TABLE IF EXISTS password_reset_token CASCADE;
DROP TABLE IF EXISTS email_confirmation_token CASCADE;
DROP TABLE IF EXISTS app_user CASCADE;


-- =====================================================================
-- 1. СОЗДАНИЕ ТАБЛИЦ
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1.1. app_user — пользователь системы (стержневая сущность)
-- ---------------------------------------------------------------------
CREATE TABLE app_user (
    user_id        SERIAL       NOT NULL,
    email          VARCHAR(255) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(20)  NOT NULL DEFAULT 'applicant',
    status         VARCHAR(20)  NOT NULL DEFAULT 'pending',
    pd_consent_at  TIMESTAMP WITH TIME ZONE,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at     TIMESTAMP WITH TIME ZONE,
    CONSTRAINT pk_app_user PRIMARY KEY (user_id),
    CONSTRAINT uniq_app_user_email UNIQUE (email),
    -- усиленная проверка формата адреса эл. почты (регулярное выражение вместо LIKE)
    CONSTRAINT chk_app_user_email
        CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_app_user_role
        CHECK (role IN ('guest', 'applicant', 'moderator', 'admin')),
    CONSTRAINT chk_app_user_status
        CHECK (status IN ('pending', 'active', 'blocked'))
);

COMMENT ON TABLE app_user IS 'Пользователь системы (стержневая сущность)';
COMMENT ON COLUMN app_user.user_id IS 'Первичный ключ пользователя';
COMMENT ON COLUMN app_user.email IS 'Логин и адрес для уведомлений; персональные данные (152-ФЗ)';
COMMENT ON COLUMN app_user.password_hash IS 'Хэш пароля (bcrypt); хранение пароля в открытом виде запрещено';
COMMENT ON COLUMN app_user.role IS 'Роль в ролевой модели: guest, applicant, moderator, admin';
COMMENT ON COLUMN app_user.status IS 'Состояние учётной записи: pending, active, blocked';
COMMENT ON COLUMN app_user.pd_consent_at IS
    'Персональные данные: дата и время получения явного согласия на обработку ПД (152-ФЗ, FR-001); NULL — согласие не получено';
COMMENT ON COLUMN app_user.created_at IS 'Дата и время регистрации';
COMMENT ON COLUMN app_user.deleted_at IS
    'Дата и время обезличивания учётной записи функцией fn_anonymize_user (FR-013); NULL — запись активна';

-- ---------------------------------------------------------------------
-- 1.2. email_confirmation_token — токен подтверждения email (FR-002)
--      Зависимая сущность: не существует без app_user
-- ---------------------------------------------------------------------
CREATE TABLE email_confirmation_token (
    token_id    SERIAL       NOT NULL,
    user_id     INTEGER      NOT NULL,
    token       VARCHAR(255) NOT NULL,
    expires_at  TIMESTAMP    NOT NULL,
    used        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_email_confirmation_token PRIMARY KEY (token_id),
    CONSTRAINT fk_email_confirmation_token_user_id FOREIGN KEY (user_id)
        REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT uniq_email_confirmation_token_token UNIQUE (token)
);

COMMENT ON TABLE email_confirmation_token IS
    'Токены подтверждения адреса эл. почты, срок действия 24 часа (FR-002)';
COMMENT ON COLUMN email_confirmation_token.token IS 'Значение токена, отправляемое пользователю по email';
COMMENT ON COLUMN email_confirmation_token.expires_at IS 'Момент истечения срока действия токена (created_at + 24 часа)';
COMMENT ON COLUMN email_confirmation_token.used IS 'Признак того, что токен уже был использован (повторное использование запрещено)';

-- ---------------------------------------------------------------------
-- 1.3. password_reset_token — токен восстановления пароля (FR-009)
--      Зависимая сущность: не существует без app_user
-- ---------------------------------------------------------------------
CREATE TABLE password_reset_token (
    token_id    SERIAL       NOT NULL,
    user_id     INTEGER      NOT NULL,
    token       VARCHAR(255) NOT NULL,
    expires_at  TIMESTAMP    NOT NULL,
    used        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_password_reset_token PRIMARY KEY (token_id),
    CONSTRAINT fk_password_reset_token_user_id FOREIGN KEY (user_id)
        REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT uniq_password_reset_token_token UNIQUE (token)
);

COMMENT ON TABLE password_reset_token IS
    'Токены восстановления пароля, срок действия 1 час (FR-009)';
COMMENT ON COLUMN password_reset_token.token IS 'Значение токена, отправляемое пользователю по email';
COMMENT ON COLUMN password_reset_token.expires_at IS 'Момент истечения срока действия токена (created_at + 1 час)';
COMMENT ON COLUMN password_reset_token.used IS 'Признак того, что токен уже был использован (повторное использование запрещено)';

-- ---------------------------------------------------------------------
-- 1.4. org_profile — профиль организации (характеристическая сущность)
--      Связь 1:1 с app_user обеспечивается ограничением UNIQUE на user_id
-- ---------------------------------------------------------------------
CREATE TABLE org_profile (
    profile_id  SERIAL       NOT NULL,
    user_id     INTEGER      NOT NULL,
    org_type    VARCHAR(10)  NOT NULL,
    inn         VARCHAR(12)  NOT NULL,
    city        VARCHAR(100) NOT NULL,
    street      VARCHAR(150),
    house       VARCHAR(20),
    org_size    VARCHAR(20),
    goal        VARCHAR(300),
    region      VARCHAR(100) NOT NULL DEFAULT 'Республика Коми',
    CONSTRAINT pk_org_profile PRIMARY KEY (profile_id),
    CONSTRAINT fk_org_profile_user_id FOREIGN KEY (user_id)
        REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT uniq_org_profile_user_id UNIQUE (user_id),
    CONSTRAINT uniq_org_profile_inn UNIQUE (inn),
    CONSTRAINT chk_org_profile_org_type
        CHECK (org_type IN ('IP', 'OOO', 'NKO', 'SMZ')),
    -- ИНН: 10 цифр для юридического лица, 12 — для ИП и самозанятого
    CONSTRAINT chk_org_profile_inn CHECK (
        (org_type = 'OOO' AND inn ~ '^[0-9]{10}$')
        OR (org_type IN ('IP', 'NKO', 'SMZ') AND inn ~ '^[0-9]{12}$')
    ),
    CONSTRAINT chk_org_profile_org_size
        CHECK (org_size IS NULL OR org_size IN ('micro', 'small', 'medium'))
);

COMMENT ON TABLE org_profile IS 'Профиль организации-заявителя (характеристическая сущность, связь 1:1 с app_user)';
COMMENT ON COLUMN org_profile.org_type IS 'Организационно-правовая форма: IP, OOO, NKO, SMZ';
COMMENT ON COLUMN org_profile.inn IS
    'Идентификационный номер налогоплательщика. Персональные данные для ИП и самозанятых (152-ФЗ): доступ ограничивается ролью владельца записи и администратора, шифрование/маскирование обеспечивается на уровне приложения';
COMMENT ON COLUMN org_profile.city IS 'Составная часть адреса организации: город';
COMMENT ON COLUMN org_profile.street IS 'Составная часть адреса организации: улица';
COMMENT ON COLUMN org_profile.house IS 'Составная часть адреса организации: дом';
COMMENT ON COLUMN org_profile.org_size IS 'Размер субъекта МСП: micro, small, medium или NULL';
COMMENT ON COLUMN org_profile.goal IS 'Цель финансирования, используется при подборе программ';

-- ---------------------------------------------------------------------
-- 1.5. source — источник сведений (обозначающая / справочная сущность)
-- ---------------------------------------------------------------------
CREATE TABLE source (
    source_id  SERIAL       NOT NULL,
    name       VARCHAR(150) NOT NULL,
    url        VARCHAR(500) NOT NULL,
    schedule   VARCHAR(50)  NOT NULL DEFAULT 'daily',
    CONSTRAINT pk_source PRIMARY KEY (source_id),
    CONSTRAINT uniq_source_name UNIQUE (name),
    CONSTRAINT chk_source_url CHECK (url LIKE 'http%')
);

COMMENT ON TABLE source IS 'Источник сведений о программах поддержки (обозначающая / справочная сущность)';
COMMENT ON COLUMN source.name IS 'Наименование источника';
COMMENT ON COLUMN source.url IS 'Адрес источника для агрегации';
COMMENT ON COLUMN source.schedule IS 'Периодичность опроса источника парсером: daily, weekly';

-- ---------------------------------------------------------------------
-- 1.6. category — категория программы (обозначающая сущность)
-- ---------------------------------------------------------------------
CREATE TABLE category (
    category_id  SERIAL       NOT NULL,
    name         VARCHAR(100) NOT NULL,
    CONSTRAINT pk_category PRIMARY KEY (category_id),
    CONSTRAINT uniq_category_name UNIQUE (name)
);

COMMENT ON TABLE category IS 'Категория программы поддержки (обозначающая сущность)';
COMMENT ON COLUMN category.name IS 'Наименование категории';

-- ---------------------------------------------------------------------
-- 1.7. program — программа грантовой поддержки (стержневая сущность)
-- ---------------------------------------------------------------------
CREATE TABLE program (
    program_id       SERIAL         NOT NULL,
    source_id        INTEGER        NOT NULL,
    category_id      INTEGER,
    title            VARCHAR(300)   NOT NULL,
    organizer        VARCHAR(200)   NOT NULL,
    amount           NUMERIC(12, 2),
    deadline         DATE,
    status           VARCHAR(10)    NOT NULL DEFAULT 'DRAFT',
    extra_json       JSONB          NOT NULL DEFAULT '{}'::jsonb,
    content_hash     CHAR(64)       NOT NULL,
    last_checked_at  TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_url       VARCHAR(500)   NOT NULL,
    CONSTRAINT pk_program PRIMARY KEY (program_id),
    CONSTRAINT fk_program_source_id FOREIGN KEY (source_id)
        REFERENCES source (source_id) ON DELETE RESTRICT,
    CONSTRAINT fk_program_category_id FOREIGN KEY (category_id)
        REFERENCES category (category_id) ON DELETE SET NULL,
    CONSTRAINT uniq_program_source_url UNIQUE (source_id, source_url),
    CONSTRAINT chk_program_status
        CHECK (status IN ('DRAFT', 'MOD', 'PUB', 'ARCH')),
    CONSTRAINT chk_program_amount CHECK (amount IS NULL OR amount > 0),
    -- опубликованная программа обязана иметь категорию и срок подачи
    CONSTRAINT chk_program_published CHECK (
        status <> 'PUB' OR (category_id IS NOT NULL AND deadline IS NOT NULL)
    )
);

COMMENT ON TABLE program IS 'Программа грантовой поддержки (стержневая сущность)';
COMMENT ON COLUMN program.title IS 'Наименование программы';
COMMENT ON COLUMN program.organizer IS 'Организатор (грантодатель)';
COMMENT ON COLUMN program.amount IS 'Максимальная сумма гранта, руб.';
COMMENT ON COLUMN program.deadline IS 'Дата окончания приёма заявок; обязательна при status = PUB';
COMMENT ON COLUMN program.status IS 'Состояние карточки программы: DRAFT, MOD, PUB, ARCH';
COMMENT ON COLUMN program.extra_json IS 'Дополнительные условия программы, состав которых различается у разных источников';
COMMENT ON COLUMN program.content_hash IS 'Хэш содержимого (SHA-256) для выявления изменений при повторном опросе источника';
COMMENT ON COLUMN program.last_checked_at IS 'Время последней проверки парсером; используется для контроля свежести (не старше 24 часов)';
COMMENT ON COLUMN program.source_url IS 'Ссылка на первоисточник записи';

-- ---------------------------------------------------------------------
-- 1.8. program_applicant_type — типы заявителей программы
--      (реализация многозначного атрибута applicant_type; 1НФ)
-- ---------------------------------------------------------------------
CREATE TABLE program_applicant_type (
    program_id      INTEGER     NOT NULL,
    applicant_type  VARCHAR(10) NOT NULL,
    CONSTRAINT pk_program_applicant_type
        PRIMARY KEY (program_id, applicant_type),
    CONSTRAINT fk_program_applicant_type_program_id FOREIGN KEY (program_id)
        REFERENCES program (program_id) ON DELETE CASCADE,
    CONSTRAINT chk_program_applicant_type_applicant_type
        CHECK (applicant_type IN ('IP', 'OOO', 'NKO', 'SMZ'))
);

COMMENT ON TABLE program_applicant_type IS
    'Типы заявителей программы (реализация многозначного атрибута applicant_type сущности PROGRAM, 1НФ)';

-- ---------------------------------------------------------------------
-- 1.9. favorite — избранное (ассоциативная сущность, M:N)
-- ---------------------------------------------------------------------
CREATE TABLE favorite (
    favorite_id  SERIAL    NOT NULL,
    user_id      INTEGER   NOT NULL,
    program_id   INTEGER   NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_favorite PRIMARY KEY (favorite_id),
    CONSTRAINT fk_favorite_user_id FOREIGN KEY (user_id)
        REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_favorite_program_id FOREIGN KEY (program_id)
        REFERENCES program (program_id) ON DELETE CASCADE,
    CONSTRAINT uniq_favorite_user_id_program_id UNIQUE (user_id, program_id)
);

COMMENT ON TABLE favorite IS 'Избранные программы пользователя (ассоциативная сущность M:N между APP_USER и PROGRAM)';

-- ---------------------------------------------------------------------
-- 1.10. application — заявка (ассоциативная сущность, M:N)
-- ---------------------------------------------------------------------
CREATE TABLE application (
    application_id  SERIAL      NOT NULL,
    user_id         INTEGER     NOT NULL,
    program_id      INTEGER     NOT NULL,
    status          VARCHAR(10) NOT NULL DEFAULT 'DRAFT',
    status_date     DATE        NOT NULL DEFAULT CURRENT_DATE,
    result          VARCHAR(10),
    CONSTRAINT pk_application PRIMARY KEY (application_id),
    CONSTRAINT fk_application_user_id FOREIGN KEY (user_id)
        REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_application_program_id FOREIGN KEY (program_id)
        REFERENCES program (program_id) ON DELETE CASCADE,
    CONSTRAINT uniq_application_user_id_program_id UNIQUE (user_id, program_id),
    CONSTRAINT chk_application_status
        CHECK (status IN ('DRAFT', 'PREP', 'SENT', 'RES')),
    CONSTRAINT chk_application_result
        CHECK (result IS NULL OR result IN ('APPROVED', 'REJECTED')),
    -- результат допустим только в статусе RES, и наоборот
    CONSTRAINT chk_application_result_status CHECK (
        (status = 'RES' AND result IS NOT NULL)
        OR (status <> 'RES' AND result IS NULL)
    )
);

COMMENT ON TABLE application IS 'Заявка на участие в программе (ассоциативная сущность M:N между APP_USER и PROGRAM)';
COMMENT ON COLUMN application.status IS 'Текущий статус заявки: DRAFT, PREP, SENT, RES';
COMMENT ON COLUMN application.status_date IS 'Дата последнего перехода статуса';
COMMENT ON COLUMN application.result IS 'Результат рассмотрения: APPROVED, REJECTED; NULL при status <> RES';

-- ---------------------------------------------------------------------
-- 1.11. moderation_queue — очередь модерации (слабая сущность)
-- ---------------------------------------------------------------------
CREATE TABLE moderation_queue (
    queue_id     SERIAL      NOT NULL,
    program_id   INTEGER     NOT NULL,
    change_type  VARCHAR(10) NOT NULL,
    status       VARCHAR(15) NOT NULL DEFAULT 'waiting',
    created_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_moderation_queue PRIMARY KEY (queue_id),
    CONSTRAINT fk_moderation_queue_program_id FOREIGN KEY (program_id)
        REFERENCES program (program_id) ON DELETE CASCADE,
    CONSTRAINT chk_moderation_queue_change_type
        CHECK (change_type IN ('NEW', 'UPD')),
    CONSTRAINT chk_moderation_queue_status
        CHECK (status IN ('waiting', 'approved', 'rejected'))
);

COMMENT ON TABLE moderation_queue IS 'Очередь модерации изменений программ (зависимая / слабая сущность от PROGRAM)';
COMMENT ON COLUMN moderation_queue.change_type IS 'Тип изменения: NEW (новая запись), UPD (изменение существующей)';
COMMENT ON COLUMN moderation_queue.status IS 'Состояние рассмотрения: waiting, approved, rejected';

-- ---------------------------------------------------------------------
-- 1.12. notification — уведомление (слабая сущность)
-- ---------------------------------------------------------------------
CREATE TABLE notification (
    notification_id  SERIAL      NOT NULL,
    user_id          INTEGER     NOT NULL,
    program_id       INTEGER     NOT NULL,
    type             VARCHAR(10) NOT NULL,
    sent_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_read          BOOLEAN     NOT NULL DEFAULT FALSE,
    CONSTRAINT pk_notification PRIMARY KEY (notification_id),
    CONSTRAINT fk_notification_user_id FOREIGN KEY (user_id)
        REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_notification_program_id FOREIGN KEY (program_id)
        REFERENCES program (program_id) ON DELETE CASCADE,
    CONSTRAINT chk_notification_type
        CHECK (type IN ('DL7', 'DL1', 'NEWP')),
    -- одно уведомление данного типа по программе на пользователя
    CONSTRAINT uniq_notification_user_id_program_id_type
        UNIQUE (user_id, program_id, type)
);

COMMENT ON TABLE notification IS 'Уведомление пользователя о программе (зависимая / слабая сущность от пары APP_USER — PROGRAM)';
COMMENT ON COLUMN notification.type IS 'Тип уведомления: DL7 (за 7 дней), DL1 (за 1 день), NEWP (новая программа)';
COMMENT ON COLUMN notification.is_read IS 'Отметка о прочтении уведомления пользователем';

-- ---------------------------------------------------------------------
-- 1.13. audit_log — журнал аудита (слабая сущность)
-- ---------------------------------------------------------------------
CREATE TABLE audit_log (
    audit_id    SERIAL      NOT NULL,
    user_id     INTEGER,
    action      VARCHAR(50) NOT NULL,
    entity      VARCHAR(50) NOT NULL,
    entity_id   INTEGER,
    ip_address  VARCHAR(45),
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_audit_log PRIMARY KEY (audit_id),
    CONSTRAINT fk_audit_log_user_id FOREIGN KEY (user_id)
        REFERENCES app_user (user_id) ON DELETE SET NULL,
    CONSTRAINT chk_audit_log_action CHECK (
        action IN ('login', 'logout', 'password_reset',
                   'role_change', 'program_publish', 'program_archive',
                   'account_delete')
    )
);

COMMENT ON TABLE audit_log IS 'Журнал аудита действий пользователей (зависимая / слабая сущность от APP_USER)';
COMMENT ON COLUMN audit_log.action IS 'Зафиксированное действие: login, logout, password_reset, role_change, program_publish, program_archive, account_delete';
COMMENT ON COLUMN audit_log.entity IS 'Тип объекта, над которым совершено действие';
COMMENT ON COLUMN audit_log.entity_id IS 'Идентификатор объекта, над которым совершено действие';
COMMENT ON COLUMN audit_log.ip_address IS 'IP-адрес, с которого выполнено действие (IPv4/IPv6)';


-- =====================================================================
-- 2. ФУНКЦИЯ МЯГКОГО УДАЛЕНИЯ (ОБЕЗЛИЧИВАНИЯ) УЧЁТНОЙ ЗАПИСИ
-- =====================================================================
-- Реализует FR-013 (152-ФЗ): по запросу пользователя система удаляет
-- профиль организации, избранное и уведомления, а также обезличивает
-- саму учётную запись (email и пароль заменяются на нечитаемые
-- значения, устанавливается deleted_at). Запись app_user не удаляется
-- физически, чтобы сохранить ссылочную целостность журнала аудита без
-- обнуления истории её же действий.
CREATE OR REPLACE FUNCTION fn_anonymize_user(p_user_id INTEGER)
RETURNS VOID AS $$
BEGIN
    DELETE FROM favorite WHERE user_id = p_user_id;
    DELETE FROM notification WHERE user_id = p_user_id;
    DELETE FROM application WHERE user_id = p_user_id;
    DELETE FROM org_profile WHERE user_id = p_user_id;
    DELETE FROM email_confirmation_token WHERE user_id = p_user_id;
    DELETE FROM password_reset_token WHERE user_id = p_user_id;

    UPDATE app_user
    SET email         = 'deleted-' || p_user_id || '@anonymized.local',
        password_hash = '$deleted$',
        status        = 'blocked',
        deleted_at    = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id;

    INSERT INTO audit_log (user_id, action, entity, entity_id)
    VALUES (p_user_id, 'account_delete', 'app_user', p_user_id);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fn_anonymize_user(INTEGER) IS
    'Мягкое удаление (обезличивание) учётной записи пользователя по 152-ФЗ (FR-013)';


-- =====================================================================
-- 3. ИНДЕКСЫ
-- =====================================================================
-- Поля, наиболее часто используемые в поиске и фильтрации (раздел 4.2 ТЗ)
CREATE INDEX idx_program_status         ON program (status);
CREATE INDEX idx_program_deadline       ON program (deadline);
CREATE INDEX idx_program_category_id    ON program (category_id);
CREATE INDEX idx_program_source_id      ON program (source_id);
CREATE INDEX idx_program_extra_json     ON program USING GIN (extra_json);

CREATE INDEX idx_application_user_id    ON application (user_id);
CREATE INDEX idx_application_status     ON application (status);
CREATE INDEX idx_favorite_user_id       ON favorite (user_id);
CREATE INDEX idx_notification_user_id   ON notification (user_id, is_read);
CREATE INDEX idx_moderation_queue_status ON moderation_queue (status);
CREATE INDEX idx_audit_log_created_at   ON audit_log (created_at);

CREATE INDEX idx_email_confirmation_token_user_id
    ON email_confirmation_token (user_id);
CREATE INDEX idx_password_reset_token_user_id
    ON password_reset_token (user_id);
