#!/usr/bin/env python3
"""
Simple Points Integration Example
Ready-to-use code for AI Vocab and Flashcard servers
"""

import requests
import json
from typing import Dict, Any, Optional

class PointsIntegration:
    """Simple points integration for AI Vocab and Flashcard servers"""
    
    def __init__(self, social_api_url: str = "http://localhost:8000"):
        self.social_api_url = social_api_url
        self.timeout = 10
    
    def award_points(self, user_name: str, points: int, reason: str, 
                    activity_type: str, **metadata) -> Dict[str, Any]:
        """
        Award points to a user
        
        Args:
            user_name: Username of the user
            points: Number of points to award
            reason: Description of why points are awarded
            activity_type: Type of activity (ai_vocab, flashcard, etc.)
            **metadata: Additional metadata about the activity
        
        Returns:
            API response with points awarded
        """
        
        payload = {
            "points": points,
            "reason": reason,
            "activity_type": activity_type,
            "metadata": metadata
        }
        
        try:
            response = requests.post(
                f"{self.social_api_url}/social/users/{user_name}/points",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False, 
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Request failed: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {e}"}
    
    def get_user_points(self, user_name: str) -> Dict[str, Any]:
        """Get user's current points and level"""
        try:
            response = requests.get(
                f"{self.social_api_url}/social/users/{user_name}/points",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def get_leaderboard(self, user_name: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """Get current leaderboard"""
        try:
            params = {"limit": limit}
            if user_name:
                params["user_name"] = user_name
                
            response = requests.get(
                f"{self.social_api_url}/social/leaderboard",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"error": str(e)}

# AI Vocab System Integration
class AIVocabPoints:
    """Points integration for AI Vocab System"""
    
    def __init__(self, social_api_url: str = "http://localhost:8000"):
        self.integration = PointsIntegration(social_api_url)
    
    def award_vocab_generation_points(self, user_name: str, words_generated: int, 
                                    level: str, session_duration: int = 0) -> Dict[str, Any]:
        """Award points for AI vocabulary generation"""
        
        # Calculate points based on level and words
        points = self._calculate_vocab_points(words_generated, level)
        
        reason = f"AI generated {words_generated} new {level} vocabulary words"
        
        return self.integration.award_points(
            user_name=user_name,
            points=points,
            reason=reason,
            activity_type="ai_vocab_generation",
            words_generated=words_generated,
            level=level,
            session_duration=session_duration,
            system="ai_vocab"
        )
    
    def award_pronunciation_points(self, user_name: str, level: str, 
                                 practice_duration: int) -> Dict[str, Any]:
        """Award points for AI pronunciation practice"""
        
        points = self._calculate_pronunciation_points(level, practice_duration)
        
        reason = f"AI pronunciation practice for {practice_duration} minutes"
        
        return self.integration.award_points(
            user_name=user_name,
            points=points,
            reason=reason,
            activity_type="ai_pronunciation",
            level=level,
            practice_duration=practice_duration,
            system="ai_pronunciation"
        )
    
    def _calculate_vocab_points(self, words_generated: int, level: str) -> int:
        """Calculate points for vocabulary generation"""
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
    
    def _calculate_pronunciation_points(self, level: str, duration: int) -> int:
        """Calculate points for pronunciation practice"""
        base_points = {
            "A1": 10,
            "A2": 15,
            "B1": 20,
            "B2": 25,
            "C1": 30
        }
        
        base = base_points.get(level, 15)
        duration_bonus = min(duration, 30) * 0.5
        
        return int(base + duration_bonus)

# Flashcard System Integration
class FlashcardPoints:
    """Points integration for Flashcard System"""
    
    def __init__(self, social_api_url: str = "http://localhost:8000"):
        self.integration = PointsIntegration(social_api_url)
    
    def award_flashcard_review_points(self, user_name: str, cards_reviewed: int,
                                    difficulty: str, mastery_achieved: bool = False,
                                    streak_days: int = 0) -> Dict[str, Any]:
        """Award points for flashcard review"""
        
        points = self._calculate_flashcard_points(cards_reviewed, difficulty, 
                                                 mastery_achieved, streak_days)
        
        reason = f"Reviewed {cards_reviewed} {difficulty} flashcards"
        if mastery_achieved:
            reason += " (Mastery achieved!)"
        
        return self.integration.award_points(
            user_name=user_name,
            points=points,
            reason=reason,
            activity_type="flashcard_review",
            cards_reviewed=cards_reviewed,
            difficulty=difficulty,
            mastery_achieved=mastery_achieved,
            streak_days=streak_days,
            system="flashcard"
        )
    
    def award_spaced_repetition_points(self, user_name: str, cards_reviewed: int,
                                     retention_rate: float) -> Dict[str, Any]:
        """Award points for spaced repetition"""
        
        points = self._calculate_spaced_repetition_points(cards_reviewed, retention_rate)
        
        reason = f"Spaced repetition: {cards_reviewed} cards, {retention_rate:.1%} retention"
        
        return self.integration.award_points(
            user_name=user_name,
            points=points,
            reason=reason,
            activity_type="spaced_repetition",
            cards_reviewed=cards_reviewed,
            retention_rate=retention_rate,
            system="flashcard"
        )
    
    def _calculate_flashcard_points(self, cards_reviewed: int, difficulty: str,
                                  mastery_achieved: bool, streak_days: int) -> int:
        """Calculate points for flashcard activities"""
        
        difficulty_multipliers = {
            "easy": 1.0,
            "medium": 1.2,
            "hard": 1.5,
            "expert": 2.0
        }
        
        base_points = min(cards_reviewed, 25)  # Cap at 25 cards
        multiplier = difficulty_multipliers.get(difficulty, 1.0)
        
        total_points = int(base_points * multiplier)
        
        # Add bonuses
        if mastery_achieved:
            total_points += 25
        
        if streak_days >= 7:
            total_points += 20
        elif streak_days >= 3:
            total_points += 10
        
        return total_points
    
    def _calculate_spaced_repetition_points(self, cards_reviewed: int, 
                                          retention_rate: float) -> int:
        """Calculate points for spaced repetition"""
        
        base_points = cards_reviewed * 1.5
        
        # Bonus for high retention rate
        if retention_rate >= 0.8:
            base_points += 15
        elif retention_rate >= 0.6:
            base_points += 10
        
        return int(base_points)

# Usage Examples
def example_ai_vocab_integration():
    """Example of how to integrate AI Vocab system"""
    
    # Initialize the integration
    vocab_points = AIVocabPoints()
    
    # When user completes AI vocab generation
    result = vocab_points.award_vocab_generation_points(
        user_name="Khanh123",
        words_generated=20,
        level="A2",
        session_duration=15
    )
    
    print(f"AI Vocab points awarded: {result}")
    
    # When user completes pronunciation practice
    result = vocab_points.award_pronunciation_points(
        user_name="Khanh123",
        level="A2",
        practice_duration=10
    )
    
    print(f"Pronunciation points awarded: {result}")

def example_flashcard_integration():
    """Example of how to integrate Flashcard system"""
    
    # Initialize the integration
    flashcard_points = FlashcardPoints()
    
    # When user completes flashcard review
    result = flashcard_points.award_flashcard_review_points(
        user_name="Tan1",
        cards_reviewed=20,
        difficulty="medium",
        mastery_achieved=True,
        streak_days=5
    )
    
    print(f"Flashcard points awarded: {result}")
    
    # When user completes spaced repetition
    result = flashcard_points.award_spaced_repetition_points(
        user_name="Tan2",
        cards_reviewed=15,
        retention_rate=0.85
    )
    
    print(f"Spaced repetition points awarded: {result}")

def test_integration():
    """Test the integration with sample data"""
    
    print("🧪 Testing Points Integration")
    print("=" * 50)
    
    # Test AI Vocab Integration
    print("\n🤖 Testing AI Vocab Integration")
    vocab_points = AIVocabPoints()
    
    test_cases = [
        {"user": "Khanh123", "words": 20, "level": "A2"},
        {"user": "Tan1", "words": 15, "level": "A1"},
        {"user": "Tan2", "words": 25, "level": "B1"},
    ]
    
    for case in test_cases:
        result = vocab_points.award_vocab_generation_points(
            user_name=case["user"],
            words_generated=case["words"],
            level=case["level"]
        )
        print(f"  {case['user']} ({case['level']}): {result.get('success', False)}")
    
    # Test Flashcard Integration
    print("\n🃏 Testing Flashcard Integration")
    flashcard_points = FlashcardPoints()
    
    flashcard_cases = [
        {"user": "Tan3", "cards": 20, "difficulty": "medium"},
        {"user": "Tan4", "cards": 15, "difficulty": "hard"},
        {"user": "Tan5", "cards": 25, "difficulty": "expert"},
    ]
    
    for case in flashcard_cases:
        result = flashcard_points.award_flashcard_review_points(
            user_name=case["user"],
            cards_reviewed=case["cards"],
            difficulty=case["difficulty"]
        )
        print(f"  {case['user']} ({case['difficulty']}): {result.get('success', False)}")
    
    # Test getting leaderboard
    print("\n🏆 Testing Leaderboard")
    integration = PointsIntegration()
    leaderboard = integration.get_leaderboard("Khanh123")
    
    if "error" not in leaderboard:
        print(f"  Leaderboard entries: {len(leaderboard.get('entries', []))}")
    else:
        print(f"  Leaderboard error: {leaderboard['error']}")

if __name__ == "__main__":
    # Run examples
    example_ai_vocab_integration()
    example_flashcard_integration()
    
    # Run tests
    test_integration()
