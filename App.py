from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
import pandas as pd
import joblib
import os
import logging
import firebase_admin
from firebase_admin import credentials, auth, firestore
import time

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

# Redirect the root route to the login page
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

# Route for the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Firebase user login (not checking password here for simplicity)
        try:
            user = auth.get_user_by_email(email)
            session['user'] = user.email
            logging.debug(f"User logged in: {user.email}")
            return redirect(url_for('home'))
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
        username = request.form['username']  # New username field

        # Firebase user sign-up
        try:
            user = auth.create_user(email=email, password=password)
            logging.debug(f"User signed up: {user.email}")

            # Store user info in Firestore
            db.collection('users').document(user.uid).set({
                'email': user.email,
                'username': username,  # Store the username provided during signup
                'createdAt': firestore.SERVER_TIMESTAMP
            })
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

# Route for the homepage/dashboard
@app.route('/home')
def home():
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))

    logging.debug("User in session, rendering index.html")
    return render_template('index.html', location=None, temperature=None, humidity=None, rainfall=None)

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

# Route for the account page where users can edit their account details
@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user' not in session:
        logging.debug("User not in session, redirecting to login")
        return redirect(url_for('login'))

    user_email = session['user']
    try:
        user = auth.get_user_by_email(user_email)  # Correct method to fetch by email
        user_doc_ref = db.collection('users').document(user.uid).get()
        username = user_doc_ref.to_dict().get('username', '') if user_doc_ref.exists else ''
    except Exception as e:
        logging.error(f"Error fetching user account: {e}")
        return render_template('account.html', error="Could not fetch user details.")

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']  # Username field

        try:
            # Update user email and password in Firebase
            auth.update_user(user.uid, email=email, password=password)
            session['user'] = email  # Update the session with the new email

            # Update Firestore with the new username
            user_doc_ref.set({
                'username': username
            }, merge=True)

            logging.debug(f"User account updated: {email}")
            return redirect(url_for('home'))

        except Exception as e:
            logging.error(f"Account update failed for {email}: {e}")
            return render_template('account.html', error="Account update failed. Please try again.", email=email, username=username)

    return render_template('account.html', email=user_email, username=username)

# Flask app entry point
if __name__ == '__main__':
    app.run(debug=True)
