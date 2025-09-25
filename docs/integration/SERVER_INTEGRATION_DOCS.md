# 🔗 Server Integration Documentation
## Points System Integration for AI Vocab & Flashcard Servers

This document provides complete implementation guide for integrating your AI vocab and flashcard servers with the social points system.

## 📋 Overview

Your servers need to call the social points API whenever users complete activities to award points and update the leaderboard in real-time.

## 🌐 API Endpoints

### Base URL
```
http://localhost:8000
```

### Authentication
All requests require the user to be authenticated. The social system will validate user credentials.

## 🎯 Points API Endpoints

### 1. Award Points to User
**Endpoint:** `POST /social/users/{user_name}/points`

**Purpose:** Award points to a user for completing activities

**Request Body:**
```json
{
    "points": 30,
    "reason": "AI generated 20 new A2 vocabulary words",
    "activity_type": "ai_vocab_generation",
    "ai_system": "vocab_generator",
    "level": "A2",
    "metadata": {
        "words_generated": 20,
        "difficulty": "intermediate",
        "session_duration": 15
    }
}
```

**Response:**
```json
{
    "success": true,
    "user_name": "Khanh123",
    "points_awarded": 30,
    "total_points": 90,
    "new_level": 2,
    "message": "Points awarded successfully"
}
```

### 2. Get User Points Summary
**Endpoint:** `GET /social/users/{user_name}/points`

**Purpose:** Get current points and level for a user

**Response:**
```json
{
    "total_points": 90,
    "available_points": 90,
    "redeemed_points": 0,
    "level": 2,
    "next_level_points": 200,
    "badges": ["first_activity", "vocab_master"]
}
```

### 3. Get Global Leaderboard
**Endpoint:** `GET /social/leaderboard`

**Purpose:** Get current leaderboard rankings

**Query Parameters:**
- `user_name`: Current user (optional)
- `limit`: Number of entries (default: 20)

**Response:**
```json
{
    "entries": [
        {
            "user_name": "Tan5",
            "total_points": 300,
            "level": 3,
            "rank": 1,
            "badges": ["ai_master", "flashcard_champion"],
            "streak_days": 7,
            "avatar_url": null
        }
    ],
    "user_rank": 4,
    "total_users": 6
}
```

## 🤖 AI Vocab System Integration

### Point Values by Level

| Level | Words Generated | Points Awarded | Activity Type |
|-------|----------------|----------------|---------------|
| A1    | 10-15 words    | 15-25 points   | Basic vocabulary |
| A2    | 15-20 words    | 20-35 points   | Intermediate vocabulary |
| B1    | 20-25 words    | 25-45 points   | Advanced vocabulary |
| B2    | 25-30 words    | 30-60 points   | Academic vocabulary |
| C1    | 30-40 words    | 40-80 points   | Professional vocabulary |

### Implementation Code

```python
import requests
import json
from typing import Dict, Any

class SocialPointsIntegration:
    def __init__(self, social_api_url: str = "http://localhost:8000"):
        self.social_api_url = social_api_url
    
    def award_vocab_points(self, user_name: str, words_generated: int, 
                          level: str, session_duration: int = 0) -> Dict[str, Any]:
        """
        Award points for AI vocabulary generation
        
        Args:
            user_name: Username of the user
            words_generated: Number of words generated
            level: User's language level (A1, A2, B1, B2, C1)
            session_duration: Duration of session in minutes
        
        Returns:
            API response with points awarded
        """
        
        # Calculate points based on level and words generated
        points = self._calculate_vocab_points(words_generated, level)
        
        payload = {
            "points": points,
            "reason": f"AI generated {words_generated} new {level} vocabulary words",
            "activity_type": "ai_vocab_generation",
            "ai_system": "vocab_generator",
            "level": level,
            "metadata": {
                "words_generated": words_generated,
                "level": level,
                "session_duration": session_duration,
                "system": "ai_vocab"
            }
        }
        
        try:
            response = requests.post(
                f"{self.social_api_url}/social/users/{user_name}/points",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error awarding points: {response.text}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            print(f"Failed to award points: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_vocab_points(self, words_generated: int, level: str) -> int:
        """Calculate points based on words generated and level"""
        base_points = {
            "A1": 15,
            "A2": 20,
            "B1": 25,
            "B2": 30,
            "C1": 40
        }
        
        multiplier = {
            "A1": 1.0,
            "A2": 1.2,
            "B1": 1.5,
            "B2": 1.8,
            "C1": 2.0
        }
        
        base = base_points.get(level, 20)
        mult = multiplier.get(level, 1.0)
        
        # Bonus for more words
        word_bonus = min(words_generated - 10, 20) * 0.5
        
        return int((base + word_bonus) * mult)
    
    def get_user_points(self, user_name: str) -> Dict[str, Any]:
        """Get user's current points and level"""
        try:
            response = requests.get(
                f"{self.social_api_url}/social/users/{user_name}/points",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": "Failed to get user points"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def get_leaderboard(self, user_name: str = None, limit: int = 20) -> Dict[str, Any]:
        """Get current leaderboard"""
        try:
            params = {"limit": limit}
            if user_name:
                params["user_name"] = user_name
                
            response = requests.get(
                f"{self.social_api_url}/social/leaderboard",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": "Failed to get leaderboard"}
                
        except Exception as e:
            return {"error": str(e)}

# Usage Example
def main():
    # Initialize the integration
    points_integration = SocialPointsIntegration()
    
    # Award points for AI vocab generation
    result = points_integration.award_vocab_points(
        user_name="Khanh123",
        words_generated=20,
        level="A2",
        session_duration=15
    )
    
    print(f"Points awarded: {result}")
    
    # Get user's current points
    user_points = points_integration.get_user_points("Khanh123")
    print(f"User points: {user_points}")
    
    # Get leaderboard
    leaderboard = points_integration.get_leaderboard("Khanh123")
    print(f"Leaderboard: {leaderboard}")

if __name__ == "__main__":
    main()
```

