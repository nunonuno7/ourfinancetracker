"""
The code is modified to add tags support to the bulk transaction importer.
"""
"""
Import optimization utilities for large Excel files.
"""

import pandas as pd
import logging
from typing import Dict, List, Tuple
from decimal import Decimal
from django.db import transaction as db_transaction
from ..models import Account, Category, Currency, AccountType, DatePeriod, Transaction, Tag, TransactionTag

logger = logging.getLogger(__name__)


class BulkTransactionImporter:
    """Optimized bulk importer for large transaction files."""

    def __init__(self, user, batch_size=2000):
        self.user = user
        self.batch_size = batch_size
        self.default_currency = None
        self.default_account_type = None
        logger.info(f"🚀 [BulkTransactionImporter] Initialized for user {user.id}, batch_size={batch_size}")

    def import_dataframe(self, df: pd.DataFrame) -> Dict:
        """Import transactions from pandas DataFrame with optimizations."""
        logger.info(f"📊 [BulkTransactionImporter] Starting import of DataFrame with shape: {df.shape}")

        result = {
            'imported': 0,
            'errors': [],
            'skipped': 0
        }

        try:
            # Use atomic block with savepoint for better performance
            with db_transaction.atomic(using='default', savepoint=True):
                logger.info(f"🔐 [BulkTransactionImporter] Starting atomic transaction with savepoint")

                # Pre-setup default objects
                logger.info(f"🏗️ [BulkTransactionImporter] Setting up defaults...")
                self._setup_defaults()

                # Clean and validate data
                logger.info(f"🧹 [BulkTransactionImporter] Cleaning data...")
                df_clean = self._clean_dataframe(df)
                if df_clean.empty:
                    logger.warning(f"⚠️ [BulkTransactionImporter] No valid data after cleaning")
                    result['errors'].append('No valid data after cleaning')
                    return result

                logger.info(f"✅ [BulkTransactionImporter] Clean data shape: {df_clean.shape}")

                # Bulk create supporting objects
                logger.info(f"🏗️ [BulkTransactionImporter] Creating supporting objects...")
                period_lookup = self._bulk_create_periods(df_clean)
                category_lookup = self._bulk_create_categories(df_clean)
                account_lookup = self._bulk_create_accounts(df_clean)

                # Bulk create transactions in batches
                logger.info(f"💰 [BulkTransactionImporter] Creating transactions...")
                result['imported'] = self._bulk_create_transactions(
                    df_clean, period_lookup, category_lookup, account_lookup
                )

                logger.info(f"✅ [BulkTransactionImporter] Import completed: {result['imported']} transactions")

        except Exception as e:
            logger.error(f"💥 [BulkTransactionImporter] Import error: {e}")
            logger.exception("Full traceback:")
            result['errors'].append(f"Import failed: {str(e)}")

        return result

    def _setup_defaults(self):
        """Setup default currency and account type."""
        self.default_currency, _ = Currency.objects.get_or_create(
            code='EUR', 
            defaults={'name': 'Euro', 'symbol': '€'}
        )
        self.default_account_type, _ = AccountType.objects.get_or_create(
            name='Savings'
        )

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate DataFrame."""
        logger.debug(f"🧹 [BulkTransactionImporter] Starting data cleaning...")
        logger.debug(f"📋 [BulkTransactionImporter] Input columns: {list(df.columns)}")

        # Required columns
        required_cols = ['Date', 'Type', 'Amount', 'Category', 'Account']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"❌ [BulkTransactionImporter] Missing columns: {missing_cols}")
            raise ValueError(f'Missing columns: {", ".join(missing_cols)}')

        logger.info(f"✅ [BulkTransactionImporter] All required columns present")

        # Clean data
        initial_rows = len(df)
        df_clean = df.dropna(subset=required_cols).copy()
        rows_after_dropna = len(df_clean)
        logger.info(f"🔢 [BulkTransactionImporter] Rows after dropna: {initial_rows} → {rows_after_dropna}")

        df_clean['Account'] = df_clean['Account'].astype(str).str.strip()
        df_clean['Category'] = df_clean['Category'].astype(str).str.strip()

        logger.debug(f"🏦 [BulkTransactionImporter] Unique accounts: {df_clean['Account'].nunique()}")
        logger.debug(f"🏷️ [BulkTransactionImporter] Unique categories: {df_clean['Category'].nunique()}")

        # Convert data types
        try:
            logger.info(f"🔄 [BulkTransactionImporter] Converting data types...")
            df_clean['Date'] = pd.to_datetime(df_clean['Date']).dt.date
            df_clean['Amount'] = df_clean['Amount'].astype(float)

            logger.debug(f"📅 [BulkTransactionImporter] Date range: {df_clean['Date'].min()} to {df_clean['Date'].max()}")
            logger.debug(f"💰 [BulkTransactionImporter] Amount range: {df_clean['Amount'].min()} to {df_clean['Amount'].max()}")

            # Clean and normalize transaction types
            logger.info(f"🏷️ [BulkTransactionImporter] Normalizing transaction types...")
            original_types = df_clean['Type'].value_counts().to_dict()
            logger.debug(f"📊 [BulkTransactionImporter] Original types: {original_types}")

            df_clean['Type'] = df_clean['Type'].astype(str).str.strip().str.upper()
            df_clean.loc[df_clean['Type'].isin(['INVESTMENT', 'INVEST', 'IV', 'INVESTIMENTO']), 'Type'] = 'IV'
            df_clean.loc[df_clean['Type'].isin(['INCOME', 'IN', 'RECEITA', 'RENDIMENTO']), 'Type'] = 'IN'
            df_clean.loc[df_clean['Type'].isin(['EXPENSE', 'EX', 'DESPESA', 'GASTO']), 'Type'] = 'EX'
            df_clean.loc[df_clean['Type'].isin(['TRANSFER', 'TR', 'TRANSFERENCIA']), 'Type'] = 'TR'
            df_clean.loc[df_clean['Type'].isin(['ADJUSTMENT', 'AJ', 'AJUSTE']), 'Type'] = 'AJ'

        except Exception as e:
            logger.error(f"❌ [BulkTransactionImporter] Data conversion error: {str(e)}")
            raise ValueError(f'Data conversion error: {str(e)}')

        # Validate transaction types
        valid_types = ['IN', 'EX', 'IV', 'TR', 'AJ']
        invalid_types = df_clean[~df_clean['Type'].isin(valid_types)]['Type'].unique()
        if len(invalid_types) > 0:
            logger.error(f"❌ [BulkTransactionImporter] Invalid types: {invalid_types}")
            raise ValueError(f'Invalid transaction types found: {", ".join(invalid_types)}. Valid types: Income/IN, Expense/EX, Investment/IV, Transfer/TR, Adjustment/AJ')

        df_clean = df_clean[df_clean['Type'].isin(valid_types)]
        final_rows = len(df_clean)
        logger.info(f"✅ [BulkTransactionImporter] Data cleaning completed: {final_rows} valid rows")

        return df_clean

    def _bulk_create_periods(self, df: pd.DataFrame) -> Dict:
        """Bulk create date periods."""
        # Get unique year/month combinations
        periods_df = df['Date'].apply(lambda x: (x.year, x.month)).drop_duplicates()

        # Check existing periods
        existing_periods = {
            (p.year, p.month): p 
            for p in DatePeriod.objects.all()
        }

        # Create missing periods
        periods_to_create = []
        for year, month in periods_df:
            if (year, month) not in existing_periods:
                from datetime import date
                period_date = date(year, month, 1)
                periods_to_create.append(DatePeriod(
                    year=year,
                    month=month,
                    label=period_date.strftime('%B %Y')
                ))

        if periods_to_create:
            DatePeriod.objects.bulk_create(periods_to_create, ignore_conflicts=True)

        # Refresh lookup
        return {
            (p.year, p.month): p 
            for p in DatePeriod.objects.all()
        }

    def _bulk_create_categories(self, df: pd.DataFrame) -> Dict:
        """Bulk create categories."""
        unique_categories = df['Category'].unique()

        # Check existing categories
        existing_categories = {
            c.name: c 
            for c in Category.objects.filter(user=self.user)
        }

        # Create missing categories
        categories_to_create = [
            Category(name=name, user=self.user)
            for name in unique_categories
            if name not in existing_categories
        ]

        if categories_to_create:
            Category.objects.bulk_create(categories_to_create, ignore_conflicts=True)

        # Refresh lookup with optimized query
        return {
            c.name: c 
            for c in Category.objects.filter(user=self.user).only('id', 'name')
        }

    def _bulk_create_accounts(self, df: pd.DataFrame) -> Dict:
        """Bulk create accounts."""
        unique_accounts = df['Account'].unique()

        # Check existing accounts
        existing_accounts = {
            a.name: a 
            for a in Account.objects.filter(user=self.user)
        }

        # Create missing accounts
        accounts_to_create = [
            Account(
                name=name, 
                user=self.user,
                currency=self.default_currency,
                account_type=self.default_account_type
            )
            for name in unique_accounts
            if name not in existing_accounts
        ]

        if accounts_to_create:
            Account.objects.bulk_create(accounts_to_create, ignore_conflicts=True)

        # Refresh lookup with optimized query
        return {
            a.name: a 
            for a in Account.objects.filter(user=self.user).only('id', 'name', 'currency_id', 'account_type_id')
        }

    def _bulk_create_transactions(
        self, 
        df: pd.DataFrame, 
        period_lookup: Dict, 
        category_lookup: Dict, 
        account_lookup: Dict
    ) -> int:
        """Optimized bulk create transactions with improved tag handling."""
        # Pre-process all tags to create them upfront
        all_tag_names = set()
        transactions_data = []
        
        logger.info(f"🔍 [BulkTransactionImporter] Pre-processing {len(df)} transactions for tag extraction...")
        
        for index, row in df.iterrows():
            try:
                transaction_date = row['Date']
                year, month = transaction_date.year, transaction_date.month

                # Get objects from lookups
                period = period_lookup.get((year, month))
                account = account_lookup.get(row['Account'])
                category = category_lookup.get(row['Category'])

                if not (period and account and category):
                    logger.warning(f"Skipping row {index}: missing period, account, or category")
                    continue

                # Ensure Income and Expense amounts are positive
                amount = Decimal(str(row['Amount']))
                if row['Type'] in ['IN', 'EX']:
                    amount = abs(amount)
                
                # Extract and clean tags
                tags_str = row.get('Tags', '')
                tag_names = []
                
                if tags_str and pd.notna(tags_str) and str(tags_str).strip():
                    tags_str_clean = str(tags_str).strip()
                    if tags_str_clean.lower() not in ['nan', 'none', 'null', '']:
                        raw_tags = tags_str_clean.split(',')
                        for tag_name in raw_tags:
                            cleaned_name = tag_name.strip()
                            if cleaned_name and cleaned_name.lower() not in ['nan', 'none', 'null', '']:
                                tag_names.append(cleaned_name)
                                all_tag_names.add(cleaned_name)
                
                # Store transaction data
                transactions_data.append({
                    'transaction': Transaction(
                        user=self.user,
                        type=row['Type'],
                        amount=amount,
                        date=transaction_date,
                        category=category,
                        account=account,
                        period=period,
                        notes=row.get('Notes', ''),
                        is_estimated=False
                    ),
                    'tag_names': tag_names
                })

            except Exception as e:
                logger.warning(f"Skipping row {index}: {e}")
                continue

        logger.info(f"📊 [BulkTransactionImporter] Processed {len(transactions_data)} valid transactions with {len(all_tag_names)} unique tags")
        
        # Bulk create all tags upfront
        if all_tag_names:
            logger.info(f"🏷️ [BulkTransactionImporter] Creating {len(all_tag_names)} unique tags...")
            self._bulk_create_tags(all_tag_names)
        
        # Get all tags for lookup with optimized query
        existing_tags = {}
        if all_tag_names:
            # Only fetch tags that we actually need
            tags_queryset = Tag.objects.filter(
                user=self.user,
                name__in=all_tag_names
            ).only('id', 'name')  # Only fetch required fields
            
            existing_tags = {tag.name.lower(): tag for tag in tags_queryset}
        
        logger.info(f"🏷️ [BulkTransactionImporter] Got {len(existing_tags)} tags for lookup")
        
        # Now bulk create transactions and their tag relationships
        return self._bulk_create_transactions_with_tags(transactions_data, existing_tags)

    def _bulk_create_tags(self, tag_names: set) -> None:
        """Bulk create all missing tags upfront - optimized version."""
        from ..models import Tag
        
        if not tag_names:
            return
        
        # Get existing tag names for this user in a single query
        existing_tag_names = set(
            Tag.objects.filter(user=self.user, name__in=tag_names)
            .values_list('name', flat=True)
        )
        
        # Create only missing tags
        missing_tag_names = tag_names - existing_tag_names
        if missing_tag_names:
            tags_to_create = [Tag(user=self.user, name=name) for name in missing_tag_names]
            # Use batch_size for very large tag sets
            if len(tags_to_create) > 500:
                # Create in chunks to avoid memory issues
                for i in range(0, len(tags_to_create), 500):
                    chunk = tags_to_create[i:i + 500]
                    Tag.objects.bulk_create(chunk, ignore_conflicts=True)
                logger.info(f"✅ [BulkTransactionImporter] Created {len(tags_to_create)} new tags in chunks")
            else:
                Tag.objects.bulk_create(tags_to_create, ignore_conflicts=True)
                logger.info(f"✅ [BulkTransactionImporter] Created {len(tags_to_create)} new tags")

    def _bulk_create_transactions_with_tags(self, transactions_data: List[Dict], existing_tags: Dict) -> int:
        """Bulk create transactions and their tag relationships efficiently."""
        from ..models import TransactionTag
        from django.db import IntegrityError
        
        total_imported = 0
        
        # Process in batches
        for i in range(0, len(transactions_data), self.batch_size):
            batch_data = transactions_data[i:i + self.batch_size]
            logger.info(f"📦 [BulkTransactionImporter] Processing batch {i//self.batch_size + 1}/{(len(transactions_data) + self.batch_size - 1)//self.batch_size}")
            
            # Prepare transactions for bulk creation
            transactions_to_create = [item['transaction'] for item in batch_data]
            
            # Use bulk_create with batch_size for better memory management
            try:
                # Use smaller batch sizes for better memory management and avoid conflicts
                batch_size = min(500, len(transactions_to_create))
                created_transactions_list = Transaction.objects.bulk_create(
                    transactions_to_create, 
                    batch_size=batch_size,
                    ignore_conflicts=False
                )
                logger.info(f"💰 [BulkTransactionImporter] Created {len(created_transactions_list)} transactions with IDs in batch of {batch_size}")
                
                # Pre-calculate all tag relationships for better performance
                transaction_tag_objects = []
                for j, created_tx in enumerate(created_transactions_list):
                    if j < len(batch_data):
                        tag_names = batch_data[j]['tag_names']
                        # Batch process tag lookups
                        for tag_name in tag_names:
                            tag = existing_tags.get(tag_name.lower())
                            if tag:
                                transaction_tag_objects.append(
                                    TransactionTag(transaction=created_tx, tag=tag)
                                )
                
                # Bulk create tag relationships
                if transaction_tag_objects:
                    TransactionTag.objects.bulk_create(transaction_tag_objects, ignore_conflicts=True)
                    logger.info(f"🏷️ [BulkTransactionImporter] Created {len(transaction_tag_objects)} tag relationships")
                
                total_imported += len(created_transactions_list)
                
            except IntegrityError as e:
                # Fallback: if there are conflicts, use ignore_conflicts and fetch IDs manually
                logger.warning(f"⚠️ [BulkTransactionImporter] Integrity error, falling back to conflict-safe mode: {e}")
                
                Transaction.objects.bulk_create(transactions_to_create, ignore_conflicts=True)
                logger.info(f"💰 [BulkTransactionImporter] Created {len(transactions_to_create)} transactions (conflict-safe)")
                
                # Use a more efficient bulk query with select_related to avoid N+1 queries
                unique_dates = set(item['transaction'].date for item in batch_data)
                unique_amounts = set(item['transaction'].amount for item in batch_data)
                
                recent_transactions = Transaction.objects.filter(
                    user=self.user,
                    date__in=unique_dates,
                    amount__in=unique_amounts
                ).select_related('category', 'account', 'period').order_by('-id')
                
                # Create a more efficient hash-based lookup using multiple criteria
                tx_lookup = {}
                for tx in recent_transactions:
                    # Create multiple possible keys for better matching
                    primary_key = (tx.date, tx.amount, tx.type, tx.category_id, tx.account_id, tx.period_id)
                    secondary_key = (tx.date, tx.amount, tx.type, tx.category.name, tx.account.name)
                    
                    if primary_key not in tx_lookup:
                        tx_lookup[primary_key] = tx
                    if secondary_key not in tx_lookup:
                        tx_lookup[secondary_key] = tx
                
                # Match transactions with their tag data
                transaction_tag_objects = []
                matched_count = 0
                for item in batch_data:
                    tx_data = item['transaction']
                    key = (tx_data.date, tx_data.amount, tx_data.type, tx_data.category.id, tx_data.account.id, tx_data.period.id)
                    
                    if key in tx_lookup:
                        matched_tx = tx_lookup[key]
                        matched_count += 1
                        
                        for tag_name in item['tag_names']:
                            tag = existing_tags.get(tag_name.lower())
                            if tag:
                                transaction_tag_objects.append(
                                    TransactionTag(transaction=matched_tx, tag=tag)
                                )
                
                logger.info(f"🔍 [BulkTransactionImporter] Matched {matched_count} transactions for tag linking")
                
                # Bulk create tag relationships
                if transaction_tag_objects:
                    TransactionTag.objects.bulk_create(transaction_tag_objects, ignore_conflicts=True)
                    logger.info(f"🏷️ [BulkTransactionImporter] Created {len(transaction_tag_objects)} tag relationships")
                
                total_imported += len(transactions_to_create)
        
        logger.info(f"✅ [BulkTransactionImporter] Total imported: {total_imported} transactions")
        return total_imported

    