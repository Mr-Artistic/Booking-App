# About the App

This is a web app that lets users to book the company's facilities such as conference rooms and equipment/software (resource).

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
