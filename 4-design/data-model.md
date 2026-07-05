# Модель данных — Гончарная мастерская «Глина»

## 1. Сущность: Slot (Занятие)
*Отвечает за расписание. Данные приходят read-only из бэкенда.*

| Поле | Тип | Описание |
| :-- | :-- | :-- |
| `id` | UUID | Уникальный ID слота |
| `program_name` | String | «Гончарный круг» или «Ручная лепка» |
| `start_time` | DateTime | Время начала занятия (UTC) |
| `master_name` | String | Имя инструктора |
| `total_places` | Int | Всего мест (10 или 6) |
| `available_places`| Int | Текущий остаток |
| `status` | Enum | `active`, `club_cancelled` |

## 2. Сущность: Booking (Бронь)
*Отвечает за запись клиента.*

| Поле | Тип | Описание |
| :-- | :-- | :-- |
| `id` | UUID | ID брони |
| `slot_id` | UUID | Ссылка на слот |
| `client_name` | String | Имя клиента |
| `phone` | String | Телефон (валидированный) |
| `needs_rental` | Boolean | True, если нужен прокат |
| `status` | Enum | `active`, `cancelled`, `late_cancelled` |

## 3. Взаимосвязи
* **1 Slot : N Bookings.** Один слот может содержать множество записей до достижения `total_places`.
* **Constraint:** При создании брони (POST /bookings) система проверяет `available_places` в слоте. Если `available_places` < 1, возвращается ошибка 409 Conflict.