# PolyNot Language Learning API

A revolutionary language learning platform that provides authentic conversational experiences through AI-powered partners with distinct personalities, backgrounds, and expertise.

## Prerequisites

- Python 3.11+
- pip (Python package manager)
- virtualenv (recommended)

## Environment Setup

1. Create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate
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

# LangSmith Configuration (optional)
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=polynot

# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
```

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
- `POST /users/` - Create a new user (requires email)
- `GET /users/{user_name}` - Get user information
- `DELETE /users/{user_name}` - Delete user account
- `PATCH /users/{user_name}` - Update user's language level

### User Profile Management
- `GET /users/{user_name}/profile` - Get complete user profile with statistics
- `PATCH /users/{user_name}/profile` - Update user profile information
- `PATCH /users/{user_name}/level` - Update user's language level
- `GET /users/{user_name}/statistics` - Get user learning statistics
- `POST /users/{user_name}/login` - Record user login and update streak
- `GET /users/{user_name}/profile/completion` - Get profile completion percentage
- `GET /users/{user_name}/profile/achievements` - Get user achievements
- `POST /migrate/user-profiles` - Migrate existing users to new profile system

### Partner Management
- `POST /partners/` - Create a new custom partner
- `GET /partners/` - Get all partners (with optional filters)
- `GET /partners/{user_name}` - Get user's custom partners

### Chat & Conversation
- `POST /chat` - Start or continue a conversation
- `GET /threads/{thread_id}/messages` - Get conversation history

### Analysis & Feedback
- `POST /feedback` - Get detailed feedback on a conversation
- `POST /evaluate` - Evaluate user's language level

### Health & Status
- `GET /` - Basic health check
- `GET /health` - Detailed health check
- `GET /test/all-endpoints` - Comprehensive system test

## User Creation & Login

### User Creation Requirements

**Required Fields:**
- `user_name`: 3-30 characters, no spaces, alphanumeric + underscore/hyphen only
- `user_level`: One of A1, A2, B1, B2, C1, C2
- `target_language`: Language to learn (e.g., "English", "Spanish")
- `email`: Real email address (Gmail, Yahoo, Outlook, etc.)

**Username Rules:**
- ✅ Valid: `john_doe`, `john-doe`, `johndoe`, `user123`
- ❌ Invalid: `john doe` (spaces), `123user` (starts with number), `admin` (reserved)

**Example:**
```bash
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{
       "user_name": "john_doe",
       "user_level": "A2",
       "target_language": "English",
       "email": "john.doe@gmail.com"
     }'
```

### Login

**Login only requires username:**
```bash
curl -X POST "http://localhost:8000/users/john_doe/login"
```

**Response:**
```json
{
  "message": "Login recorded successfully",
  "streak_days": 1,
  "last_login": "2025-08-22T20:55:26.569"
}
```

## Testing

### Quick API Test

```bash
# Health check
curl http://localhost:8000/health

# Test all endpoints
curl http://localhost:8000/test/all-endpoints

# Create a test user
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{"user_name": "test_user", "user_level": "A2", "target_language": "English"}'
```

### Comprehensive Test Suite

```bash
# Run the full test suite
python docs_and_tests/test_enhanced_partner_system.py
```

### API Testing

1. Using Swagger UI:
   - Open http://localhost:8000/docs
   - Test endpoints directly from the interface

2. Using curl:

```bash
# Create a new user
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{"user_name": "test_user", "user_level": "A2", "target_language": "English"}'

# Create a custom partner
curl -X POST "http://localhost:8000/partners/?user_name=test_user" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Tour Guide",
       "ai_role": "friendly tour guide",
       "scenario": "Exploring a new city with local insights",
       "target_language": "English",
       "user_level": "B1",
       "personality": "Enthusiastic and knowledgeable about local culture",
       "background": "Has been a tour guide for 5 years in this city",
       "communication_style": "Friendly and informative, speaks clearly",
       "expertise": "Local history, culture, and hidden gems",
       "interests": "Local cuisine, photography, meeting people from different cultures"
     }'

# Start a chat with a partner
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "user_name": "test_user",
       "thread_id": "123",
       "user_input": "Hello!",
       "partner_id": "partner_uuid"
     }'

# Test User Profile Feature
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{"user_name": "profile_user", "user_level": "B1", "target_language": "English"}'

