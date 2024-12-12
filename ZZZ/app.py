from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
import plotly.express as px
import json

app = Flask(__name__)

# Database setup
DB_PATH = "rag_app.db"  # Update this to the correct path of your SQLite database

# Function to load data
def load_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM application_logs"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

# Function to generate graphs
def generate_graphs(df):
    # Peak User Interaction Times
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['hour'] = df['created_at'].dt.hour
    peak_data = df['hour'].value_counts().reset_index(name='count')
    peak_data.columns = ['hour', 'count']
    fig_peak = px.bar(peak_data, x='hour', y='count', title="Peak Interaction Times", labels={'hour': 'Hour', 'count': 'Interactions'})
    fig_peak.update_traces(texttemplate='%{y}', textposition='outside')
    graphJSON_peak = json.dumps(fig_peak, cls=px.json.PlotlyJSONEncoder)

    # Top FAQs
    if 'user_query' in df.columns:
        faq_data = df['user_query'].value_counts().reset_index(name='count').head(10)
        faq_data.columns = ['query', 'count']
        fig_faqs = px.bar(faq_data, x='query', y='count', title="Top FAQs", labels={'query': 'Query', 'count': 'Frequency'})
        fig_faqs.update_traces(texttemplate='%{y}', textposition='outside')
        graphJSON_faqs = json.dumps(fig_faqs, cls=px.json.PlotlyJSONEncoder)
    else:
        graphJSON_faqs = None

    return graphJSON_peak, graphJSON_faqs

# Routes
@app.route("/")
def index():
    df = load_data()
    graph_peak, graph_faqs = generate_graphs(df)
    return render_template("index.html", graph_peak=graph_peak, graph_faqs=graph_faqs)

@app.route("/get_faqs", methods=["POST"])
def get_faqs():
    data = request.get_json()
    location = data.get("location", "").strip().lower()
    if not location:
        return jsonify({"error": "No location provided"}), 400

    try:
        df = load_data()
        if 'user_query' in df.columns:
            faqs = df[df['user_query'].str.contains(location, case=False, na=False)]['user_query'].unique()
            return jsonify(faqs.tolist())
        else:
            return jsonify({"error": "Column 'user_query' not found"}), 500
    except Exception as e:
        print(f"Error in get_faqs: {e}")
        return jsonify({"error": "An error occurred"}), 500

if __name__ == "__main__":
    app.run(debug=True)
