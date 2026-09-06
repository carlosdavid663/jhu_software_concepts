from flask import Flask
from pages import pages

# Create the Flask application.
app = Flask(__name__)

# Add the three pages from pages.py to the application.
app.register_blueprint(pages)

# Start the website
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
