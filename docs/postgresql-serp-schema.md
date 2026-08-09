# PostgreSQL: схема `serp`

Этот справочник описывает данные публичной поисковой выдачи Wildberries,
которые сборщик `wb_serp` сохраняет в PostgreSQL. Источник истины для структуры
— `wb_serp/postgres.py`; изменения DDL должны сопровождаться обновлением этого
файла.

## Жизненный цикл данных

- Полный рыночный снимок начинается в `05:00`, `11:00`, `17:00` и `23:00`
  часового пояса `Asia/Yekaterinburg`.
- Все пятиминутные попытки внутри одного шестичасового окна используют общий
  `batch_id` и одни page-checkpoints.
- Повторный запуск пропускает сохранённые страницы и запрашивает только
  отсутствующие.
- В `serp.attempts` попадают только запуски, которые действительно обратились
  к WB. Ожидание нового curl, занятый advisory lock и уже завершённый батч не
  создают попытку.
- При каждой успешной публикации батчи старше `WB_RETENTION_DAYS` (по умолчанию
  90 дней) удаляются. Дочерние строки удаляются каскадно.
- `page_fetched_at` — время наблюдения выдачи. Поля `updated_at` — время записи
  или перезаписи строки в PostgreSQL и не заменяют время наблюдения.

## Связи

```text
serp.batches (1)
  ├── (N) serp.products
  ├── (N) serp.query_totals
  └── (N) serp.attempts
```

Во всех дочерних таблицах `batch_id` ссылается на
`serp.batches(batch_id) ON DELETE CASCADE`.

## `serp.batches`

Одна строка на шестичасовой снимок. При повторных попытках строка обновляется и
показывает последнее опубликованное состояние батча.

| Столбец | Тип | Смысл и источник |
|---|---|---|
| `batch_id` | `text` | Первичный ключ вида `serp_20260810_0500`. |
| `batch_started_at_local` | `timestamptz` | Начало окна в локальном часовом поясе батча. |
| `batch_started_at_utc` | `timestamptz` | То же начало окна в UTC. |
| `batch_timezone` | `text` | IANA timezone, обычно `Asia/Yekaterinburg`. |
| `status` | `text` | Последний статус: `complete`, `partial`, `blocked` или `timed_out`. |
| `queries_expected` | `integer` | Число запросов после загрузки YAML и применения `WB_QUERY_LIMIT`. |
| `queries_completed` | `integer` | Число запросов, для которых собрана последовательность page-checkpoints от первой страницы. |
| `pages_expected` | `integer` | Верхняя ожидаемая граница: запросы × `WB_PAGES`. |
| `pages_completed` | `integer` | Сумма сохранённых последовательных страниц по всем запросам. |
| `product_rows` | `integer` | Число товарных строк в опубликованном снимке. |
| `error_count` | `integer` | Число ошибок последней реальной попытки. |
| `created_at` | `timestamptz` | Время первой вставки строки в БД. |
| `updated_at` | `timestamptz` | Время последнего upsert состояния батча. |

Первичный ключ: `batch_id`.

Индекс: `serp_batches_started_idx (batch_started_at_utc)`.

## `serp.products`

Товары на конкретных местах поисковой выдачи. Одна карточка может встречаться
в нескольких запросах, батчах и позициях.

| Столбец | Тип | Смысл и источник |
|---|---|---|
| `batch_id` | `text` | Батч наблюдения; внешний ключ на `serp.batches`. |
| `query` | `text` | Исходный поисковый запрос из YAML. |
| `dest_label` | `text` | Человекочитаемая метка региона/назначения, сейчас обычно `main`. |
| `dest` | `text` | Параметр назначения WB, с которым запрошена выдача. |
| `page` | `integer` | Номер страницы выдачи, начиная с 1. |
| `position_on_page` | `integer` | Позиция товара внутри страницы, начиная с 1. |
| `global_position` | `integer` | Расчётная позиция `(page - 1) × 100 + position_on_page`. |
| `total_catalog` | `bigint` | Общее количество результатов, сообщённое WB для запроса. |
| `normquery` | `text` | Нормализованный запрос из metadata WB. |
| `catalog_type` | `text` | Тип каталожного сопоставления из metadata WB. |
| `catalog_value` | `text` | Значение каталожного сопоставления из metadata WB. |
| `nm_id` | `bigint` | Артикул WB (`id`/`nmId`); при отсутствии используется доступный идентификатор `root`. |
| `root` | `bigint` | Корневой идентификатор карточки из SERP. |
| `name` | `text` | Название товара из SERP. |
| `brand` | `text` | Название бренда. |
| `brand_id` | `bigint` | Идентификатор бренда (`brandId`). |
| `supplier` | `text` | Название поставщика из SERP. |
| `supplier_id` | `bigint` | Идентификатор поставщика (`supplierId`). |
| `subject_id` | `bigint` | Идентификатор предмета WB (`subjectId`). |
| `rating` | `numeric` | Рейтинг товара из SERP. |
| `review_rating` | `numeric` | Рейтинг по отзывам (`reviewRating`). |
| `feedbacks` | `integer` | Количество отзывов. |
| `price_rub` | `numeric(14,2)` | Минимальная `product`-цена среди размеров в публичной выдаче, рубли. Это наблюдаемая SERP-цена, не официальная цена из кабинета. |
| `basic_price_rub` | `numeric(14,2)` | Минимальная `basic`-цена среди размеров в SERP, рубли. |
| `discount_percent` | `numeric(8,2)` | Расчёт `(basic_price_rub - price_rub) / basic_price_rub × 100`. |
| `sizes_count` | `integer` | Количество элементов `sizes` в товаре SERP. |
| `option_ids` | `text` | `optionId` размеров, объединённые через ` | `. |
| `colors` | `text` | Названия цветов, объединённые через ` | `. |
| `total_quantity` | `integer` | Доступное количество (`totalQuantity`) из SERP. |
| `time1` | `integer` | Служебное поле времени/логистики WB из ответа SERP. |
| `time2` | `integer` | Второе служебное поле времени/логистики WB. |
| `wh` | `integer` | Идентификатор склада/логистического назначения из SERP. |
| `view_flags` | `bigint` | Битовая маска `viewFlags` WB. |
| `is_advert` | `boolean` | `true`, если в `viewFlags` установлен рекламный бит `64`. |
| `page_fetched_at` | `timestamptz` | Фактическое UTC-время успешного получения страницы. Для checkpoints, созданных до добавления поля, может быть `NULL`. |
| `updated_at` | `timestamptz` | Время последнего upsert этой позиции в БД. |

