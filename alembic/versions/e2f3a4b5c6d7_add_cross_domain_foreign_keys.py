"""add cross-domain foreign keys across all domain tables

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-04-26 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # accounts → users
    op.create_foreign_key(
        'fk_bank_accounts_user_id', 'bank_accounts', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_credit_cards_user_id', 'credit_cards', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )

    # transactions → users
    op.create_foreign_key(
        'fk_transactions_user_id', 'transactions', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    # transaction_items → categories
    op.create_foreign_key(
        'fk_transaction_items_category_id', 'transaction_items', 'categories',
        ['category_id'], ['id'], ondelete='RESTRICT',
    )

    # categorization → users
    op.create_foreign_key(
        'fk_categories_user_id', 'categories', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_categorization_rules_user_id', 'categorization_rules', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )

    # earnings → users, transactions, earning_sources
    op.create_foreign_key(
        'fk_earning_sources_user_id', 'earning_sources', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_earnings_user_id', 'earnings', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_earnings_transaction_id', 'earnings', 'transactions',
        ['transaction_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_earnings_source_id', 'earnings', 'earning_sources',
        ['source_id'], ['id'], ondelete='SET NULL',
    )

    # investments → users, bank_accounts
    op.create_foreign_key(
        'fk_holdings_user_id', 'holdings', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_sip_registrations_user_id', 'sip_registrations', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_sip_registrations_bank_account_id', 'sip_registrations', 'bank_accounts',
        ['bank_account_id'], ['id'], ondelete='SET NULL',
    )

    # budgets → users, categories
    op.create_foreign_key(
        'fk_budget_goals_user_id', 'budget_goals', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_budget_goals_category_id', 'budget_goals', 'categories',
        ['category_id'], ['id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_budget_progress_user_id', 'budget_progress', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )

    # peers → users, transactions
    op.create_foreign_key(
        'fk_peer_contacts_user_id', 'peer_contacts', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_peer_balances_user_id', 'peer_balances', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_peer_balances_linked_transaction_id', 'peer_balances', 'transactions',
        ['linked_transaction_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_peer_settlements_linked_transaction_id', 'peer_settlements', 'transactions',
        ['linked_transaction_id'], ['id'], ondelete='SET NULL',
    )

    # notifications → users
    op.create_foreign_key(
        'fk_notifications_user_id', 'notifications', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )

    # statements → users, categories, transactions
    op.create_foreign_key(
        'fk_statement_uploads_user_id', 'statement_uploads', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_raw_extracted_rows_ai_category_id', 'raw_extracted_rows', 'categories',
        ['ai_suggested_category_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_raw_extracted_rows_final_category_id', 'raw_extracted_rows', 'categories',
        ['final_category_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_raw_extracted_rows_transaction_id', 'raw_extracted_rows', 'transactions',
        ['transaction_id'], ['id'], ondelete='SET NULL',
    )

    # import_ → users
    op.create_foreign_key(
        'fk_import_jobs_user_id', 'import_jobs', 'users',
        ['user_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_import_jobs_user_id', 'import_jobs', type_='foreignkey')

    op.drop_constraint('fk_raw_extracted_rows_transaction_id', 'raw_extracted_rows', type_='foreignkey')
    op.drop_constraint('fk_raw_extracted_rows_final_category_id', 'raw_extracted_rows', type_='foreignkey')
    op.drop_constraint('fk_raw_extracted_rows_ai_category_id', 'raw_extracted_rows', type_='foreignkey')
    op.drop_constraint('fk_statement_uploads_user_id', 'statement_uploads', type_='foreignkey')

    op.drop_constraint('fk_notifications_user_id', 'notifications', type_='foreignkey')

    op.drop_constraint('fk_peer_settlements_linked_transaction_id', 'peer_settlements', type_='foreignkey')
    op.drop_constraint('fk_peer_balances_linked_transaction_id', 'peer_balances', type_='foreignkey')
    op.drop_constraint('fk_peer_balances_user_id', 'peer_balances', type_='foreignkey')
    op.drop_constraint('fk_peer_contacts_user_id', 'peer_contacts', type_='foreignkey')

    op.drop_constraint('fk_budget_progress_user_id', 'budget_progress', type_='foreignkey')
    op.drop_constraint('fk_budget_goals_category_id', 'budget_goals', type_='foreignkey')
    op.drop_constraint('fk_budget_goals_user_id', 'budget_goals', type_='foreignkey')

    op.drop_constraint('fk_sip_registrations_bank_account_id', 'sip_registrations', type_='foreignkey')
    op.drop_constraint('fk_sip_registrations_user_id', 'sip_registrations', type_='foreignkey')
    op.drop_constraint('fk_holdings_user_id', 'holdings', type_='foreignkey')

    op.drop_constraint('fk_earnings_source_id', 'earnings', type_='foreignkey')
    op.drop_constraint('fk_earnings_transaction_id', 'earnings', type_='foreignkey')
    op.drop_constraint('fk_earnings_user_id', 'earnings', type_='foreignkey')
    op.drop_constraint('fk_earning_sources_user_id', 'earning_sources', type_='foreignkey')

    op.drop_constraint('fk_categorization_rules_user_id', 'categorization_rules', type_='foreignkey')
    op.drop_constraint('fk_categories_user_id', 'categories', type_='foreignkey')

    op.drop_constraint('fk_transaction_items_category_id', 'transaction_items', type_='foreignkey')
    op.drop_constraint('fk_transactions_user_id', 'transactions', type_='foreignkey')

    op.drop_constraint('fk_credit_cards_user_id', 'credit_cards', type_='foreignkey')
    op.drop_constraint('fk_bank_accounts_user_id', 'bank_accounts', type_='foreignkey')
