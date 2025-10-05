# Service Booking Agent

AI-powered service booking agent built with LangGraph.

## Features

- Natural language booking processing
- LangGraph workflow orchestration
- Smart provider selection with distance, schedule, and budget weighting
- Real-time pricing, availability, email, and push notifications


## Setup

1. **Clone and setup environment:**
   ```bash
   cd booking-agent
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   npm install --prefix frontend
   npm run build --prefix frontend
   npm start
   python app.py
  ```

2. **Environment variables:**
   ```bash
   cp .env
   # Edit .env with your actual values
   ```

3. **Firebase setup:**
   - Create Firebase project
   - Enable Firestore Database
   - Download service account JSON
   - Update FIREBASE_SERVICE_ACCOUNT path in .env


## API Endpoints

### POST /book
Book a service using natural language.

### GET /bookings?uid=user123
Get user's booking history.

## Data Model

### Firestore Collections

- `users/{uid}` - User profiles
- `services/{serviceId}` - Available services
- `providers/{providerId}` - Service providers
- `schedules/{providerId}/slots/{slotId}` - Available time slots
- `bookings/{bookingId}` - Confirmed bookings


## Contributing


Appreciate if you are willing to add more features. Some of my recommendations are complete user profile page, add more locations and real services.

HOW CAN YOU CONTRIBUTE?  

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Submit a pull request

## License
MIT License