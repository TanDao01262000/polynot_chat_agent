# PolyNot Language Learning API

## Prerequisites

- Python 3.10+
- pip (Python package manager)
- virtualenv (recommended)

## Environment Setup

1. Create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file in the root directory:

```bash
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# LangSmith Configuration
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=polynot


## Running the Server

1. Start the FastAPI server:

```bash
# Development mode
uvicorn src.main:app --reload

# Production mode
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

2. Access the API documentation:
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

### User Management
- `POST /users/` - Create a new user
- `GET /users/{user_name}` - Get user information
- `PATCH /users/{user_name}` - Update user's language level

### Chat
- `POST /chat` - Start or continue a conversation
- `POST /feedback` - Get feedback on a conversation
- `POST /evaluate` - Evaluate user's language level

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_main.py

# Run with coverage
pytest --cov=src tests/
```

### API Testing

1. Using Swagger UI:
   - Open http://localhost:8000/docs
   - Authenticate using your API key
   - Test endpoints directly from the interface

2. Using curl:

```bash
# Create a new user
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{"user_name": "test_user", "user_level": "A2", "target_language": "English"}'

# Start a chat
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"user_name": "test_user", "thread_id": "123", "user_input": "Hello!", "scenario_id": "coffee_shop"}'
```

### Available Scenarios

The API includes the following premade scenarios:

1. `coffee_shop` (A2) - Ordering at a coffee shop
2. `job_interview` (B2) - Job interview for marketing position
3. `first_date` (B1) - First date at a restaurant
4. `travel_planning` (B1) - Planning a vacation
5. `doctor_visit` (B2) - Visit to the doctor's office
6. `shopping` (A2) - Shopping for clothes

### Sample Scenario Test

Here's a complete example using the coffee shop scenario:

```bash
# 1. Create a user
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{
       "user_name": "coffee_lover",
       "user_level": "A2",
       "target_language": "English"
     }'

# 2. Start coffee shop conversation
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "user_name": "coffee_lover",
       "thread_id": "coffee_conv_1",
       "user_input": "Hello, I would like to order a coffee",
       "scenario_id": "coffee_shop"
     }'

# 3. Get feedback
curl -X POST "http://localhost:8000/feedback" \
     -H "Content-Type: application/json" \
     -d '{
       "user_name": "coffee_lover",
       "thread_id": "coffee_conv_1"
     }'
```

To test in Swagger UI:
1. Go to http://localhost:8000/docs
2. Find the `/chat` endpoint
3. Click "Try it out"
4. Use this sample request body:
```json
{
  "user_name": "coffee_lover",
  "thread_id": "coffee_conv_1",
  "user_input": "Hello, I would like to order a coffee",
  "scenario_id": "coffee_shop"
}
```
