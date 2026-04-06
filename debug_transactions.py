
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ourfinancetracker_site.settings')
django.setup()

from core.models import Transaction, User, DatePeriod
from django.db import connection
from datetime import date
import pandas as pd

# Check transactions in the database
user = User.objects.first()
if user:
    print(f"User: {user.username} (ID: {user.id})")
    
    # Count transactions
    tx_count = Transaction.objects.filter(user=user).count()
    print(f"User transactions: {tx_count}")
    
    # Show a few transactions
    if tx_count > 0:
        latest = Transaction.objects.filter(user=user).order_by('-date')[:5]
        for tx in latest:
            print(f"  - {tx.date} | {tx.type} | {tx.amount} | {tx.category}")
    
    # Direct query
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM core_transaction WHERE user_id = %s", [user.id])
        count = cursor.fetchone()[0]
        print(f"Direct query: {count} transactions")
        
        if count > 0:
            cursor.execute("""
                SELECT date, type, amount, category_id, account_id 
                FROM core_transaction 
                WHERE user_id = %s 
                ORDER BY date DESC 
                LIMIT 5
            """, [user.id])
            rows = cursor.fetchall()
            print("Latest 5 transactions:")
            for row in rows:
                print(f"  - {row}")

    # NEW: Test the specific transactions_json query
    print("\n=== TRANSACTIONS_JSON QUERY TEST ===")
    start_date = date(2025, 1, 1)
    end_date = date.today()
    
    with connection.cursor() as cursor:
        # Exact query used by the transactions_json function
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
        print(f"transactions_json query returned: {len(transactions)} transactions")
        
        if transactions:
            print("First 3 transactions:")
            for i, tx in enumerate(transactions[:3]):
                print(f"  {i+1}: {tx}")
        
        # Check DatePeriods
        periods = DatePeriod.objects.all().count()
        print(f"\nDatePeriods in DB: {periods}")
        
        # Check whether there are transactions without period_id
        cursor.execute("SELECT COUNT(*) FROM core_transaction WHERE user_id = %s AND period_id IS NULL", [user.id])
        no_period = cursor.fetchone()[0]
        print(f"Transactions without period_id: {no_period}")
