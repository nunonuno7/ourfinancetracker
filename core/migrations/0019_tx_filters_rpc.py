from django.db import migrations

TX_FILTERS_FUNCTION = """
CREATE OR REPLACE FUNCTION tx_filters(
    _user   core_transaction.user_id%%TYPE,
    _period core_transaction.period_id%%TYPE DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_build_object(
        'types', (
            SELECT COALESCE(jsonb_agg(DISTINCT t.type ORDER BY t.type), '[]'::jsonb)
            FROM core_transaction t
            WHERE t.user_id = _user
              AND (_period IS NULL OR t.period_id = _period)
        ),
        'categories', (
            SELECT COALESCE(jsonb_agg(DISTINCT c.name ORDER BY c.name), '[]'::jsonb)
            FROM core_transaction t
            JOIN core_category c ON c.id = t.category_id
            WHERE t.user_id = _user
              AND (_period IS NULL OR t.period_id = _period)
        ),
        'accounts', (
            SELECT COALESCE(jsonb_agg(DISTINCT a.name ORDER BY a.name), '[]'::jsonb)
            FROM core_transaction t
            JOIN core_account a ON a.id = t.account_id
            WHERE t.user_id = _user
              AND (_period IS NULL OR t.period_id = _period)
        ),
        'periods', (
            SELECT COALESCE(
                jsonb_agg(
                    DISTINCT to_char(make_date(dp.year, dp.month, 1), 'YYYY-MM')
                    ORDER BY 1
                ),
                '[]'::jsonb
            )
            FROM core_transaction t
            JOIN core_dateperiod dp ON dp.id = t.period_id
            WHERE t.user_id = _user
        )
    );
$$;
"""

# Drop robusto: apaga qualquer versão previamente criada da função (tipos diferentes)
DROP_TX_FILTERS_FUNCTION = """
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT n.nspname AS schemaname, p.oid,
           pg_get_function_identity_arguments(p.oid) AS args
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.proname = 'tx_filters'
  LOOP
    EXECUTE format('DROP FUNCTION IF EXISTS %I.tx_filters(%s);', r.schemaname, r.args);
  END LOOP;
END $$;
"""

def create_tx_filters(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(TX_FILTERS_FUNCTION)

def drop_tx_filters(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP_TX_FILTERS_FUNCTION)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_remove_account_unique_account_user_name_and_more"),
    ]
    operations = [
        migrations.RunPython(create_tx_filters, drop_tx_filters),
    ]