## 🃏 Flashcard System Integration

### Point Values by Difficulty

| Difficulty | Cards Reviewed | Points Awarded | Activity Type |
|------------|----------------|----------------|---------------|
| Easy       | 10-15 cards    | 10-15 points   | Basic flashcards |
| Medium     | 15-20 cards    | 15-25 points   | Intermediate flashcards |
| Hard       | 10-15 cards    | 20-35 points   | Advanced flashcards |
| Expert     | 15-25 cards    | 30-50 points   | Expert flashcards |

### Implementation Code

```python
class FlashcardPointsIntegration:
    def __init__(self, social_api_url: str = "http://localhost:8000"):
        self.social_api_url = social_api_url
    
    def award_flashcard_points(self, user_name: str, cards_reviewed: int,
                              difficulty: str, mastery_achieved: bool = False,
                              streak_days: int = 0) -> Dict[str, Any]:
        """
        Award points for flashcard activities
        
        Args:
            user_name: Username of the user
            cards_reviewed: Number of cards reviewed
            difficulty: Difficulty level (easy, medium, hard, expert)
            mastery_achieved: Whether user achieved mastery
            streak_days: Current streak in days
        
        Returns:
            API response with points awarded
        """
        
        # Calculate base points
        base_points = self._calculate_flashcard_points(cards_reviewed, difficulty)
        
        # Add bonuses
        total_points = base_points
        
        if mastery_achieved:
            total_points += 25  # Mastery bonus
        
        if streak_days >= 7:
            total_points += 20  # Streak bonus
        
        payload = {
            "points": total_points,
            "reason": f"Reviewed {cards_reviewed} {difficulty} flashcards",
            "activity_type": "flashcard_review",
            "difficulty": difficulty,
            "metadata": {
                "cards_reviewed": cards_reviewed,
                "difficulty": difficulty,
                "mastery_achieved": mastery_achieved,
                "streak_days": streak_days,
                "system": "flashcard"
            }
        }
        
        try:
            response = requests.post(
                f"{self.social_api_url}/social/users/{user_name}/points",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": response.text}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _calculate_flashcard_points(self, cards_reviewed: int, difficulty: str) -> int:
        """Calculate points based on cards reviewed and difficulty"""
        difficulty_multipliers = {
            "easy": 1.0,
            "medium": 1.2,
            "hard": 1.5,
            "expert": 2.0
        }
        
        base_points = min(cards_reviewed, 25)  # Cap at 25 cards
        multiplier = difficulty_multipliers.get(difficulty, 1.0)
        
        return int(base_points * multiplier)
    
    def award_spaced_repetition_points(self, user_name: str, cards_reviewed: int,
                                     retention_rate: float) -> Dict[str, Any]:
        """Award points for spaced repetition sessions"""
        
        # Base points for spaced repetition
        base_points = cards_reviewed * 1.5
        
        # Bonus for high retention rate
        if retention_rate >= 0.8:
            base_points += 15
        
        payload = {
            "points": int(base_points),
            "reason": f"Spaced repetition: {cards_reviewed} cards, {retention_rate:.1%} retention",
            "activity_type": "spaced_repetition",
            "metadata": {
                "cards_reviewed": cards_reviewed,
                "retention_rate": retention_rate,
                "system": "flashcard"
            }
        }
        
        try:
            response = requests.post(
                f"{self.social_api_url}/social/users/{user_name}/points",
                json=payload,
                timeout=10
            )
            
            return response.json() if response.status_code == 200 else {"success": False}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Usage Example
def flashcard_example():
    integration = FlashcardPointsIntegration()
    
    # Award points for flashcard review
    result = integration.award_flashcard_points(
        user_name="Tan1",
        cards_reviewed=20,
        difficulty="medium",
        mastery_achieved=True,
        streak_days=5
    )
    
    print(f"Flashcard points awarded: {result}")
    
    # Award points for spaced repetition
    result = integration.award_spaced_repetition_points(
        user_name="Tan2",
        cards_reviewed=15,
        retention_rate=0.85
    )
    
    print(f"Spaced repetition points awarded: {result}")
```

