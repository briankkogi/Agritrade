from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
import pandas as pd
import joblib
import os
import logging
import firebase_admin
from firebase_admin import credentials, auth, firestore
import time
import json

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # Use a default for development

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load the trained model and other necessary components
model = joblib.load('stacking_model.pkl')
scaler = joblib.load('scaler.pkl')
label_encoder = joblib.load('label_encoder.pkl')

# OpenWeather API key
API_KEY = '6ccecd2ea82b83adf48ae94faca5a556'

# Initialize Firebase Admin SDK
cred = credentials.Certificate('credentials/agritrade-3fe65-firebase-adminsdk-zfqtb-8e8abb15f4.json')
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()

# Redirect the root route to the welcome page or dashboard if logged in
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))  # Redirect to the dashboard if logged in
    return redirect(url_for('welcome'))  # Redirect to welcome page if unauthenticated

@app.route('/welcome')
def welcome():
    if 'user' in session:
        return redirect(url_for('dashboard'))  # Redirect to dashboard if already logged in
    return render_template('welcome.html')  # Render the welcome page

# Route for the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Firebase user login
            user = auth.get_user_by_email(email)
            
            # Assuming password verification is done elsewhere, or add Firebase authentication check
            session['user'] = user.email  # Store email in session
            logging.debug(f"User logged in: {user.email}")

            # Redirect to dashboard after login
            return redirect(url_for('dashboard'))
        except Exception as e:
            logging.error(f"Login failed for {email}: {e}")
            return render_template('login.html', error="Login failed. Please check your credentials.")

    return render_template('login.html')

# Route for the signup page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        fullName = request.form['fullName']
        phoneNumber = request.form['phoneNumber']

        # Firebase user sign-up
        try:
            user = auth.create_user(email=email, password=password)
            logging.debug(f"User signed up: {user.email}, UID: {user.uid}")

            # Store user info in Firestore
            db.collection('users').document(user.uid).set({
                'email': user.email,
                'fullName': fullName,  # Store the username provided during signup
                'phoneNumber': phoneNumber,  # Store the username provided during signup
                'createdAt': firestore.SERVER_TIMESTAMP
            })
            logging.debug(f"User data saved to Firestore for UID: {user.uid}")

            return redirect(url_for('login'))
        except Exception as e:
            logging.error(f"Signup failed for {email}: {e}")
            return render_template('signup.html', error="Signup failed. Please try again.")

    return render_template('signup.html')

# Verify the JWT token received from the Firebase client
@app.route('/verify_token', methods=['POST'])
def verify_token():
    try:
        token = request.json['token']
        decoded_token = auth.verify_id_token(token)
        session['user'] = decoded_token['email']  # Store user email in session
        logging.debug(f"User verified and logged in: {session['user']}")
        return jsonify(success=True), 200
    except Exception as e:
        logging.error(f"Token verification failed: {e}")
        return jsonify(success=False), 401  # Unauthorized

# Route for the dashboard page
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))

    logging.debug("User in session, rendering dashboard.html")
    return render_template('dashboard.html')

@app.route('/crops')
def crops():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('crops.html')

@app.route('/selling')
def selling():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    item_id = request.args.get('itemId')  # Retrieve the itemId from the query string
    if item_id:
        return render_template('selling.html', item_id=item_id)
    else:
        return "Item ID is missing!", 400
    
@app.route('/manage_crops')
def manage_crops():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('managecrops.html')

@app.route('/account')
def account():
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))

    logging.debug("User in session, rendering dashboard.html")
    return render_template('account.html')

# Route for the inventory page
@app.route('/inventory')
def inventory():
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))

    logging.debug("User accessed inventory page")
    return render_template('inventory.html')


@app.route('/add_inventory')
def add_inventory():
    if request.method == 'POST':
        # Logic to handle the form submission and add inventory
        inventory_item = request.form['item_name']
        quantity = request.form['quantity']
        price = request.form['price']
        
        # Here you would process the data, e.g., save it to a database
        return f'Inventory for {inventory_item} added successfully!'
    
    return render_template('add_inventory.html')  # Render the form template

# Route for the home page
@app.route('/home')
def home():
    # Check if the user is logged in
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))

    logging.debug("User accessed home page")
    return render_template('index.html')  

# Route to log out the user
@app.route('/logout')
def logout():
    session.pop('user', None)
    logging.debug("User logged out")
    return redirect(url_for('login'))

# Route to fetch weather data from OpenWeather API
@app.route('/get_weather', methods=['POST'])
def get_weather():
    try:
        lat = request.json['latitude']
        lon = request.json['longitude']

        weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"

        start_time = time.time()
        weather_response = requests.get(weather_url, timeout=5)
        response_time = time.time() - start_time
        logging.debug(f"OpenWeather API response time: {response_time:.2f} seconds")

        if weather_response.status_code != 200:
            logging.error(f"API Error {weather_response.status_code}: {weather_response.text}")
            return jsonify({'error': 'Failed to fetch weather data'}), 500

        weather_data = weather_response.json()
        temperature = weather_data['main']['temp']
        humidity = weather_data['main']['humidity']
        rainfall = weather_data.get('rain', {}).get('1h', 0.0)
        location = weather_data['name']

        return jsonify({
            'location': location,
            'temperature': temperature,
            'humidity': humidity,
            'rainfall': rainfall
        })

    except Exception as e:
        logging.error(f"Error fetching weather data: {e}")
        return jsonify({'error': str(e)})

