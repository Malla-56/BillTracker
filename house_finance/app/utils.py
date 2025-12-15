import csv
import os
import sqlite3
from datetime import datetime

def parse_date_ing(date_str):
    # ING CSVs usually dd/mm/yyyy
    try:
        return datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError:
        return date_str # Fallback

def import_csv_to_db(csv_path, db_path):
    transactions = []
    if not os.path.exists(csv_path):
        return None
    
    filename = os.path.basename(csv_path)
    # Basic check if already imported? For now allow re-import or appending.
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if already imported
    existing = cursor.execute('SELECT id FROM imports WHERE filename = ?', (filename,)).fetchone()
    if existing:
        conn.close()
        print(f"Skipping {filename}, already imported.")
        return False
    
    # Create Import Record
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('INSERT INTO imports (filename, upload_date) VALUES (?, ?)', (filename, today))
    import_id = cursor.lastrowid
    
    min_date = None
    max_date = None
    
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile:
            # Check empty
            csvfile.seek(0)
            if not csvfile.read(1):
                return None
            csvfile.seek(0)
            
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                description = row.get('Description', '')
                date_str = row.get('Date', '')
                
                # Format Date YYYY-MM-DD for sorting/filtering
                date_iso = parse_date_ing(date_str)
                
                if not min_date or date_iso < min_date: min_date = date_iso
                if not max_date or date_iso > max_date: max_date = date_iso

                amount = 0.0
                try:
                    credit_str = row.get('Credit', '').strip()
                    debit_str = row.get('Debit', '').strip()
                    
                    if credit_str:
                        amount = float(credit_str)
                    elif debit_str:
                        amount = float(debit_str)
                        if amount > 0: amount = -amount
                    else:
                        amount_str = row.get('Amount', '').strip()
                        if amount_str: amount = float(amount_str)
                except ValueError:
                    continue
                    
                cursor.execute('''
                    INSERT INTO transactions (date, description, amount, source_file, import_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (date_iso, description, amount, filename, import_id))
                
        # Update import record with range
        if min_date and max_date:
            cursor.execute('UPDATE imports SET start_date = ?, end_date = ? WHERE id = ?', 
                           (min_date, max_date, import_id))
            
        conn.commit()
    except Exception as e:
        print(f"Error importing CSV: {e}")
        conn.rollback()
    finally:
        conn.close()
        
    return True

def get_transactions_db(db_path, month=None, year=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    
    if month and year:
        # SQLite substr(date, 1, 4) = 'YYYY' and substr(date, 6, 2) = 'MM'
        # Assuming date is YYYY-MM-DD
        query += " AND strftime('%Y', date) = ? AND strftime('%m', date) = ?"
        params.append(str(year))
        params.append(f"{int(month):02d}")
        
    query += " ORDER BY date DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    # Convert to dict
    return [dict(row) for row in rows]

def calculate_rules_status_db(db_path, month=None, year=None):
    # Fetch rules
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rules = conn.execute('SELECT * FROM rules').fetchall()
    conn.close()
    
    # Fetch transactions for filter
    transactions = get_transactions_db(db_path, month, year)
    
    # Add 'matched_rule' to transactions
    for t in transactions:
        t['matched_rule'] = None

    rule_statuses = []

    for rule in rules:
        total_paid = 0.0
        ref = rule['reference'].lower()
        
        for t in transactions:
            if ref in t['description'].lower():
                # Only count INCOME (positive amounts) towards payment rules usually
                if t['amount'] > 0:
                    total_paid += t['amount']
                    t['matched_rule'] = rule['name']
                
        expected = rule['amount']
        
        status = 'UNPAID'
        color = 'danger'
        
        if total_paid >= expected:
            status = 'PAID'
            color = 'success'
        elif total_paid > 0:
            status = 'PARTIAL'
            color = 'warning'
            
        rule_statuses.append({
            'id': rule['id'],
            'name': rule['name'],
            'reference': rule['reference'],
            'expected': expected,
            'paid': total_paid,
            'status': status,
            'color': color
        })
        
    return rule_statuses, transactions
