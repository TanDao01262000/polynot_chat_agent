# 🚀 Quick Setup Guide
## Points System Integration for Your Servers

This guide shows you exactly how to integrate your AI vocab and flashcard servers with the social points system.

## 📋 Prerequisites

1. **Social API Server** must be running on `http://localhost:8000`
2. **Python requests library** installed: `pip install requests`
3. **User accounts** exist in the social system

## 🔧 Step 1: Copy the Integration Code

Copy the `points_integration_example.py` file to your server projects.

## 🔧 Step 2: Install Dependencies

```bash
pip install requests
```

## 🔧 Step 3: Import and Use

### For AI Vocab Server:

```python
from points_integration_example import AIVocabPoints

# Initialize the integration
vocab_points = AIVocabPoints()

# When user completes vocabulary generation
def on_vocab_generation_complete(user_name, words_generated, level):
    result = vocab_points.award_vocab_generation_points(
        user_name=user_name,
        words_generated=words_generated,
        level=level
    )
    
    if result.get('success'):
        print(f"✅ Awarded {result['points_awarded']} points to {user_name}")
    else:
        print(f"❌ Failed to award points: {result.get('error')}")

# When user completes pronunciation practice
def on_pronunciation_complete(user_name, level, duration):
    result = vocab_points.award_pronunciation_points(
        user_name=user_name,
        level=level,
        practice_duration=duration
    )
    
    if result.get('success'):
        print(f"✅ Awarded {result['points_awarded']} points to {user_name}")
```

### For Flashcard Server:

```python
from points_integration_example import FlashcardPoints

# Initialize the integration
flashcard_points = FlashcardPoints()

# When user completes flashcard review
def on_flashcard_review_complete(user_name, cards_reviewed, difficulty, mastery=False):
    result = flashcard_points.award_flashcard_review_points(
        user_name=user_name,
        cards_reviewed=cards_reviewed,
        difficulty=difficulty,
        mastery_achieved=mastery
    )
    
    if result.get('success'):
        print(f"✅ Awarded {result['points_awarded']} points to {user_name}")
    else:
        print(f"❌ Failed to award points: {result.get('error')}")

# When user completes spaced repetition
def on_spaced_repetition_complete(user_name, cards_reviewed, retention_rate):
    result = flashcard_points.award_spaced_repetition_points(
        user_name=user_name,
        cards_reviewed=cards_reviewed,
        retention_rate=retention_rate
    )
    
    if result.get('success'):
        print(f"✅ Awarded {result['points_awarded']} points to {user_name}")
```

## 🧪 Step 4: Test Integration

```python
# Test the integration
from points_integration_example import test_integration

# Run the test
test_integration()
```

## 📊 Step 5: Check Results

After integration, users will:

1. **Earn points** automatically for AI vocab activities
2. **Earn points** automatically for flashcard activities  
3. **See updated leaderboard** in real-time
4. **Compete** with other users
5. **Track progress** across all systems

## 🎯 Point Values

### AI Vocab System:
- **A1**: 15-25 points per session
- **A2**: 20-35 points per session
- **B1**: 25-45 points per session
- **B2**: 30-60 points per session
- **C1**: 40-80 points per session

### Flashcard System:
- **Easy**: 10-15 points per session
- **Medium**: 15-25 points per session
- **Hard**: 20-35 points per session
- **Expert**: 30-50 points per session
- **Mastery Bonus**: +25 points
- **Streak Bonus**: +10-20 points

## 🚀 Expected Results

After implementation:

1. **Real-time Points**: Users earn points immediately
2. **Updated Leaderboard**: Rankings change in real-time
3. **Increased Engagement**: Gamification drives more usage
4. **Cross-System Learning**: Users engage with multiple systems
5. **Social Competition**: Users compete on leaderboards

## 🆘 Troubleshooting

### Common Issues:

1. **Connection Error**: 
   - Check if social API server is running on `http://localhost:8000`
   - Verify network connectivity

2. **User Not Found**:
   - Ensure user exists in the social system
   - Check username spelling

3. **Timeout Error**:
   - Increase timeout value in the integration code
   - Check server performance

4. **Invalid Response**:
   - Check API endpoint URLs
   - Verify request format

### Debug Mode:

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test with a simple call
from points_integration_example import PointsIntegration
integration = PointsIntegration()
result = integration.get_user_points("Khanh123")
print(f"Debug result: {result}")
```

## 📞 Support

If you need help:

1. **Check the social API server** is running
2. **Verify user exists** in the social system
3. **Test with simple API calls** first
4. **Check error messages** in responses

## 🎉 Success!

Once implemented, your users will enjoy:

- ✅ **Unified Learning Experience** across all systems
- ✅ **Gamified Learning** with points and leaderboards
- ✅ **Social Competition** with other learners
- ✅ **Progress Tracking** across all activities
- ✅ **Achievement System** with badges and milestones

**The integration is ready to implement and will create an amazing unified learning platform!** 🚀
