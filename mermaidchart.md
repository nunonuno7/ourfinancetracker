
erDiagram

%% ---------- RELAÇÕES DE AUTENTICAÇÃO ----------

auth_user||--o{auth_user_groups: has

auth_user||--o{auth_user_user_permissions: has

auth_group||--o{auth_group_permissions: has

auth_user_groups}o--||auth_group: member_of

auth_user_user_permissions}o--||auth_permission: granted_to

auth_group_permissions}o--||auth_permission: grants

auth_permission}o--||django_content_type: applies_to

django_admin_log}o--||auth_user: action_by

django_admin_log}o--||django_content_type: relates_to

%% ---------- RELAÇÕES CORE ----------

auth_user||--o{core_account: owns

auth_user||--o{core_transaction: records

auth_user||--o{core_category: defines

core_account}o--||core_accounttype: typed_as

core_account}o--||core_currency: in_currency

core_accountbalance}o--||core_account: for_account

core_transaction}o--||core_category: categorized_as

core_transaction}o--||date_period: for_period

core_accountbalance}o--||date_period: for_period

core_transaction_tags}o--||core_transaction: tags_txn

core_transaction_tags}o--||core_tag: with_tag

%% ---------- ENTIDADES ----------

auth_user{

    int idPK

    varchar username

    varchar email

    varchar password

    boolean is_active

    timestamp date_joined

}

auth_group{

    int idPK

    varchar name

}

auth_permission{

    int idPK

    varchar name

    varchar codename

    int content_type_idFK

}

django_content_type{

    int idPK

    varchar app_label

    varchar model

}

core_account{

    bigint idPK

    varchar name

    date created_at

    int user_idFK

    bigint account_type_idFK

    bigint currency_idFK

    int position

}

core_accounttype{

    bigint idPK

    varchar name

}

core_currency{

    bigint idPK

    varchar code

    varchar symbol

    smallint decimals

}

core_accountbalance{

    bigint idPK

    decimal reported_balance

    bigint account_idFK

    bigint period_idFK

}

core_transaction{

    bigint idPK

    decimal amount

    varchar type

    text notes

    boolean is_estimated

    boolean is_cleared

    timestamp created_at

    timestamp updated_at

    bigint period_idFK

    bigint category_idFK

    int user_idFK

}

core_category{

    bigint idPK

    varchar name

    int user_idFK

    bigint parent_idFK

}

core_tag{

    bigint idPK

    varchar name

}

core_transaction_tags{

    bigint idPK

    bigint transaction_idFK

    bigint tag_idFK

}

date_period{

    bigint idPK

    int year

    int month

    varchar label

}

django_admin_log{

    int idPK

    timestamp action_time

    text object_id

    varchar object_repr

    smallint action_flag

    text change_message

    int content_type_idFK

    int user_idFK

}
