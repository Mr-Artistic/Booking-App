# About the App

This is a web app that lets users to book the company's facilities such as conference rooms and equipment/software (resources). The app is written in Python and uses the Streamlit framework.

## App Features:

    - View all current bookings in a timeline chart (Date vs Time).
    - See detailed information on all existing bookings in a table format.
    - Check pricing for a resource.
    - Submit a new booking request for a resource or conference room.
    - Receive an automated confirmation email after the booking.
    - The system prevents overlapping bookings for the same resource/room.
    - The booking data is stored to your database.

## Prerequisites (private/ not in this source code)

    - Database, email, resources and payment link configured through secrets.toml file.
    - User Auth configured via yaml file (requires streamlit-authenticator).

## Deployment

    - Deploy with render or your vm.
    - Route through your domain via cloudflare or Nginx reverse-proxy.

## App Demo (Screenshot)

    - See demo.png

## Project-folder Hierarchy

    Booking_App
    |-- .streamlit
    |   | # -- hidden files
    |-- assets
    |   |-- conference_lottie.json
    |   |-- logo.ico
    |   |-- logo.png
    |   `-- resource_lottie.json
    |-- conference_app
    |   |-- __init__.py
    |   |-- app.py
    |   |-- config.py
    |   `-- functions.py
    |-- resource_app
    |   |-- __init__.py
    |   |-- app.py
    |   |-- config.py
    |   `-- functions.py
    |-- CHANGELOG.md
    |-- README.md
    |-- demo.png
    |-- home.py
    `-- requirements.txt
