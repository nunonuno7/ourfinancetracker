from django.db import migrations

TX_FILTERS_FUNCTION = """
CREATE OR REPLACE FUNCTION tx_filters(
    _user core_transaction.user_id%TYPE,
    _period core_transaction.period%TYPE DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_build_object(
        'types', (
            SELECT jsonb_agg(DISTINCT t.type)
            FROM core_transaction t
            WHERE t.user_id = _user
              AND (_period IS NULL OR t.period = _period)
        ),
        'categories', (
            SELECT jsonb_agg(DISTINCT c.name)
            FROM core_transaction t
            JOIN core_category c ON c.id = t.category_id
            WHERE t.user_id = _user
              AND (_period IS NULL OR t.period = _period)
        ),
        'accounts', (
            SELECT jsonb_agg(DISTINCT a.name)
            FROM core_transaction t
            JOIN core_account a ON a.id = t.account_id
            WHERE t.user_id = _user
              AND (_period IS NULL OR t.period = _period)
        ),
        'periods', (
            SELECT jsonb_agg(DISTINCT t.period)
            FROM core_transaction t
            WHERE t.user_id = _user
        )
    );
$$;
"""

DROP_TX_FILTERS_FUNCTION = """
DROP FUNCTION IF EXISTS tx_filters(uuid, text);
DROP FUNCTION IF EXISTS tx_filters(bigint, integer);
"""


def create_tx_filters(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(TX_FILTERS_FUNCTION)


def drop_tx_filters(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TX_FILTERS_FUNCTION)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_remove_account_unique_account_user_name_and_more"),
    ]

    operations = [
        migrations.RunPython(create_tx_filters, drop_tx_filters),
    ]
