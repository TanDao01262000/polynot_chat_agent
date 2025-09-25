"""
Study Analytics Service - Global word study analytics and insights
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from collections import Counter
from supabase import Client
from .social_models import (
    WordStudyRecord, GlobalWordAnalytics, StudyInsights, 
    WordRecommendation, StudyAnalyticsRequest, StudyAnalyticsResponse
)

logger = logging.getLogger(__name__)

class StudyAnalyticsService:
    """Service for tracking and analyzing global word study patterns"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
    
    def record_word_study(self, user_name: str, word: str, language: str, 
                          level: str, study_type: str, context: Optional[str] = None,
                          difficulty_score: Optional[float] = None) -> bool:
        """Record a word being studied by a user"""
        try:
            # Create study record
            study_record = {
                "id": str(uuid.uuid4()),
                "user_name": user_name,
                "word": word.lower().strip(),
                "language": language,
                "level": level,
                "study_type": study_type,
                "context": context,
                "difficulty_score": difficulty_score,
                "created_at": datetime.now().isoformat()
            }
            
            self.supabase.table("word_study_records").insert(study_record).execute()
            
            # Update global analytics
            self._update_global_word_analytics(word.lower().strip(), language)
            
            # Update user insights
            self._update_user_study_insights(user_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording word study: {str(e)}")
            return False
    
    def get_global_word_analytics(self, word: str, language: str) -> Optional[GlobalWordAnalytics]:
        """Get global analytics for a specific word"""
        try:
            response = self.supabase.table("global_word_analytics").select("*").eq("word", word.lower()).eq("language", language).execute()
            
            if not response.data:
                return None
            
            data = response.data[0]
            return GlobalWordAnalytics(
                word=data["word"],
                language=data["language"],
                total_studiers=data["total_studiers"],
                today_studiers=data["today_studiers"],
                this_week_studiers=data["this_week_studiers"],
                level_breakdown=data["level_breakdown"],
                study_types=data["study_types"],
                average_difficulty=data["average_difficulty"],
                popularity_trend=data["popularity_trend"],
                last_updated=data["last_updated"]
            )
            
        except Exception as e:
            logger.error(f"Error getting global word analytics: {str(e)}")
            return None
    
    def get_study_analytics(self, request: StudyAnalyticsRequest, user_name: Optional[str] = None) -> StudyAnalyticsResponse:
        """Get comprehensive study analytics"""
        try:
            # Get global word analytics
            analytics = self._get_global_analytics(request)
            
            # Get user insights if user_name provided
            user_insights = None
            if user_name:
                user_insights = self._get_user_study_insights(user_name)
            
            # Get word recommendations
            recommendations = self._get_word_recommendations(request, user_name)
            
            return StudyAnalyticsResponse(
                analytics=analytics,
                user_insights=user_insights,
                recommendations=recommendations,
                total_words=len(analytics),
                time_period=request.time_period,
                last_updated=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error getting study analytics: {str(e)}")
            raise
    
    def get_trending_words(self, language: str, level: Optional[str] = None, limit: int = 20) -> List[GlobalWordAnalytics]:
        """Get trending words for a language and level"""
        try:
            query = self.supabase.table("global_word_analytics").select("*").eq("language", language)
            
            if level:
                # Filter by level breakdown
                query = query.contains("level_breakdown", {level: {"$gt": 0}})
            
            # Order by today's studiers
            query = query.order("today_studiers", desc=True).limit(limit)
            
            response = query.execute()
            if not response.data:
                return []
            
            analytics = []
            for data in response.data:
                analytics.append(GlobalWordAnalytics(
                    word=data["word"],
                    language=data["language"],
                    total_studiers=data["total_studiers"],
                    today_studiers=data["today_studiers"],
                    this_week_studiers=data["this_week_studiers"],
                    level_breakdown=data["level_breakdown"],
                    study_types=data["study_types"],
                    average_difficulty=data["average_difficulty"],
                    popularity_trend=data["popularity_trend"],
                    last_updated=data["last_updated"]
                ))
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting trending words: {str(e)}")
            return []
    
    def get_user_study_insights(self, user_name: str) -> Optional[StudyInsights]:
        """Get study insights for a specific user"""
        try:
            return self._get_user_study_insights(user_name)
        except Exception as e:
            logger.error(f"Error getting user study insights: {str(e)}")
            return None
    
    def _update_global_word_analytics(self, word: str, language: str):
        """Update global analytics for a word"""
        try:
            # Get current analytics
            response = self.supabase.table("global_word_analytics").select("*").eq("word", word).eq("language", language).execute()
            
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)
            
            if response.data:
                # Update existing record
                current = response.data[0]
                
                # Calculate new values
                total_studiers = current["total_studiers"] + 1
                today_studiers = current["today_studiers"] + 1
                this_week_studiers = current["this_week_studiers"] + 1
                
                # Update level breakdown
                level_breakdown = current["level_breakdown"]
                # This would need to be calculated from recent records
                
                # Update study types
                study_types = current["study_types"]
                # This would need to be calculated from recent records
                
                # Calculate popularity trend
                popularity_trend = self._calculate_popularity_trend(word, language)
                
                update_data = {
                    "total_studiers": total_studiers,
                    "today_studiers": today_studiers,
                    "this_week_studiers": this_week_studiers,
                    "level_breakdown": level_breakdown,
                    "study_types": study_types,
                    "popularity_trend": popularity_trend,
                    "last_updated": now.isoformat()
                }
                
                self.supabase.table("global_word_analytics").update(update_data).eq("word", word).eq("language", language).execute()
            else:
                # Create new record
                new_record = {
                    "id": str(uuid.uuid4()),
                    "word": word,
                    "language": language,
                    "total_studiers": 1,
                    "today_studiers": 1,
                    "this_week_studiers": 1,
                    "level_breakdown": {},
                    "study_types": {},
                    "average_difficulty": 0.0,
                    "popularity_trend": "stable",
                    "last_updated": now.isoformat()
                }
                
                self.supabase.table("global_word_analytics").insert(new_record).execute()
                
        except Exception as e:
            logger.error(f"Error updating global word analytics: {str(e)}")
    
    def _update_user_study_insights(self, user_name: str):
        """Update user study insights"""
        try:
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)
            
            # Get user's study records
            today_records = self.supabase.table("word_study_records").select("*").eq("user_name", user_name).gte("created_at", today_start.isoformat()).execute()
            week_records = self.supabase.table("word_study_records").select("*").eq("user_name", user_name).gte("created_at", week_start.isoformat()).execute()
            all_records = self.supabase.table("word_study_records").select("*").eq("user_name", user_name).execute()
            
            # Calculate insights
            words_studied_today = len(today_records.data) if today_records.data else 0
            words_studied_this_week = len(week_records.data) if week_records.data else 0
            total_words_studied = len(all_records.data) if all_records.data else 0
            
            # Get most difficult words
            most_difficult_words = self._get_most_difficult_words(user_name)
            
            # Calculate study streak
            study_streak = self._calculate_study_streak(user_name)
            
            # Get user's level and calculate progress
            user_response = self.supabase.table("profiles").select("user_level").eq("user_name", user_name).execute()
            user_level = user_response.data[0]["user_level"] if user_response.data else "A1"
            level_progress = self._calculate_level_progress(user_name, user_level)
            
            # Calculate rankings
            global_rank = self._calculate_global_rank(user_name)
            level_rank = self._calculate_level_rank(user_name, user_level)
            
            # Update or create user insights
            insights_data = {
                "user_name": user_name,
                "words_studied_today": words_studied_today,
                "words_studied_this_week": words_studied_this_week,
                "total_words_studied": total_words_studied,
                "most_difficult_words": most_difficult_words,
                "study_streak": study_streak,
                "level_progress": level_progress,
                "global_rank": global_rank,
                "level_rank": level_rank,
                "last_updated": now.isoformat()
            }
            
            # Check if user insights exist
            existing_response = self.supabase.table("user_study_insights").select("*").eq("user_name", user_name).execute()
            
            if existing_response.data:
                self.supabase.table("user_study_insights").update(insights_data).eq("user_name", user_name).execute()
            else:
                insights_data["id"] = str(uuid.uuid4())
                self.supabase.table("user_study_insights").insert(insights_data).execute()
                
        except Exception as e:
            logger.error(f"Error updating user study insights: {str(e)}")
    
    def _get_global_analytics(self, request: StudyAnalyticsRequest) -> List[GlobalWordAnalytics]:
        """Get global analytics based on request"""
        try:
            query = self.supabase.table("global_word_analytics").select("*").eq("language", request.language)
            
            if request.level:
                query = query.contains("level_breakdown", {request.level: {"$gt": 0}})
            
            # Filter by time period
            if request.time_period == "today":
                query = query.order("today_studiers", desc=True)
            elif request.time_period == "week":
                query = query.order("this_week_studiers", desc=True)
            else:
                query = query.order("total_studiers", desc=True)
            
            query = query.limit(request.limit)
            
            response = query.execute()
            if not response.data:
                return []
            
            analytics = []
            for data in response.data:
                analytics.append(GlobalWordAnalytics(
                    word=data["word"],
                    language=data["language"],
                    total_studiers=data["total_studiers"],
                    today_studiers=data["today_studiers"],
                    this_week_studiers=data["this_week_studiers"],
                    level_breakdown=data["level_breakdown"],
                    study_types=data["study_types"],
                    average_difficulty=data["average_difficulty"],
                    popularity_trend=data["popularity_trend"],
                    last_updated=data["last_updated"]
                ))
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting global analytics: {str(e)}")
            return []
    
    def _get_user_study_insights(self, user_name: str) -> Optional[StudyInsights]:
        """Get user study insights"""
        try:
            response = self.supabase.table("user_study_insights").select("*").eq("user_name", user_name).execute()
            
            if not response.data:
                return None
            
            data = response.data[0]
            return StudyInsights(
                user_name=data["user_name"],
                words_studied_today=data["words_studied_today"],
                words_studied_this_week=data["words_studied_this_week"],
                total_words_studied=data["total_words_studied"],
                most_difficult_words=data["most_difficult_words"],
                study_streak=data["study_streak"],
                level_progress=data["level_progress"],
                global_rank=data["global_rank"],
                level_rank=data["level_rank"]
            )
            
        except Exception as e:
            logger.error(f"Error getting user study insights: {str(e)}")
            return None
    
    def _get_word_recommendations(self, request: StudyAnalyticsRequest, user_name: Optional[str] = None) -> List[WordRecommendation]:
        """Get word recommendations based on analytics"""
        try:
            # Get trending words
            trending_words = self.get_trending_words(request.language, request.level, 10)
            
            recommendations = []
            for word_analytics in trending_words:
                # Calculate popularity score
                popularity_score = min(word_analytics.today_studiers / 10.0, 1.0)
                
                # Determine if trending
                trending = word_analytics.popularity_trend == "increasing"
                
                # Generate reason
                reason = f"Studied by {word_analytics.today_studiers} people today"
                if trending:
                    reason += " (trending up!)"
                
                recommendations.append(WordRecommendation(
                    word=word_analytics.word,
                    language=word_analytics.language,
                    level=request.level or "A1",
                    reason=reason,
                    popularity_score=popularity_score,
                    difficulty_score=word_analytics.average_difficulty,
                    study_count=word_analytics.today_studiers,
                    trending=trending
                ))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting word recommendations: {str(e)}")
            return []
    
    def _calculate_popularity_trend(self, word: str, language: str) -> str:
        """Calculate popularity trend for a word"""
        try:
            # Get recent analytics
            response = self.supabase.table("global_word_analytics").select("today_studiers, this_week_studiers").eq("word", word).eq("language", language).execute()
            
            if not response.data:
                return "stable"
            
            data = response.data[0]
            today = data["today_studiers"]
            this_week = data["this_week_studiers"]
            
            # Simple trend calculation
            if today > this_week * 0.2:  # More than 20% of week's total today
                return "increasing"
            elif today < this_week * 0.1:  # Less than 10% of week's total today
                return "decreasing"
            else:
                return "stable"
                
        except Exception as e:
            logger.error(f"Error calculating popularity trend: {str(e)}")
            return "stable"
    
    def _get_most_difficult_words(self, user_name: str) -> List[str]:
        """Get most difficult words for a user"""
        try:
            response = self.supabase.table("word_study_records").select("word, difficulty_score").eq("user_name", user_name).not_null("difficulty_score").order("difficulty_score", desc=True).limit(5).execute()
            
            if not response.data:
                return []
            
            return [record["word"] for record in response.data]
            
        except Exception as e:
            logger.error(f"Error getting most difficult words: {str(e)}")
            return []
    
    def _calculate_study_streak(self, user_name: str) -> int:
        """Calculate user's study streak in days"""
        try:
            # Get user's study records ordered by date
            response = self.supabase.table("word_study_records").select("created_at").eq("user_name", user_name).order("created_at", desc=True).execute()
            
            if not response.data:
                return 0
            
            # Calculate streak
            streak = 0
            current_date = datetime.now().date()
            
            for record in response.data:
                record_date = datetime.fromisoformat(record["created_at"].replace('Z', '+00:00')).date()
                if record_date == current_date or record_date == current_date - timedelta(days=streak):
                    streak += 1
                    current_date = record_date
                else:
                    break
            
            return streak
            
        except Exception as e:
            logger.error(f"Error calculating study streak: {str(e)}")
            return 0
    
    def _calculate_level_progress(self, user_name: str, level: str) -> Dict[str, Any]:
        """Calculate user's progress within their level"""
        try:
            # Get user's study records
            response = self.supabase.table("word_study_records").select("*").eq("user_name", user_name).execute()
            
            if not response.data:
                return {"words_learned": 0, "progress_percentage": 0}
            
            # Calculate progress based on words studied
            words_learned = len(response.data)
            
            # Simple progress calculation (could be more sophisticated)
            level_thresholds = {"A1": 100, "A2": 200, "B1": 500, "B2": 1000, "C1": 2000, "C2": 3000}
            threshold = level_thresholds.get(level, 100)
            progress_percentage = min((words_learned / threshold) * 100, 100)
            
            return {
                "words_learned": words_learned,
                "progress_percentage": progress_percentage,
                "next_milestone": threshold
            }
            
        except Exception as e:
            logger.error(f"Error calculating level progress: {str(e)}")
            return {"words_learned": 0, "progress_percentage": 0}
    
    def _calculate_global_rank(self, user_name: str) -> Optional[int]:
        """Calculate user's global ranking"""
        try:
            # Get all users ordered by total words studied
            response = self.supabase.table("user_study_insights").select("user_name, total_words_studied").order("total_words_studied", desc=True).execute()
            
            if not response.data:
                return None
            
            # Find user's rank
            for i, user_data in enumerate(response.data):
                if user_data["user_name"] == user_name:
                    return i + 1
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating global rank: {str(e)}")
            return None
    
    def _calculate_level_rank(self, user_name: str, level: str) -> Optional[int]:
        """Calculate user's ranking within their level"""
        try:
            # Get users at same level ordered by total words studied
            response = self.supabase.table("user_study_insights").select("user_name, total_words_studied").eq("level", level).order("total_words_studied", desc=True).execute()
            
            if not response.data:
                return None
            
            # Find user's rank within level
            for i, user_data in enumerate(response.data):
                if user_data["user_name"] == user_name:
                    return i + 1
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating level rank: {str(e)}")
            return None
