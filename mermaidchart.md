
---
config:

  theme: forest
---
erDiagram

%% === AUTENTICAÇÃO E PERMISSÕES ===

auth_user{

    int idPK

    %% varchar(150)

    varchar username

    %% varchar(254)

    varchar email

    %% hash

    varchar password

    boolean is_active

    timestamp date_joined

}

auth_group{

    int idPK

    %% varchar(80)

    varchar name

}

auth_permission{

    int idPK

    varchar name

    %% varchar(100)

    varchar codename

    int content_type_idFK

}

auth_user_groups{

    int idPK

    int user_idFK

    int group_idFK

}

auth_user_user_permissions{

    int idPK

    int user_idFK

    int permission_idFK

}

auth_group_permissions{

    int idPK

    int group_idFK

    int permission_idFK

}

django_content_type{

    int idPK

    %% varchar(100)

    varchar app_label

    %% varchar(100)

    varchar model

}

%% === LOG DE AÇÕES ADMIN ===

django_admin_log{

    int idPK

    timestamp action_time

    text object_id

    %% varchar(200)

    varchar object_repr

    smallint action_flag

    text change_message

    int content_type_idFK

    int user_idFK

}

%% === ENTIDADES FINANCEIRAS ===

core_account{

    bigint idPK

    %% varchar(100)

    varchar name

    date created_at

    int user_idFK

    bigint account_type_idFK

    bigint currency_idFK

    int position

}

core_accounttype{

    bigint idPK

    %% varchar(50)

    varchar name

}

core_currency{

    bigint idPK

    %% ISO-4217, varchar(3)

    varchar code

    %% símbolo monetário, varchar(4)

    varchar symbol

    smallint decimals

}

core_accountbalance{

    bigint idPK

    %% decimal(12,2)

    decimal reported_balance

    bigint account_idFK

    bigint period_idFK

}

core_transaction{

    bigint idPK

    %% decimal(12,2)

    decimal amount

    %% income | expense | investment

    varchar type

    text notes

    boolean is_cleared

    timestamp created_at

    timestamp updated_at

    bigint period_idFK

    bigint category_idFK

    bigint account_idFK

    int user_idFK

}

core_transaction_attachment{

    bigint idPK

    bigint transaction_idFK

    %% varchar(255)

    varchar file_path

    timestamp created_at

    timestamp updated_at

}

core_category{

    bigint idPK

    %% varchar(100)

    varchar name

    int user_idFK

    int position

}

core_tag{

    bigint idPK

    %% varchar(100)

    varchar name

    int position

}

core_transaction_tags{

    bigint idPK

    bigint transaction_idFK

    bigint tag_idFK

}

core_budget{

    bigint idPK

    int user_idFK

    bigint category_idFK

    date start_date

    date end_date

    %% decimal(12,2)

    decimal amount

    boolean rollover

    timestamp created_at

    timestamp updated_at

    int position

}

core_recurring_transaction{

    bigint idPK

    int user_idFK

    %% decimal(12,2)

    decimal amount

    %% daily | weekly | monthly | yearly

    varchar frequency

    date next_occurrence

    bigint end_period_idFK

    boolean is_active

    bigint template_transaction_idFK

    timestamp created_at

    timestamp updated_at

    int position

}

core_import_log{

    bigint idPK

    int user_idFK

    %% varchar(80)

    varchar source

    timestamp imported_at

    int num_records

    %% success | partial | error

    varchar status

    text error_message

    timestamp created_at

    timestamp updated_at

}

core_exchange_rate{

    bigint idPK

    %% ISO-4217

    varchar from_currency_codeFK

    %% ISO-4217

    varchar to_currency_codeFK

    %% decimal(12,6)

    decimal rate

    date rate_date

    timestamp created_at

    timestamp updated_at

}

date_period{

    bigint idPK

    int year

    int month

    %% varchar(20)

    varchar label

}

%% === RELAÇÕES ENTRE ENTIDADES ===

auth_user||--o{auth_user_groups: has_groups

auth_user||--o{auth_user_user_permissions: has_permissions

auth_group||--o{auth_group_permissions: has_permissions

auth_user_groups}o--||auth_group: belongs_to_group

auth_user_user_permissions}o--||auth_permission: permission_ref

auth_group_permissions}o--||auth_permission: permission_ref

auth_permission}o--||django_content_type: applies_to

django_admin_log}o--||auth_user: action_by

django_admin_log}o--||django_content_type: on_model

auth_user||--o{core_account: owns_account

auth_user||--o{core_transaction: records_transaction

auth_user||--o{core_category: defines_category

auth_user||--o{core_budget: owns_budget

auth_user||--o{core_import_log: performed_import

auth_user||--o{core_recurring_transaction: schedules_recurring

core_account}o--||core_accounttype: has_type

core_account}o--||core_currency: uses_currency

core_accountbalance}o--||core_account: for_account

core_accountbalance}o--||date_period: in_period

core_transaction}o--||core_category: has_category

core_transaction}o--||date_period: occurs_in

core_transaction}o--||core_account: belongs_to_account

core_transaction_attachment}o--||core_transaction: attachment_of

core_transaction_tags}o--||core_transaction: for_transaction

core_transaction_tags}o--||core_tag: has_tag

core_budget}o--||core_category: for_category

core_recurring_transaction}o--||core_transaction: template_for

core_recurring_transaction}o--||date_period: ends_in

core_exchange_rate}o--||core_currency: from_currency

core_exchange_rate}o--||core_currency: to_currency
