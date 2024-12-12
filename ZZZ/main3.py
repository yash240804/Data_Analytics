from flask import Flask, render_template, request, jsonify
import pandas as pd
import sqlite3
import pytz
import plotly.express as px
import json

# Flask app initialization
app = Flask(__name__)

# Set your local time zone
local_tz = pytz.timezone("Asia/Kolkata")

def hour_to_range(hour):
    start_hour = hour
    end_hour = (hour + 1) % 24
    start_label = f"{start_hour % 12 or 12} {'AM' if start_hour < 12 else 'PM'}"
    end_label = f"{end_hour % 12 or 12} {'AM' if end_hour < 12 else 'PM'}"
    return f"{start_label} to {end_label}"

# Connect to SQLite database and load data
def load_data():
    db_path = "rag_app.db"  # Replace with your database path
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM application_logs"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Parse timestamps and adjust to the local timezone
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['created_at'] = df['created_at'].dt.tz_localize('UTC').dt.tz_convert(local_tz)
    df['hour'] = df['created_at'].dt.hour
    df['date'] = df['created_at'].dt.date

    # Add a time range column
    def hour_to_range(hour):
        start_hour = hour
        end_hour = (hour + 1) % 24
        start_label = f"{start_hour % 12 or 12} {'AM' if start_hour < 12 else 'PM'}"
        end_label = f"{end_hour % 12 or 12} {'AM' if end_hour < 12 else 'PM'}"
        return f"{start_label} to {end_label}"

    df['time_range'] = df['hour'].apply(hour_to_range)
    return df

dataframe = load_data()

# Extract location-based FAQs
def extract_location_faqs_from_queries(df, locations):
    if 'user_query' in df.columns:
        location_faqs = []
        for location in locations:
            queries = df[df['user_query'].str.contains(location, case=False, na=False)]['user_query'].unique()
            if len(queries) > 0:
                location_faqs.append({'college_location': location, 'user_query': list(queries)})
        return pd.DataFrame(location_faqs)
    else:
        return pd.DataFrame(columns=['college_location', 'user_query'])

known_locations = ["Jaipur", "Ajmer", "Jodhpur", "Udaipur", "Kota", "Bikaner"]
location_faqs_df = extract_location_faqs_from_queries(dataframe, known_locations)

# Flask routes
@app.route('/')
def index():
    # Prepare data for peak times graph
    peak_data = dataframe.groupby('time_range').size().reset_index(name='count')

    peak_data['time_range'] = pd.Categorical(peak_data['time_range'], 
                                             categories=[hour_to_range(h) for h in range(24)], 
                                             ordered=True)
    
    peak_data = peak_data.sort_values('time_range')
    fig_peak = px.bar(
        peak_data, 
        x='time_range', 
        y='count', 
        title='Peak User Interaction Times',
        labels={'time_range': 'Time Range', 'count': 'Interactions'},
        text='count'
    )
    fig_peak.update_traces(texttemplate='%{text}', textposition='outside')
    peak_graph = json.dumps(fig_peak, cls=px.utils.PlotlyJSONEncoder)

    # Pass data to template
    return render_template('index.html', peak_graph=peak_graph, locations=known_locations)

@app.route('/location-faqs', methods=['POST'])
def location_faqs():
    location = request.json.get('location')
    if location:
        faqs = location_faqs_df[location_faqs_df['college_location'] == location]['user_query'].values
        if len(faqs) > 0:
            return jsonify({'faqs': faqs[0]})
    return jsonify({'faqs': []})

if __name__ == "__main__":
    app.run(debug=True)