# Update user profile
curl -X PATCH "http://localhost:8000/users/profile_user/profile" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "profile_user@example.com",
       "first_name": "John",
       "last_name": "Doe",
       "bio": "Passionate language learner",
       "native_language": "Spanish",
       "learning_goals": "Become fluent in English for work",
       "preferred_topics": "Business, travel, technology"
     }'

# Get complete user profile
curl -X GET "http://localhost:8000/users/profile_user/profile"

# Get user statistics
curl -X GET "http://localhost:8000/users/profile_user/statistics"

# Record user login
curl -X POST "http://localhost:8000/users/profile_user/login"

# Update user level
curl -X PATCH "http://localhost:8000/users/profile_user/level" \
     -H "Content-Type: application/json" \
     -d '{"user_level": "B2"}'
```

### Available Premade Partners

The API includes the following premade partners with detailed character profiles:

1. **Emily Carter** (A2) - Coffee Shop Barista
   - Warm, enthusiastic barista who loves coffee and helping customers
2. **Michael Lee** (B2) - Hiring Manager
   - Professional hiring manager conducting job interviews
3. **Sophie Martin** (B1) - Date Partner
   - Friendly person on a first date at a casual restaurant
4. **Carlos Rivera** (B1) - Travel Agent
   - Enthusiastic travel agent helping plan vacations
5. **Dr. Olivia Smith** (B2) - Doctor
   - Caring doctor in a medical consultation
6. **Anna Kim** (A2) - Shop Assistant
   - Friendly shop assistant helping with clothing purchases

### Sample Partner Test

Here's a complete example using a custom partner:

```bash
# 1. Create a user
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{
       "user_name": "alex",
       "user_level": "B1",
       "target_language": "English"
     }'

# 2. Create a custom partner
curl -X POST "http://localhost:8000/partners/?user_name=alex" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "City Tour Guide",
       "ai_role": "friendly tour guide",
       "scenario": "Exploring a new city with local insights",
       "target_language": "English",
       "user_level": "B1",
       "personality": "Enthusiastic and knowledgeable about local culture",
       "background": "Has been a tour guide for 5 years in this city",
       "communication_style": "Friendly and informative, speaks clearly",
       "expertise": "Local history, culture, and hidden gems",
       "interests": "Local cuisine, photography, meeting people from different cultures"
     }'

# 3. Start conversation with the partner
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "user_name": "alex",
       "thread_id": "tour_conversation_1",
       "user_input": "Hi! I just arrived in the city and would love to explore some local places.",
       "partner_id": "partner_uuid_from_step_2"
     }'

# 4. Get feedback
curl -X POST "http://localhost:8000/feedback?user_name=alex&thread_id=tour_conversation_1"
```

To test in Swagger UI:
1. Go to http://localhost:8000/docs
2. Find the `/chat` endpoint
3. Click "Try it out"
4. Use this sample request body:
```json
{
  "user_name": "alex",
  "thread_id": "tour_conversation_1",
  "user_input": "Hi! I just arrived in the city.",
  "partner_id": "your_partner_id"
}
```

## Database Schema

The API uses Supabase with the following main tables:

- `users` - User information and language levels
- `partners` - Conversation partners (both premade and custom) with enhanced character profiles
- `conversation_history` - Chat messages and conversation threads

## Features

- **Authentic AI Partners**: Realistic characters with detailed personalities, backgrounds, and expertise
- **Natural Conversations**: Partners respond as real people, not language tutors
- **Progress Tracking**: Automated level evaluation and detailed feedback
- **Customizable Partners**: Create your own conversation partners with full character profiles
- **Language Learning**: AI partners adapt to user's language level
- **Conversation History**: Track and retrieve chat conversations
- **Feedback System**: Get detailed feedback on conversations
- **Level Evaluation**: Assess user's language progress

## Documentation

For comprehensive documentation, visit the [`docs_and_tests/`](docs_and_tests/) folder:

- **[📖 Main Documentation](docs_and_tests/README.md)** - Complete project overview and quick start
- **[🔧 Technical Documentation](docs_and_tests/TECHNICAL_DOCUMENTATION.md)** - Architecture, deployment, and development guide
- **[📡 API Reference](docs_and_tests/API_REFERENCE.md)** - Complete API endpoints and examples
