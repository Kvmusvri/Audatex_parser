# Структура базы данных

## parser_car_detail

| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |
|------|-----|----------|-------------|-------------|--------|
| id | INTEGER | ✗ | ✓ |  |  |
| request_id | VARCHAR(50) | ✗ |  |  | ✓ |
| vin | VARCHAR(50) | ✗ |  |  | ✓ |
| group_zone | VARCHAR(50) | ✗ |  |  |  |
| code | VARCHAR(50) | ✗ |  |  |  |
| title | TEXT | ✗ |  |  |  |
| source_from | VARCHAR(50) | ✗ |  |  |  |
| created_date | DATE | ✗ |  |  |  |

## parser_car_detail_group_zone

| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |
|------|-----|----------|-------------|-------------|--------|
| id | INTEGER | ✗ | ✓ |  |  |
| request_id | VARCHAR(50) | ✗ |  |  | ✓ |
| vin | VARCHAR(50) | ✗ |  |  | ✓ |
| type | VARCHAR(50) | ✗ |  |  |  |
| title | TEXT | ✗ |  |  |  |
| source_from | VARCHAR(50) | ✗ |  |  |  |
| created_date | DATE | ✗ |  |  |  |

## parser_car_request_status

| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |
|------|-----|----------|-------------|-------------|--------|
| id | INTEGER | ✗ | ✓ |  |  |
| request_id | VARCHAR(50) | ✗ |  |  | ✓ |
| vin | VARCHAR(50) | ✗ |  |  | ✓ |
| vin_status | VARCHAR(50) | ✗ |  |  |  |
| comment | VARCHAR(50) | ✗ |  |  |  |
| started_at | DATETIME | ✓ |  |  |  |
| completed_at | DATETIME | ✓ |  |  |  |
| created_date | DATE | ✗ |  |  |  |

## parser_car_options

| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |
|------|-----|----------|-------------|-------------|--------|
| id | INTEGER | ✗ | ✓ |  |  |
| request_id | VARCHAR(50) | ✗ |  |  | ✓ |
| vin | VARCHAR(50) | ✗ |  |  | ✓ |
| zone_name | VARCHAR(100) | ✗ |  |  |  |
| option_code | VARCHAR(50) | ✗ |  |  |  |
| option_title | TEXT | ✗ |  |  |  |
| is_selected | BOOLEAN | ✗ |  |  |  |
| source_from | VARCHAR(50) | ✗ |  |  |  |
| created_date | DATE | ✗ |  |  |  |

## parser_schedule_settings

| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |
|------|-----|----------|-------------|-------------|--------|
| id | INTEGER | ✗ | ✓ |  |  |
| start_time | VARCHAR(5) | ✗ |  |  |  |
| end_time | VARCHAR(5) | ✗ |  |  |  |
| is_active | BOOLEAN | ✗ |  |  |  |
| created_at | DATETIME | ✗ |  |  |  |
| updated_at | DATETIME | ✗ |  |  |  |

## users

| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |
|------|-----|----------|-------------|-------------|--------|
| id | INTEGER | ✗ | ✓ |  |  |
| username | VARCHAR(50) | ✗ |  |  |  |
| email | VARCHAR(100) | ✓ |  |  |  |
| hashed_password | VARCHAR(255) | ✗ |  |  |  |
| role | VARCHAR(20) | ✗ |  |  |  |
| is_active | BOOLEAN | ✗ |  |  |  |
| last_login | DATETIME | ✓ |  |  |  |
| failed_login_attempts | INTEGER | ✗ |  |  |  |
| locked_until | DATETIME | ✓ |  |  |  |
| created_at | DATETIME | ✗ |  |  |  |
| updated_at | DATETIME | ✗ |  |  |  |

## user_sessions

| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |
|------|-----|----------|-------------|-------------|--------|
| id | INTEGER | ✗ | ✓ |  |  |
| user_id | INTEGER | ✗ |  | ✓ |  |
| token_hash | VARCHAR(255) | ✗ |  |  |  |
| expires_at | DATETIME | ✗ |  |  |  |
| ip_address | VARCHAR(45) | ✓ |  |  |  |
| user_agent | TEXT | ✓ |  |  |  |
| created_at | DATETIME | ✗ |  |  |  |

**Связи:**
- `user_id` → `users.id`

