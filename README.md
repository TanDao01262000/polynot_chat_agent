# PolyNot Language Learning API

A comprehensive language learning platform with AI-powered chat, social features, and intelligent learning analytics.

## 🚀 Features

### Core Learning
- **AI Chat Agent**: Intelligent conversation practice with LangChain/LangGraph
- **Level Evaluation**: Automatic assessment of user language levels
- **Feedback System**: Real-time learning feedback and suggestions

### Social Learning
- **Social Posts**: Share learning experiences and achievements
- **Smart Feed**: Personalized content based on user level and preferences
- **Leaderboards**: Global and level-based rankings
- **Points System**: Gamified learning with points and achievements
- **Study Analytics**: Global word usage analytics and insights

### Integration Ready
- **AI Vocab Integration**: Connect with AI vocabulary generation systems
- **Flashcard Integration**: Connect with spaced repetition systems
- **Points API**: Award points for external learning activities

## 📁 Project Structure

```
polynot_chat_agent/
├── src/                          # Main application code
│   ├── main.py                  # FastAPI application
│   ├── chat_agent.py            # AI chat agent
│   ├── social_service.py        # Social features service
│   ├── smart_feed_service.py    # Intelligent feed service
│   ├── study_analytics_service.py # Study analytics service
│   ├── social_integration.py    # Auto-posting integration
│   ├── social_models.py         # Data models
│   └── models.py                # Core models
├── docs/                        # Documentation
│   ├── integration/             # Integration guides
│   └── social/                  # Social features docs
├── docs_and_tests/             # API documentation
├── social_migration.sql         # Database schema
└── requirements.txt            # Dependencies
```

## 🛠️ Quick Start

### Prerequisites
- Python 3.11+
- Supabase account
- Virtual environment

### Installation

1. **Clone and setup**:
```bash
git clone <repository>
cd polynot_chat_agent
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Setup database**:
```bash
# Run the migration script in your Supabase SQL editor
cat social_migration.sql
```

4. **Configure environment**:
```bash
# Set your Supabase credentials
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"
```

5. **Start the server**:
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Documentation

### API Documentation
- **Complete Guide**: `docs_and_tests/COMPLETE_GUIDE.md`
- **API Reference**: `docs_and_tests/API_REFERENCE.md`
- **Technical Docs**: `docs_and_tests/TECHNICAL_DOCUMENTATION.md`

### Integration Guides
- **Server Integration**: `docs/integration/SERVER_INTEGRATION_DOCS.md`
- **Quick Setup**: `docs/integration/QUICK_SETUP_GUIDE.md`
- **AI System Integration**: `docs/integration/AI_SYSTEM_INTEGRATION_GUIDE.md`

### Social Features
- **Social Overview**: `docs/social/README.md`
- **Points Integration**: `docs/integration/points_integration_example.py`

## 🔗 API Endpoints

### Core Learning
- `POST /chat` - AI conversation practice
- `GET /users/{user_name}` - Get user profile
- `POST /users/` - Create user account

### Social Features
- `POST /social/posts` - Create social post
- `GET /social/feed` - Get personalized feed
- `GET /social/leaderboard` - Get global leaderboard
- `GET /social/users/{user_name}/points` - Get user points

### Study Analytics
- `POST /study/record-word` - Record word study
- `GET /study/analytics` - Get study analytics
- `GET /study/trending-words` - Get trending words

## 🔧 Integration

### For AI Vocab Servers
```python
from docs.integration.points_integration_example import AIVocabPoints

vocab_points = AIVocabPoints()
result = vocab_points.award_vocab_generation_points(
    user_name="user123",
    words_generated=20,
    level="A2"
)
```

### For Flashcard Servers
```python
from docs.integration.points_integration_example import FlashcardPoints

flashcard_points = FlashcardPoints()
result = flashcard_points.award_flashcard_review_points(
    user_name="user123",
    cards_reviewed=20,
    difficulty="medium"
)
```

## 🎯 Key Features

### Social Learning Platform
- **Multi-user support** with different language levels (A1-C1)
- **Real-time leaderboards** with points and achievements
- **Smart feed** with level-based content filtering
- **Study analytics** with global word usage insights
- **Privacy controls** for user data protection

### Points System
- **Automatic point awarding** for learning activities
- **Level-based point scaling** (A1: 15-25 points, C1: 40-80 points)
- **Achievement system** with badges and milestones
- **Social competition** with global rankings

### AI Integration
- **LangChain/LangGraph** for intelligent conversations
- **Level evaluation** with automatic assessment
- **Feedback system** with personalized suggestions
- **Social integration** with auto-posting capabilities

## 🚀 Deployment

### Docker
```bash
# Development
docker-compose up

# Production
docker-compose -f docker-compose.prod.yml up
```

### Manual Deployment
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
# (Execute social_migration.sql in Supabase)

# Start server
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## 🧪 Testing

The API includes comprehensive testing capabilities:

```bash
# Test social features
curl -X GET "http://localhost:8000/health"

# Test user creation
curl -X POST "http://localhost:8000/users/" \
  -H "Content-Type: application/json" \
  -d '{"user_name": "testuser", "user_level": "A2", "target_language": "English", "email": "test@example.com", "password": "password123"}'

# Test social features
curl -X GET "http://localhost:8000/social/leaderboard"
```

## 📊 Database Schema

The system uses Supabase with the following key tables:
- `profiles` - User profiles and settings
- `social_posts` - Social posts and content
- `user_points` - Points and achievements
- `word_study_records` - Study analytics
- `global_word_analytics` - Global word usage

## 🔒 Security

- **Row Level Security (RLS)** enabled on all tables
- **JWT authentication** for user sessions
- **Input validation** with Pydantic models
- **SQL injection protection** with parameterized queries

## 📈 Performance

- **Async/await** for non-blocking operations
- **Database indexing** for fast queries
- **Connection pooling** with Supabase
- **Caching** for frequently accessed data

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues or questions:
1. Check the documentation in `docs/`
2. Review the API reference
3. Test with the provided examples
4. Check the logs for error details

---

**Built with ❤️ for language learners worldwide** 🌍