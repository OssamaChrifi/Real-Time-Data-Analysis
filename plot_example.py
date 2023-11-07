# app.py
from flask import Flask, jsonify, render_template
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

app = Flask(__name)

# Set up a SQLAlchemy database connection
db_uri = "mysql://username:password@localhost:3306/mydatabase"
engine = create_engine(db_uri)
Session = sessionmaker(bind=engine)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def get_data():
    # Query the database to retrieve data for the pie chart
    session = Session()
    data = session.execute("SELECT category, COUNT(*) AS count FROM my_table GROUP BY category")
    session.close()
    
    # Convert the data to a format suitable for Chart.js
    chart_data = [{"label": row.category, "data": row.count} for row in data]
    
    return jsonify(chart_data)

if __name__ == "__main__":
    app.run(debug=True)
