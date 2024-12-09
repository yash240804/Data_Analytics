import sqlite3
import pandas as pd
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import pytz

# Set your local time zone
local_tz = pytz.timezone("Asia/Kolkata")  # Replace with your local timezone if different

# Connect to SQLite database
db_path = "rag_app.db"  # Replace with your actual path
conn = sqlite3.connect(db_path)

# Load data from application_logs table
query = "SELECT * FROM application_logs"
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

# Create Dash app with Bootstrap styles
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define a list of known locations (cities with polytechnic colleges)
known_locations = ["Jaipur", "Ajmer", "Jodhpur", "Udaipur", "Kota", "Bikaner"]

# Extract location-based FAQs from user queries
def extract_location_faqs_from_queries(df, locations):
    if 'user_query' in df.columns:
        location_faqs = []
        for location in locations:
            # Find queries mentioning the location
            queries = df[df['user_query'].str.contains(location, case=False, na=False)]['user_query'].unique()
            if len(queries) > 0:
                location_faqs.append({'college_location': location, 'user_query': list(queries)})
        return pd.DataFrame(location_faqs)
    else:
        return pd.DataFrame(columns=['college_location', 'user_query'])

# Extract location-based FAQs
location_faqs_df = extract_location_faqs_from_queries(df, known_locations)

# Create dropdown options
location_options = [{'label': loc, 'value': loc} for loc in location_faqs_df['college_location'].unique()]

# Callback for location-based FAQs
@app.callback(
    Output("location-faqs", "children"),
    [Input("location-dropdown", "value")]
)
def update_faqs(location):
    if location:
        faqs = location_faqs_df[location_faqs_df['college_location'] == location]['user_query'].values
        if faqs.size > 0:  # Check if FAQs exist
            return html.Ul([html.Li(faq) for faq in faqs[0]])  # Display FAQs as a list
        else:
            return "No FAQs available for this location."
    return "Select a location to view FAQs."

# Layout for the dashboard
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("AI Chatbot Insights Dashboard", className="text-center text-primary, mb-4"), width=12)
    ]),
    dbc.Tabs([
        # Tab 1: Data Insights
        dbc.Tab(label="Insights", children=[
            dbc.Row([
                dbc.Col(dcc.Graph(id='peak-times', style={'height': '400px'}), width=6),
                dbc.Col(dcc.Graph(id='faqs-trends', style={'height': '400px'}), width=6),
            ]),
            dbc.Row([
                dbc.Col(dcc.Graph(id='query-trends', style={'height': '400px'}), width=6),
                dbc.Col(dcc.Graph(id='feedback-sentiments', style={'height': '400px'}), width=6),
            ])
        ]),

        # Tab 2: Location-based FAQs
        dbc.Tab(label="Location-based FAQs", children=[
            dbc.Row([
                dbc.Col([
                    html.Label("Select a Location:", className="font-weight-bold"),
                    dcc.Dropdown(
                        id="location-dropdown",
                        options=location_options,
                        placeholder="Choose a location",
                        style={"margin-bottom": "20px"}
                    ),
                    html.Div(id="location-faqs", className="text-secondary")
                ])
            ])
        ])
    ])
], fluid=True)

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
    category_counts = {cat: sum(df['user_query'].str.lower().str.contains('|'.join(words))) for cat, words in categories.items()}
    category_data = pd.DataFrame(category_counts.items(), columns=['Category', 'Count'])

    fig_trends = px.pie(
        category_data, 
        names='Category', 
        values='Count',
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

def update_faqs(location):
    if location:
        faqs = location_faqs_df[location_faqs_df['college_location'] == location]['user_query'].values[0]
        return html.Ul([html.Li(faq) for faq in faqs])
    return "Select a location to view FAQs."

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
