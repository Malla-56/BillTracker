import sqlite3

def get_db_connection(db_file):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_file):
    conn = get_db_connection(db_file)
    
    # Rules Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            reference TEXT NOT NULL,
            amount REAL NOT NULL
        )
    ''')
    
    # Transactions Table (New)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            description TEXT,
            amount REAL,
            source_file TEXT,
            category TEXT,
            import_id INTEGER
        )
    ''')
    
    # Imports Table (New - for Calendar ranges)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            start_date TEXT,
            end_date TEXT,
            upload_date TEXT
        )
    ''')
    
    # Bills Table (New)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            due_date TEXT NOT NULL,
            amount REAL,
            is_paid BOOLEAN DEFAULT 0,
            paid_date TEXT,
            transaction_id INTEGER,
            FOREIGN KEY(transaction_id) REFERENCES transactions(id)
        )
    ''')
    
    # Recurring Bills Table (New)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS recurring_bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL,
            due_day INTEGER NOT NULL
        )
    ''')
    
    # Migrations
    # Check for due_day in rules
    try:
        cur = conn.execute("PRAGMA table_info(rules)")
        columns = [row[1] for row in cur.fetchall()]
        if 'due_day' not in columns:
            print("Migrating: Adding due_day to rules table")
            conn.execute('ALTER TABLE rules ADD COLUMN due_day INTEGER')
    except Exception as e:
        print(f"Migration error: {e}")
    
    conn.commit()
    conn.close()