Первичный ключ:
`(batch_id, query, dest_label, page, position_on_page)`.

Индексы:

- `serp_products_nm_batch_idx (nm_id, batch_id)` — история артикула;
- `serp_products_query_batch_idx (query, batch_id)` — история запроса.

## `serp.query_totals`

Компактная полнота сбора по запросу внутри батча.

| Столбец | Тип | Смысл и источник |
|---|---|---|
| `batch_id` | `text` | Батч; внешний ключ на `serp.batches`. |
| `query` | `text` | Запрос из YAML. |
| `dest_label` | `text` | Метка назначения выдачи. |
| `products_collected` | `integer` | Число товарных строк во всех сохранённых страницах запроса. |
| `pages_collected` | `integer` | Число последовательных сохранённых страниц, начиная с первой. |
| `total_catalog` | `bigint` | Максимальное значение общего количества результатов среди сохранённых страниц. |
| `updated_at` | `timestamptz` | Время последнего upsert агрегата. |

Первичный ключ: `(batch_id, query, dest_label)`.

## `serp.attempts`

Операционный журнал реальных обращений к WB. Одна строка не равна одному
пятиминутному cron-тику: быстрые no-op запуски не записываются.

| Столбец | Тип | Смысл и источник |
|---|---|---|
| `attempt_id` | `uuid` | Уникальный первичный ключ попытки. |
| `batch_id` | `text` | Продолжаемый батч; внешний ключ на `serp.batches`. |
| `started_at` | `timestamptz` | Начало реальной попытки. |
| `finished_at` | `timestamptz` | Завершение сбора перед публикацией. |
| `status` | `text` | `complete`, `partial`, `blocked` или `timed_out`. |
| `pages_completed_before` | `integer` | Сколько page-checkpoints существовало до попытки. |
| `pages_completed_after` | `integer` | Сколько последовательных страниц отражено в `query_totals` после попытки. |
| `error_count` | `integer` | Количество ошибок этой попытки. |
| `errors` | `jsonb` | Массив деталей: timestamp, query, page, dest, HTTP status, краткое тело ответа. |
| `created_at` | `timestamptz` | Время вставки журнала в БД. |

Первичный ключ: `attempt_id`.

## Правила записи

- `serp.batches`, `serp.products` и `serp.query_totals` пишутся через
  `INSERT ... ON CONFLICT DO UPDATE`; повторная публикация одного батча не
  создаёт дубликаты позиций.
- `serp.attempts` вставляется по новому UUID и сохраняет историю реальных
  попыток.
- Page-checkpoints сначала атомарно сохраняются на Railway volume, затем из них
  пересобирается снимок PostgreSQL. Поэтому после сбоя процесс продолжает с
  отсутствующей страницы.
- Удаление старой строки `serp.batches` удаляет связанные товары, итоги и
  попытки посредством `ON DELETE CASCADE`.

## Примеры чтения

Последний статус батча:

```sql
SELECT *
FROM serp.batches
ORDER BY batch_started_at_utc DESC
LIMIT 1;
```

Позиции и наблюдаемая SERP-цена одного артикула во времени:

```sql
SELECT
    b.batch_started_at_utc,
    p.query,
    p.global_position,
    p.price_rub,
    p.page_fetched_at
FROM serp.products AS p
JOIN serp.batches AS b USING (batch_id)
WHERE p.nm_id = :nm_id
ORDER BY b.batch_started_at_utc, p.query;
```

`:nm_id` — параметр для SQL-клиента. При ручном выполнении замените его числом,
например `123456789`.

Незавершённые или заблокированные реальные попытки:

```sql
SELECT batch_id, started_at, status, errors
FROM serp.attempts
WHERE status <> 'complete'
ORDER BY started_at DESC;
```

Текущая полнота последнего батча:

```sql
SELECT
    batch_id,
    queries_completed,
    queries_expected,
    pages_completed,
    pages_expected,
    product_rows,
    error_count
FROM serp.batches
ORDER BY batch_started_at_utc DESC
LIMIT 1;
```
