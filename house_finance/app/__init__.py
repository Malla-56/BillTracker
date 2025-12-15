from flask import Flask
import os

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    app.config['DB_FILE'] = os.path.join(app.root_path, '..', 'finance.db')
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    from .routes import main
    app.register_blueprint(main)
    
    from .models import init_db
    init_db(app.config['DB_FILE'])
    
    # Auto-import existing CSVs in uploads folder
    from .utils import import_csv_to_db
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.lower().endswith('.csv'):
                csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                print(f"Auto-importing: {filename}")
                import_csv_to_db(csv_path, app.config['DB_FILE'])
    
    return app
