from django.db import connection

def testar_query_sql(user):
    user_id = user.id

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
              t.date,
              t.type,
              t.amount,
              COALESCE(c.name, '') AS category,
              STRING_AGG(tag.name, ', ') AS tags,
              COALESCE(a.name, '') AS account,
              CONCAT(p.year, '-', LPAD(p.month::text, 2, '0')) AS period
            FROM core_transaction t
            LEFT JOIN core_category c ON t.category_id = c.id
            LEFT JOIN core_account a ON t.account_id = a.id
            LEFT JOIN core_dateperiod p ON t.period_id = p.id
            LEFT JOIN core_transaction_tags tt ON t.id = tt.transaction_id
            LEFT JOIN core_tag tag ON tag.id = tt.tag_id
            WHERE t.user_id = %s
            GROUP BY t.id, t.date, t.type, t.amount, c.name, a.name, p.year, p.month
            ORDER BY t.date DESC;
        """, [user_id])

        results = cursor.fetchall()
        for row in results:
            print("🟢", row)
