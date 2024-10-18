from flask import Flask, render_template, jsonify
import pandas as pd
import threading
from data_generator import generate_live_data

app = Flask(__name__)

CSV_FILE = 'live_data.csv'

# Start the data generation in a separate thread
data_thread = threading.Thread(target=generate_live_data, args=(CSV_FILE, 5))
data_thread.daemon = True
data_thread.start()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/get_data')
def get_data():
    try:
        df = pd.read_csv(CSV_FILE)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df = df.sort_values('Timestamp', ascending=False).head(30)
        columns = df.columns.tolist()
        data = df.to_dict(orient='records')
        return jsonify({
            'columns': columns,
            'data': data
        })
    except pd.errors.EmptyDataError:
        return jsonify({
            'columns': [],
            'data': []
        })
    except Exception as e:
        app.logger.error(f"Error reading CSV file: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)