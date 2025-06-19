erDiagram
    %% ---------- RELATIONSHIPS ----------
    USER        ||--|| USER_SETTINGS        : has
    USER        ||--o{ ACCOUNT              : owns
    USER        ||--o{ CATEGORY             : defines
    CATEGORY    ||--o{ CATEGORY             : parent_of
    USER        ||--o{ TRANSACTION          : records
    USER        ||--o{ TAG                  : creates
    TRANSACTION ||--o{ TRANSACTION_TAG      : has
    TAG         ||--o{ TRANSACTION_TAG      : labels
    ACCOUNT     ||--o{ ACCOUNT_BALANCE      : snapshots
    ACCOUNT     }o--|| ACCOUNT_TYPE         : typed_as
    ACCOUNT     }o--|| CURRENCY             : denominated_in
    ACCOUNT_BALANCE }o--|| DATE_PERIOD      : for
    CURRENCY    ||--o{ EXCHANGE_RATE        : source_of_rate
    CURRENCY    ||--o{ EXCHANGE_RATE        : target_of_rate
    USER        ||--o{ RECURRING_TRANSACTION: schedules
    RECURRING_TRANSACTION }o--|| TRANSACTION: template_of
    USER        ||--o{ IMPORT_LOG           : imports

    %% ---------- ENTITIES ----------
    USER {
        int          id PK
        varchar(150) username  "unique"
        varchar(254) email     "unique"
        varchar(255) password_hash
        bool         is_active
        datetime     created_at
    }
    USER_SETTINGS {
        int          id PK
        int          user_id FK
        varchar(3)   default_currency_id FK
        varchar(50)  timezone
        tinyint      start_of_month       "1‑31"
    }
    ACCOUNT {
        int          id PK
        int          user_id FK
        varchar(80)  name
        int          account_type_id FK
        varchar(3)   currency_id FK
        bool         is_active
    }
    ACCOUNT_TYPE {
        int          id PK
        varchar(20)  name  "saving | investment | credit"
    }
    CURRENCY {
        varchar(3)   id PK  "ISO code"
        varchar(40)  name
        varchar(5)   symbol
    }
    EXCHANGE_RATE {
        int          id PK
        varchar(3)   source_currency_id FK
        varchar(3)   target_currency_id FK
        decimal(16,6) rate
        date         rate_date
    }
    DATE_PERIOD {
        int          id PK
        smallint     year
        tinyint      month  "1‑12"
    }
    ACCOUNT_BALANCE {
        int          id PK
        int          account_id FK
        int          period_id FK
        decimal(18,2) reported_balance
    }
    CATEGORY {
        int          id PK
        int          user_id FK
        varchar(80)  name
        int          parent_id FK nullable
    }
    TAG {
        int          id PK
        int          user_id FK
        varchar(60)  name
    }
    TRANSACTION {
        int          id PK
        int          user_id FK
        int          account_id FK
        int          category_id FK nullable
        date         date
        enum         type  "income | expense | investimento"
        decimal(18,2) amount
        text         description nullable
    }
    TRANSACTION_TAG {
        int          id PK
        int          transaction_id FK
        int          tag_id FK
    }
    RECURRING_TRANSACTION {
        int          id PK
        int          user_id FK
        int          account_id FK
        enum         type          "income | expense | investimento"
        decimal(18,2) amount
        varchar(50)  cron_expression
        date         next_run
        int          category_id FK nullable
    }
    IMPORT_LOG {
        int          id PK
        int          user_id FK
        varchar(120) filename
        smallint     rows_processed
        datetime     created_at
    }