# Route to fetch 5-day weather forecast from OpenWeather API
@app.route('/get_forecast', methods=['POST'])
def get_forecast():
    try:
        lat = request.json['latitude']
        lon = request.json['longitude']

        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"

        forecast_response = requests.get(forecast_url, timeout=5)

        if forecast_response.status_code != 200:
            logging.error(f"API Error {forecast_response.status_code}: {forecast_response.text}")
            return jsonify({'error': 'Failed to fetch forecast data'}), 500

        forecast_data = forecast_response.json()

        forecast_list = []
        added_dates = set()
        for entry in forecast_data['list']:
            date_time = entry['dt_txt']
            date = date_time.split(' ')[0]
            time_of_day = date_time.split(' ')[1]

            if time_of_day == '12:00:00' and date not in added_dates:
                forecast_list.append({
                    'date': date,
                    'temperature': entry['main']['temp'],
                    'humidity': entry['main']['humidity'],
                    'rainfall': entry.get('rain', {}).get('3h', 0.0)
                })
                added_dates.add(date)

            if len(forecast_list) == 5:
                break

        return jsonify({
            'forecast': forecast_list
        })

    except Exception as e:
        logging.error(f"Error fetching forecast data: {e}")
        return jsonify({'error': str(e)})

# Route for crop prediction based on weather data
@app.route('/predict', methods=['POST'])
def predict():
    try:
        temperature = request.form.get('user-temperature') or request.form['temperature']
        humidity = request.form.get('user-humidity') or request.form['humidity']
        rainfall = request.form.get('user-rainfall') or request.form['rainfall']

        data = pd.DataFrame({
            'temperature': [float(temperature)],
            'humidity': [float(humidity)],
            'rainfall': [float(rainfall)]
        })

        data_scaled = scaler.transform(data)

        start_time = time.time()
        probabilities = model.predict_proba(data_scaled)[0]
        prediction_time = time.time() - start_time
        logging.debug(f"Prediction time: {prediction_time:.2f} seconds")

        crops = label_encoder.inverse_transform(range(len(probabilities)))
        crop_probabilities = {crop: round(prob, 2) for crop, prob in zip(crops, probabilities)}
        sorted_crop_probabilities = dict(sorted(crop_probabilities.items(), key=lambda item: item[1], reverse=True))

        return render_template('result.html', crop_probabilities=sorted_crop_probabilities)

    except Exception as e:
        logging.error(f"Error in prediction: {e}")
        return str(e)

# Load crop optimal conditions
with open('crop_optimal_conditions.json', 'r') as f:
    crop_optimal_conditions = json.load(f)

@app.route('/crop-details/<crop_name>')
def crop_details(crop_name):
    if 'user' not in session:
        return redirect(url_for('login'))

    if crop_name in crop_optimal_conditions:
        conditions = crop_optimal_conditions[crop_name]
        crop_info = {
            'crop_name': crop_name,
            'recommendation_reason': f"Based on the weather conditions, {crop_name} is well-suited for cultivation in your area.",
            'optimal_temperature': f"{conditions['temperature']['min']}°C - {conditions['temperature']['max']}°C",
            'optimal_humidity': f"{conditions['humidity']['min']}% - {conditions['humidity']['max']}%",
            'optimal_rainfall': f"{conditions['rainfall']['min']}mm - {conditions['rainfall']['max']}mm annually",
            'optimal_ph': f"{conditions['ph']['min']} - {conditions['ph']['max']}",
            'optimal_N': f"{conditions['N']['min']} - {conditions['N']['max']} kg/ha",
            'optimal_P': f"{conditions['P']['min']} - {conditions['P']['max']} kg/ha",
            'optimal_K': f"{conditions['K']['min']} - {conditions['K']['max']} kg/ha",
            'growing_tips': [
                f"Maintain temperature between {conditions['temperature']['min']}°C and {conditions['temperature']['max']}°C for optimal growth.",
                f"Keep humidity levels between {conditions['humidity']['min']}% and {conditions['humidity']['max']}%.",
                f"Ensure annual rainfall or irrigation between {conditions['rainfall']['min']}mm and {conditions['rainfall']['max']}mm.",
                f"Maintain soil pH between {conditions['ph']['min']} and {conditions['ph']['max']}.",
                f"Apply Nitrogen fertilizer at {conditions['N']['min']} - {conditions['N']['max']} kg/ha.",
                f"Apply Phosphorus fertilizer at {conditions['P']['min']} - {conditions['P']['max']} kg/ha.",
                f"Apply Potassium fertilizer at {conditions['K']['min']} - {conditions['K']['max']} kg/ha.",
                "Monitor soil moisture regularly and adjust watering accordingly.",
                "Implement proper pest management techniques specific to this crop.",
                "Conduct regular soil tests to ensure optimal nutrient levels."
            ]
        }
    else:
        crop_info = {
            'crop_name': crop_name,
            'recommendation_reason': "We don't have specific data for this crop. Please consult local agricultural experts for more information.",
            'optimal_temperature': "Not available",
            'optimal_humidity': "Not available",
            'optimal_rainfall': "Not available",
            'optimal_ph': "Not available",
            'optimal_N': "Not available",
            'optimal_P': "Not available",
            'optimal_K': "Not available",
            'growing_tips': [
                "Consult local agricultural experts for specific growing conditions and tips.",
                "Research best practices for this crop in your region.",
                "Monitor plant health regularly and adjust care as needed."
            ]
        }

    return render_template('cropdetails.html', **crop_info)

# Flask app entry point
if __name__ == '__main__':
    app.run(debug=True)
