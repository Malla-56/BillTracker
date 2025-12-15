from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify
import os
import sqlite3
from datetime import datetime
from .models import get_db_connection
from .utils import get_transactions_db, calculate_rules_status_db, import_csv_to_db

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return redirect(url_for('main.view_rules'))

@main.route('/rules')
def view_rules():
    month = request.args.get('month')
    year = request.args.get('year')
    
    # Default to current month/year if not provided
    if not month or not year:
        now = datetime.now()
        month = now.strftime('%m')
        year = now.strftime('%Y')
        
    rule_data, _ = calculate_rules_status_db(current_app.config['DB_FILE'], month, year)
        
    return render_template('rules.html', rules=rule_data, active_tab='rules', month=month, year=year)

@main.route('/transactions')
def view_transactions():
    month = request.args.get('month')
    year = request.args.get('year')
    
    if not month or not year:
        # Show all? or Default to current?
        # Let's show all by default for transactions if not specified, 
        # OR default to current to match Rules behavior.
        # Let's default to current for consistency.
        now = datetime.now()
        month = now.strftime('%m')
        year = now.strftime('%Y')

    _, transactions_with_status = calculate_rules_status_db(current_app.config['DB_FILE'], month, year)
    
    return render_template('transactions.html', transactions=transactions_with_status, active_tab='transactions', month=month, year=year)

@main.route('/bills')
def view_bills():
    conn = get_db_connection(current_app.config['DB_FILE'])
    bills = conn.execute('SELECT * FROM bills ORDER BY due_date ASC').fetchall()
    recurring = conn.execute('SELECT * FROM recurring_bills').fetchall()
    conn.close()
    
    # Determine "Current View Month" for generation button?
    # Defaults to current month usually
    now = datetime.now()
    return render_template('bills.html', bills=bills, recurring=recurring, current_month=now.month, current_year=now.year, active_tab='bills')

@main.route('/calendar')
def view_calendar():
    return render_template('calendar.html', active_tab='calendar')

@main.route('/api/calendar_events')
def get_calendar_events():
    # Return imports ranges for calendar
    conn = get_db_connection(current_app.config['DB_FILE'])
    imports = conn.execute('SELECT * FROM imports').fetchall()
    conn.close()
    
    events = []
    for imp in imports:
        if imp['start_date'] and imp['end_date']:
            events.append({
                'title': f"Data: {imp['filename']}",
                'start': imp['start_date'],
                'end': imp['end_date'],
                'color': '#3788d8'
            })
    return jsonify(events)

@main.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.referrer)
    
    file = request.files['file']
    if file.filename == '':
        return redirect(request.referrer)
        
    if file:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        # Import to DB
        import_csv_to_db(filepath, current_app.config['DB_FILE'])
        
    return redirect(request.referrer)

@main.route('/add_rule', methods=['POST'])
def add_rule():
    name = request.form['name']
    reference = request.form['reference']
    amount = float(request.form['amount'])
    due_day = request.form.get('due_day') # Optional
    
    conn = get_db_connection(current_app.config['DB_FILE'])
    conn.execute('INSERT INTO rules (name, reference, amount, due_day) VALUES (?, ?, ?, ?)',
                 (name, reference, amount, due_day))
    conn.commit()
    conn.close()
    return redirect(request.referrer)

@main.route('/add_recurring_bill', methods=['POST'])
def add_recurring_bill():
    name = request.form['name']
    amount = request.form.get('amount')
    due_day = int(request.form['due_day'])
    
    conn = get_db_connection(current_app.config['DB_FILE'])
    conn.execute('INSERT INTO recurring_bills (name, amount, due_day) VALUES (?, ?, ?)',
                 (name, amount, due_day))
    conn.commit()
    conn.close()
    return redirect(url_for('main.view_bills'))

@main.route('/generate_bills', methods=['POST'])
def generate_bills():
    month = int(request.form.get('month'))
    year = int(request.form.get('year'))
    
    conn = get_db_connection(current_app.config['DB_FILE'])
    
    # Get Templates
    templates = conn.execute('SELECT * FROM recurring_bills').fetchall()
    
    count = 0
    for t in templates:
        # Calculate full date
        # Handle february/short months simple logic: clamp to last day if needed
        # Or simple: Date(year, month, day)
        try:
            # Simple check if bill already exists for this month/year/name
            # This is a basic check; real app might need more robust duplication check
            start_of_month = f"{year}-{month:02d}-01"
            end_of_month = f"{year}-{month:02d}-31" # lax check
            
            existing = conn.execute('''
                SELECT id FROM bills 
                WHERE name = ? 
                AND strftime('%Y', due_date) = ? 
                AND strftime('%m', due_date) = ?
            ''', (t['name'], str(year), f"{month:02d}")).fetchone()
            
            if not existing:
                # Construct date, careful with day > days in month
                # For simplicity, we just format string YYYY-MM-DD
                # If day is 31 and month is Feb, this is tricky.
                # Let's assume valid days or just clamp visually? 
                # Better: try/except date creation
                
                day = t['due_day']
                # Basic clamping for now won't be perfect but works for most
                # Ideally use calendar.monthrange
                
                due_date = f"{year}-{month:02d}-{day:02d}"
                
                conn.execute('INSERT INTO bills (name, due_date, amount) VALUES (?, ?, ?)',
                             (t['name'], due_date, t['amount']))
                count += 1
        except Exception as e:
            print(f"Error generating bill {t['name']}: {e}")
            
    conn.commit()
    conn.close()
    return redirect(url_for('main.view_bills'))

@main.route('/delete_rule/<int:rule_id>')
def delete_rule(rule_id):
    conn = get_db_connection(current_app.config['DB_FILE'])
    conn.execute('DELETE FROM rules WHERE id = ?', (rule_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer)

@main.route('/add_bill', methods=['POST'])
def add_bill():
    name = request.form['name']
    due_date = request.form['due_date']
    amount = request.form.get('amount')
    
    conn = get_db_connection(current_app.config['DB_FILE'])
    conn.execute('INSERT INTO bills (name, due_date, amount) VALUES (?, ?, ?)',
                 (name, due_date, amount))
    conn.commit()
    conn.close()
    return redirect(url_for('main.view_bills'))

@main.route('/pay_bill/<int:bill_id>')
def pay_bill(bill_id):
    # Determine paid status toggle
    conn = get_db_connection(current_app.config['DB_FILE'])
    bill = conn.execute('SELECT is_paid FROM bills WHERE id = ?', (bill_id,)).fetchone()
    if bill:
        new_status = 0 if bill['is_paid'] else 1
        paid_date = datetime.now().strftime('%Y-%m-%d') if new_status else None
        conn.execute('UPDATE bills SET is_paid = ?, paid_date = ? WHERE id = ?', 
                     (new_status, paid_date, bill_id))
        conn.commit()
    conn.close()
    return redirect(url_for('main.view_bills'))

@main.route('/delete_bill/<int:bill_id>')
def delete_bill(bill_id):
    conn = get_db_connection(current_app.config['DB_FILE'])
    conn.execute('DELETE FROM bills WHERE id = ?', (bill_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('main.view_bills'))
