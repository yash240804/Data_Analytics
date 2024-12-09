import sqlite3
import pandas as pd
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pytz

# Set your local time zone
local_tz = pytz.timezone("Asia/Kolkata")  # Replace with your local timezone if different

# Connect to SQLite database
db_path = "rag_app.db"  # Replace with your actual path
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if the 'in_scope' column exists
cursor.execute("PRAGMA table_info(application_logs)")
columns = [info[1] for info in cursor.fetchall()]
if "in_scope" not in columns:
    # Add the in_scope column if it doesn't exist
    cursor.execute("ALTER TABLE application_logs ADD COLUMN in_scope INTEGER DEFAULT 1")

    # Example logic: Mark queries as out-of-scope based on conditions
    cursor.execute("UPDATE application_logs SET in_scope = 0 WHERE user_query LIKE '%capital%' OR user_query LIKE '%2+2%'")

conn.commit()

# Load data from application_logs table (filtered for in-scope queries)
query = "SELECT * FROM application_logs WHERE in_scope = 1"
df = pd.read_sql_query(query, conn)
conn.close()

# Parse timestamps and adjust to the local timezone
df['created_at'] = pd.to_datetime(df['created_at'])  # Parse as datetime
df['created_at'] = df['created_at'].dt.tz_localize('UTC').dt.tz_convert(local_tz)  # Convert to local timezone
df['hour'] = df['created_at'].dt.hour  # Extract hour in 24-hour format
df['date'] = df['created_at'].dt.date

# Create a new column for time ranges
def hour_to_range(hour):
    start_hour = hour
    end_hour = (hour + 1) % 24
    start_label = f"{start_hour % 12 or 12} {'AM' if start_hour < 12 else 'PM'}"
    end_label = f"{end_hour % 12 or 12} {'AM' if end_hour < 12 else 'PM'}"
    return f"{start_label} to {end_label}"

df['time_range'] = df['hour'].apply(hour_to_range)

# Create Dash app
app = Dash(__name__)

# Layout for the dashboard
app.layout = html.Div([
    html.H1("AI Chatbot Insights Dashboard", style={'text-align': 'center'}),
    
    # Graph: Peak User Interaction Times
    dcc.Graph(id='peak-times', style={'height': '400px'}),
    
    # Graph: FAQs Trends
    dcc.Graph(id='faqs-trends', style={'height': '400px'}),
    
    # Graph: User Query Trends
    dcc.Graph(id='query-trends', style={'height': '400px'}),
    
    # Graph: Feedback Sentiments
    dcc.Graph(id='feedback-sentiments', style={'height': '400px'})
])

# Callback for graphs
@app.callback(
    [Output('peak-times', 'figure'),
     Output('faqs-trends', 'figure'),
     Output('query-trends', 'figure'),
     Output('feedback-sentiments', 'figure')],
    [Input('peak-times', 'id')]  # Placeholder input
)
def update_graphs(_):
    # Peak User Interaction Times
    peak_data = df.groupby('time_range').size().reset_index(name='count')
    peak_data['time_range'] = pd.Categorical(peak_data['time_range'], 
                                             categories=[hour_to_range(h) for h in range(24)], 
                                             ordered=True)
    peak_data = peak_data.sort_values('time_range')

    fig_peak = px.bar(
        peak_data, 
        x='time_range', 
        y='count', 
        title='Peak User Interaction Times',
        labels={'time_range': 'Time Range', 'count': 'Number of Interactions'},
        text='count'
    )
    fig_peak.update_traces(texttemplate='%{text}', textposition='outside')
    fig_peak.update_layout(xaxis=dict(tickmode='linear'))

    # FAQs Trends
    faq_data = df['user_query'].value_counts().reset_index(name='count').head(10)
    faq_data.columns = ['query', 'count']
    fig_faqs = px.bar(
        faq_data, 
        x='query', 
        y='count', 
        title='Top FAQs',
        labels={'query': 'Query', 'count': 'Count'},
        text='count'
    )
    fig_faqs.update_traces(texttemplate='%{text}', textposition='outside')

    # User Query Trends (Categorized)
    categories = {
        'Hostel': ['hostel', 'accommodation', 'room', 'stay'],
        'Placement': ['placement', 'job', 'career', 'opportunity'],
        'Fees': ['fees', 'cost', 'tuition', 'scholarship'],
        'Admission': ['admission', 'application', 'process', 'form'],
        'Curriculum': ['course', 'subject', 'curriculum', 'syllabus']
    }
    
    # Initialize category counts
    category_counts = {category: 0 for category in categories.keys()}
    
    for query in df['user_query'].str.lower():
        for category, keywords in categories.items():
            if any(keyword in query for keyword in keywords):
                category_counts[category] += 1
                break  # Stop checking once a match is found
    
    # Convert to percentage
    total_queries = sum(category_counts.values())
    category_data = pd.DataFrame({
        'Category': category_counts.keys(),
        'Percentage': [(count / total_queries) * 100 for count in category_counts.values()]
    })
    
    fig_trends = px.pie(
        category_data, 
        names='Category', 
        values='Percentage',
        title='User Query Trends by Category'
    )

    # Feedback Sentiments
    feedback_data = df['feedback'].value_counts().reset_index(name='count')
    feedback_data.columns = ['feedback', 'count']
    feedback_data['feedback'] = feedback_data['feedback'].map({1: 'Thumbs Up', 0: 'Thumbs Down'})

    fig_feedback = px.pie(
        feedback_data, 
        names='feedback', 
        values='count', 
        title='Feedback Sentiments Distribution'
    )
    
    return fig_peak, fig_faqs, fig_trends, fig_feedback

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
