erDiagram
    %% ---------- RELAÇÕES ----------
    USER ||--|| USER_SETTINGS : has
    USER ||--o{ ACCOUNT : owns
    ACCOUNT ||--o{ ACCOUNT_BALANCE : keeps
    USER ||--o{ CATEGORY : defines
    CATEGORY ||--o{ CATEGORY : parent_of
    USER ||--o{ TRANSACTION : records
    TRANSACTION }o--|| ACCOUNT : reconciled_with
    TRANSACTION }o--|| CATEGORY : is_in
    TRANSACTION ||--o{ TRANSACTION_ATTACHMENT : has
    USER ||--o{ BUDGET : sets
    USER ||--o{ RECURRING_TRANSACTION : schedules
    RECURRING_TRANSACTION }o--|| TRANSACTION : template_of
    USER ||--o{ IMPORT_LOG : imports
    ACCOUNT }o--|| ACCOUNT_TYPE : typed_as
    ACCOUNT }o--|| CURRENCY : denominated_in
    CURRENCY ||--o{ EXCHANGE_RATE : source_of
    CURRENCY ||--o{ EXCHANGE_RATE : target_of

    %% ---------- ENTIDADES ----------
    USER {
        int          id PK
        varchar(150) username  "único"
        varchar(254) email     "único"
        varchar(255) password_hash
        boolean      is_active
        datetime     created_at
        datetime     updated_at
    }
    USER_SETTINGS {
        int          id PK
        int          user_id FK
        varchar(3)   default_currency_id FK
        varchar(50)  timezone
        tinyint      start_of_month
        datetime     created_at
        datetime     updated_at
    }
    ACCOUNT {
        int          id PK
        int          user_id FK
        varchar(80)  name
        int          account_type_id FK
        varchar(3)   currency_id FK
        datetime     created_at
        datetime     updated_at
    }
    ACCOUNT_TYPE {
        int          id PK
        varchar(40)  name
    }
    CURRENCY {
        varchar(3)   code PK
        varchar(4)   symbol
        tinyint      decimals
    }
    ACCOUNT_BALANCE {
        int          id PK
        int          account_id FK
        date         balance_date
        decimal      reported_balance
        boolean      is_manual_entry
        datetime     created_at
        datetime     updated_at
    }
    CATEGORY {
        int          id PK
        int          user_id FK
        varchar(80)  name
        int          parent_id FK
        datetime     created_at
        datetime     updated_at
    }
    TRANSACTION {
        int          id PK
        int          user_id FK
        decimal      amount
        date         date
        enum         type        "income|expense|investment"
        int          category_id FK
        int          account_id FK   "opcional"
        boolean      is_estimated    "default:false"
        text         notes
        boolean      is_cleared      "default:false"
        datetime     created_at
        datetime     updated_at
    }
    TRANSACTION_ATTACHMENT {
        int          id PK
        int          transaction_id FK
        varchar(255) file_path
        datetime     created_at
        datetime     updated_at
    }
    BUDGET {
        int          id PK
        int          user_id FK
        int          category_id FK
        date         start_date
        date         end_date
        decimal      amount
        boolean      rollover
        datetime     created_at
        datetime     updated_at
    }
    RECURRING_TRANSACTION {
        int          id PK
        int          user_id FK
        decimal      amount
        enum         frequency  "daily|weekly|monthly|yearly"
        date         next_occurrence
        date         end_date
        boolean      is_active
        int          template_transaction_id FK
        datetime     created_at
        datetime     updated_at
    }
    IMPORT_LOG {
        int          id PK
        int          user_id FK
        varchar(80)  source
        datetime     imported_at
        int          num_records
        enum         status     "success|partial|error"
        text         error_message
        datetime     created_at
        datetime     updated_at
    }
    EXCHANGE_RATE {
        int          id PK
        varchar(3)   from_currency_code FK
        varchar(3)   to_currency_code   FK
        decimal      rate
        date         rate_date
        datetime     created_at
        datetime     updated_at
    }

    %% ---------- ÍNDICES / CONSTRAINTS SUGERIDOS ----------
    %% EXCHANGE_RATE : UNIQUE (from_currency_code, to_currency_code, rate_date)
    %% ACCOUNT_BALANCE : UNIQUE (account_id, balance_date)
    %% CATEGORY        : UNIQUE (user_id, name, parent_id)
    %% TRANSACTION     : INDEX (user_id, date)
