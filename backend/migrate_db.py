"""
DB 마이그레이션 스크립트 - 누락된 컬럼 추가 및 새 테이블 생성
"""
import sqlite3

DB_PATH = "billing.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 테이블별 누락 컬럼 추가
    migrations = [
        # slip_configs 테이블
        ("slip_configs", "rounding_rule", "VARCHAR(20) DEFAULT 'floor'"),
        ("slip_configs", "hkont_sales_export", "VARCHAR(20) DEFAULT '41021020'"),

        # slip_configs - 환율 규칙 (매출)
        ("slip_configs", "exchange_rate_rule_sales", "VARCHAR(30) DEFAULT 'document_date'"),
        ("slip_configs", "exchange_rate_type_sales", "VARCHAR(20) DEFAULT 'send_rate'"),

        # slip_configs - 환율 규칙 (매입)
        ("slip_configs", "exchange_rate_rule_purchase", "VARCHAR(30) DEFAULT 'document_date'"),
        ("slip_configs", "exchange_rate_type_purchase", "VARCHAR(20) DEFAULT 'basic_rate'"),

        # slip_configs - 환율 규칙 (해외법인)
        ("slip_configs", "exchange_rate_rule_overseas", "VARCHAR(30) DEFAULT 'first_of_billing_month'"),
        ("slip_configs", "exchange_rate_type_overseas", "VARCHAR(20) DEFAULT 'basic_rate'"),

        # slip_configs - 일할 계산 설정
        ("slip_configs", "pro_rata_enabled", "BOOLEAN DEFAULT 1"),
        ("slip_configs", "pro_rata_calculation", "VARCHAR(30) DEFAULT 'calendar_days'"),

        # slip_records 테이블
        ("slip_records", "tax_code", "VARCHAR(10)"),
        ("slip_records", "dmbtr_c", "FLOAT"),
        ("slip_records", "source_type", "VARCHAR(30) DEFAULT 'billing'"),
        ("slip_records", "additional_charge_id", "INTEGER"),
        ("slip_records", "split_rule_id", "INTEGER"),
        ("slip_records", "split_allocation_id", "INTEGER"),
        ("slip_records", "pro_rata_ratio", "FLOAT"),
        ("slip_records", "original_amount", "FLOAT"),

        # contract_billing_profiles 테이블
        ("contract_billing_profiles", "exchange_rate_type", "VARCHAR(20)"),
        ("contract_billing_profiles", "custom_exchange_rate_date", "DATE"),
        ("contract_billing_profiles", "rounding_rule_override", "VARCHAR(20)"),
        ("contract_billing_profiles", "pro_rata_override", "VARCHAR(20)"),

        # exchange_rates 테이블 (HB 환율 정보)
        ("exchange_rates", "basic_rate", "FLOAT"),
        ("exchange_rates", "send_rate", "FLOAT"),
        ("exchange_rates", "buy_rate", "FLOAT"),
        ("exchange_rates", "sell_rate", "FLOAT"),

        # hb_contracts 테이블 - 계약 시작/종료일
        ("hb_contracts", "contract_start_date", "DATE"),
        ("hb_contracts", "contract_end_date", "DATE"),
    ]

    for table, column, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"Added {column} to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {column} already exists in {table}")
            else:
                print(f"Error adding {column} to {table}: {e}")

    # 새 테이블 생성
    new_tables = [
        # 추가 비용 테이블
        """
        CREATE TABLE IF NOT EXISTS additional_charges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_seq INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            charge_type VARCHAR(20) DEFAULT 'other',
            amount FLOAT NOT NULL,
            currency VARCHAR(10) DEFAULT 'USD',
            recurrence_type VARCHAR(20) DEFAULT 'one_time',
            start_date DATE,
            end_date DATE,
            applies_to_sales BOOLEAN DEFAULT 1,
            applies_to_purchase BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_seq) REFERENCES hb_contracts(seq)
        )
        """,

        # 분할 청구 규칙 테이블
        """
        CREATE TABLE IF NOT EXISTS split_billing_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_account_id VARCHAR(50) NOT NULL,
            source_contract_seq INTEGER NOT NULL,
            name VARCHAR(200),
            effective_from DATE,
            effective_to DATE,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_account_id) REFERENCES hb_vendor_accounts(id),
            FOREIGN KEY (source_contract_seq) REFERENCES hb_contracts(seq)
        )
        """,

        # 분할 청구 배분 테이블
        """
        CREATE TABLE IF NOT EXISTS split_billing_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            target_company_seq INTEGER NOT NULL,
            split_type VARCHAR(20) DEFAULT 'percentage',
            split_value FLOAT NOT NULL,
            priority INTEGER DEFAULT 0,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rule_id) REFERENCES split_billing_rules(id) ON DELETE CASCADE,
            FOREIGN KEY (target_company_seq) REFERENCES hb_companies(seq)
        )
        """,

        # 일할 계산 기간 테이블
        """
        CREATE TABLE IF NOT EXISTS pro_rata_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_seq INTEGER NOT NULL,
            billing_cycle VARCHAR(10) NOT NULL,
            start_day INTEGER NOT NULL,
            end_day INTEGER NOT NULL,
            total_days INTEGER NOT NULL,
            active_days INTEGER NOT NULL,
            ratio FLOAT NOT NULL,
            is_manual BOOLEAN DEFAULT 0,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_seq) REFERENCES hb_contracts(seq)
        )
        """,
    ]

    for table_sql in new_tables:
        try:
            cursor.execute(table_sql)
            # 테이블 이름 추출
            table_name = table_sql.split("CREATE TABLE IF NOT EXISTS")[1].split("(")[0].strip()
            print(f"Created table {table_name}")
        except sqlite3.OperationalError as e:
            print(f"Error creating table: {e}")

    # 인덱스 생성
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_additional_charges_contract ON additional_charges(contract_seq)",
        "CREATE INDEX IF NOT EXISTS idx_split_rules_account ON split_billing_rules(source_account_id)",
        "CREATE INDEX IF NOT EXISTS idx_split_rules_contract ON split_billing_rules(source_contract_seq)",
        "CREATE INDEX IF NOT EXISTS idx_split_alloc_rule ON split_billing_allocations(rule_id)",
        "CREATE INDEX IF NOT EXISTS idx_split_alloc_company ON split_billing_allocations(target_company_seq)",
        "CREATE INDEX IF NOT EXISTS idx_pro_rata_contract ON pro_rata_periods(contract_seq)",
        "CREATE INDEX IF NOT EXISTS idx_pro_rata_cycle ON pro_rata_periods(billing_cycle)",
    ]

    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
            idx_name = index_sql.split("CREATE INDEX IF NOT EXISTS")[1].split("ON")[0].strip()
            print(f"Created index {idx_name}")
        except sqlite3.OperationalError as e:
            print(f"Error creating index: {e}")

    conn.commit()
    conn.close()
    print("\nMigration completed!")


if __name__ == "__main__":
    migrate()