## 🔧 Configuration

### Environment Variables
```bash
# Social API Configuration
SOCIAL_API_URL=http://localhost:8000
SOCIAL_API_TIMEOUT=10

# Points Configuration
ENABLE_POINTS_AWARDING=true
POINTS_DEBUG_MODE=false
```

### Error Handling
```python
def safe_award_points(integration, user_name, **kwargs):
    """Safely award points with error handling"""
    try:
        result = integration.award_vocab_points(user_name, **kwargs)
        
        if result.get("success", False):
            print(f"✅ Points awarded successfully: {result['points_awarded']}")
            return True
        else:
            print(f"❌ Failed to award points: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Exception awarding points: {e}")
        return False
```

## 📊 Testing Integration

### Test Script
```python
def test_integration():
    """Test the points integration"""
    
    # Test AI Vocab Integration
    vocab_integration = SocialPointsIntegration()
    
    test_cases = [
        {"user": "Khanh123", "words": 20, "level": "A2"},
        {"user": "Tan1", "words": 15, "level": "A1"},
        {"user": "Tan2", "words": 25, "level": "B1"},
    ]
    
    for case in test_cases:
        result = vocab_integration.award_vocab_points(
            user_name=case["user"],
            words_generated=case["words"],
            level=case["level"]
        )
        print(f"Test {case['user']}: {result}")
    
    # Test Flashcard Integration
    flashcard_integration = FlashcardPointsIntegration()
    
    flashcard_cases = [
        {"user": "Tan3", "cards": 20, "difficulty": "medium"},
        {"user": "Tan4", "cards": 15, "difficulty": "hard"},
        {"user": "Tan5", "cards": 25, "difficulty": "expert"},
    ]
    
    for case in flashcard_cases:
        result = flashcard_integration.award_flashcard_points(
            user_name=case["user"],
            cards_reviewed=case["cards"],
            difficulty=case["difficulty"]
        )
        print(f"Flashcard test {case['user']}: {result}")

if __name__ == "__main__":
    test_integration()
```

## 🚀 Implementation Checklist

### For AI Vocab Server:
- [ ] Install `requests` library
- [ ] Add `SocialPointsIntegration` class
- [ ] Call `award_vocab_points()` after vocabulary generation
- [ ] Handle errors gracefully
- [ ] Test with different user levels
- [ ] Monitor API responses

### For Flashcard Server:
- [ ] Install `requests` library  
- [ ] Add `FlashcardPointsIntegration` class
- [ ] Call `award_flashcard_points()` after flashcard sessions
- [ ] Call `award_spaced_repetition_points()` for spaced repetition
- [ ] Handle errors gracefully
- [ ] Test with different difficulties
- [ ] Monitor API responses

## 📈 Expected Results

After implementation, you should see:

1. **Real-time Points**: Users earn points immediately after activities
2. **Updated Leaderboard**: Rankings change in real-time
3. **User Engagement**: Increased activity due to gamification
4. **Cross-System Learning**: Users engage with multiple systems
5. **Social Competition**: Users compete on leaderboards

## 🆘 Troubleshooting

### Common Issues:
1. **Connection Errors**: Check if social API server is running
2. **Authentication Errors**: Ensure user exists in social system
3. **Timeout Errors**: Increase timeout values
4. **Invalid Responses**: Check API endpoint URLs

### Debug Mode:
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test with debug output
integration = SocialPointsIntegration()
result = integration.award_vocab_points("test_user", 10, "A1")
print(f"Debug result: {result}")
```

## 📞 Support

If you need help with implementation:
1. Check the social API server is running on `http://localhost:8000`
2. Verify user exists in the social system
3. Test with simple API calls first
4. Check error messages in responses

**The integration is ready to implement and will create a unified, gamified learning experience!** 🚀
