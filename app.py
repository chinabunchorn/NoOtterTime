import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# Initialize Flask app.
# By default, Flask serves files from the 'static' folder at the '/static' route.
app = Flask(__name__, static_folder='static')

# Enable CORS, ensuring cookies/sessions/credentials are supported
CORS(app, supports_credentials=True)

# 1. Serve the frontend HTML files
@app.route('/')
def serve_index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:filename>')
def serve_frontend(filename):
    # Serve the requested HTML file (e.g. login.html) from the 'frontend' folder
    return send_from_directory('frontend', filename)

# 2. Add your API routes below
@app.route('/api/courses', methods=['GET'])
def get_courses():
    # Example stub
    return jsonify({"data": []}), 200

# ... Put the rest of your API routes here ...

if __name__ == '__main__':
    # Dynamic port binding for Render.com
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)