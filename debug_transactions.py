
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ourfinancetracker_site.settings')
django.setup()

from core.models import Transaction, User, DatePeriod
from django.db import connection
from datetime import date
import pandas as pd

# Verificar transações na base de dados
user = User.objects.first()
if user:
    print(f"Utilizador: {user.username} (ID: {user.id})")
    
    # Contar transações
    tx_count = Transaction.objects.filter(user=user).count()
    print(f"Transações do utilizador: {tx_count}")
    
    # Mostrar algumas transações
    if tx_count > 0:
        latest = Transaction.objects.filter(user=user).order_by('-date')[:5]
        for tx in latest:
            print(f"  - {tx.date} | {tx.type} | {tx.amount} | {tx.category}")
    
    # Query direta
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM core_transaction WHERE user_id = %s", [user.id])
        count = cursor.fetchone()[0]
        print(f"Query direta: {count} transações")
        
        if count > 0:
            cursor.execute("""
                SELECT date, type, amount, category_id, account_id 
                FROM core_transaction 
                WHERE user_id = %s 
                ORDER BY date DESC 
                LIMIT 5
            """, [user.id])
            rows = cursor.fetchall()
            print("Últimas 5 transações:")
            for row in rows:
                print(f"  - {row}")

    # NOVO: Testar query específica do transactions_json
    print("\n=== TESTE QUERY TRANSACTIONS_JSON ===")
    start_date = date(2025, 1, 1)
    end_date = date.today()
    
    with connection.cursor() as cursor:
        # Query exacta da função transactions_json
        cursor.execute("""
            SELECT tx.id, tx.date, 
                   COALESCE(dp.year, EXTRACT(year FROM tx.date)) as year,
                   COALESCE(dp.month, EXTRACT(month FROM tx.date)) as month,
                   tx.type, tx.amount,
                   COALESCE(cat.name, 'Other') AS category,
                   COALESCE(acc.name, '(no account)') AS account,
                   COALESCE(curr.symbol, '€') AS currency
            FROM core_transaction tx
            LEFT JOIN core_category cat ON tx.category_id = cat.id
            LEFT JOIN core_account acc ON tx.account_id = acc.id
            LEFT JOIN core_currency curr ON acc.currency_id = curr.id
            LEFT JOIN core_dateperiod dp ON tx.period_id = dp.id
            WHERE tx.user_id = %s AND tx.date BETWEEN %s AND %s
            ORDER BY tx.date DESC, tx.id DESC
        """, [user.id, start_date, end_date])
        transactions = cursor.fetchall()
        print(f"Query transactions_json retornou: {len(transactions)} transações")
        
        if transactions:
            print("Primeiras 3 transações:")
            for i, tx in enumerate(transactions[:3]):
                print(f"  {i+1}: {tx}")
        
        # Verificar DatePeriods
        periods = DatePeriod.objects.all().count()
        print(f"\nDatePeriods na BD: {periods}")
        
        # Verificar se há transações sem period_id
        cursor.execute("SELECT COUNT(*) FROM core_transaction WHERE user_id = %s AND period_id IS NULL", [user.id])
        no_period = cursor.fetchone()[0]
        print(f"Transações sem period_id: {no_period}")
