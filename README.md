# AgriTrade

AgriTrade is a web application designed to help users manage their agricultural trade activities. This project includes features such as inventory management, crop management, user authentication, and report generation.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Node.js and npm installed on your machine.
- Python 3.x installed on your machine.
- Firebase account and project set up.

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/agritrade.git
    cd agritrade
    ```

2. Install Python dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Set up Firebase:

    - Go to the Firebase console and create a new project.
    - Add a web app to your Firebase project.
    - Copy the Firebase configuration and replace the existing configuration in `static/firebase.js` and other relevant files.

## Running the Application

1. Start the development server:
   Python app.py 
2. Open your browser and navigate to http://127.0.0.1:5000.

## Project Structure

- `static/`: Contains all the CSS and JavaScript files.
- `templates/`: Contains all the HTML templates.
- `modeltraining.ipynb`: Jupyter notebook for model training.
- `requirements.txt`: Python dependencies.

## Firebase Configuration

Ensure you have the correct Firebase configuration in the following files:

- `static/firebase.js`
- `templates/account.html`
- `templates/dashboard.html`
- `templates/inventory.html`
- `templates/managecrops.html`
- `templates/signup.html`
