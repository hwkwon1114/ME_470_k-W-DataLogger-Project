from flask import Flask, render_template, jsonify
import pandas as pd

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    df = pd.read_csv('data.csv')
    # Assuming the CSV has columns 'time' and 'kw_per_ton'
    data = {
        'time': df['time'].tolist(),
        'kw_per_ton': df['kw_per_ton'].tolist()
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
