"""
Smart Feed Service - Intelligent content filtering and recommendation
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from collections import Counter
from supabase import Client
from .social_models import (
    SmartFeedRequest, SmartFeedResponse, ContentRecommendation, 
    TrendingContent, UserPrivacySettings, PostResponse
)
from .social_service import SocialService

logger = logging.getLogger(__name__)

class SmartFeedService:
    """Intelligent feed service with level-based filtering and trending content"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.social_service = SocialService(supabase_client)
    
    def get_smart_feed(self, user_name: str, request: SmartFeedRequest) -> SmartFeedResponse:
        """Get intelligent personalized feed"""
        try:
            # Get user profile and preferences
            user_profile = self._get_user_profile(user_name)
            if not user_profile:
                raise Exception("User profile not found")
            
            # Get user's privacy settings
            privacy_settings = self._get_user_privacy_settings(user_name)
            
            # Build intelligent query
            posts = self._build_intelligent_query(user_name, user_profile, privacy_settings, request)
            
            # Get trending content
            trending_content = []
            if request.include_trending:
                trending_content = self._get_trending_content(
                    user_profile["target_language"], 
                    user_profile["user_level"]
                )
            
            # Get content recommendations
            recommendations = self._get_content_recommendations(
                user_name, user_profile, posts
            )
            
            # Apply personalization
            if request.personalization_score > 0:
                posts = self._apply_personalization(posts, user_name, request.personalization_score)
            
            # Format posts
            formatted_posts = []
            for post in posts:
                formatted_posts.append(self.social_service._format_post_response(post, user_name))
            
            # Calculate pagination
            total_posts = len(formatted_posts)
            start_idx = (request.page - 1) * request.limit
            end_idx = start_idx + request.limit
            paginated_posts = formatted_posts[start_idx:end_idx]
            
            total_pages = (total_posts + request.limit - 1) // request.limit
            
            return SmartFeedResponse(
                posts=paginated_posts,
                recommendations=recommendations,
                trending_content=trending_content,
                total_posts=total_posts,
                current_page=request.page,
                total_pages=total_pages,
                has_next=request.page < total_pages,
                feed_algorithm="intelligent_level_based",
                personalization_applied=request.personalization_score > 0
            )
            
        except Exception as e:
            logger.error(f"Error getting smart feed: {str(e)}")
            raise
    
    def _get_user_profile(self, user_name: str) -> Optional[Dict[str, Any]]:
        """Get user profile with language level and preferences"""
        try:
            response = self.supabase.table("profiles").select("*").eq("user_name", user_name).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return None
    
    def _get_user_privacy_settings(self, user_name: str) -> UserPrivacySettings:
        """Get user privacy settings"""
        try:
            response = self.supabase.table("user_privacy_settings").select("*").eq("user_name", user_name).execute()
            if response.data:
                return UserPrivacySettings(**response.data[0])
            else:
                # Create default privacy settings
                default_settings = UserPrivacySettings(user_name=user_name)
                self.supabase.table("user_privacy_settings").insert(default_settings.dict()).execute()
                return default_settings
        except Exception as e:
            logger.error(f"Error getting privacy settings: {str(e)}")
            return UserPrivacySettings(user_name=user_name)
    
    def _build_intelligent_query(self, user_name: str, user_profile: Dict[str, Any], 
                               privacy_settings: UserPrivacySettings, request: SmartFeedRequest) -> List[Dict[str, Any]]:
        """Build intelligent query based on user level and preferences"""
        try:
            # Get user's following list
            following_response = self.supabase.table("user_follows").select("following_user_name").eq("follower_user_name", user_name).execute()
            following_users = [f["following_user_name"] for f in following_response.data] if following_response.data else []
            
            # Add user's own posts
            following_users.append(user_name)
            
            # Build base query
            query = self.supabase.table("social_posts").select("*").eq("is_active", True)
            
            # Level-based filtering
            if request.include_level_peers and privacy_settings.allow_level_filtering:
                # Get users at same level
                level_peers_response = self.supabase.table("profiles").select("user_name").eq("user_level", user_profile["user_level"]).execute()
                level_peers = [p["user_name"] for p in level_peers_response.data] if level_peers_response.data else []
                
                # Get users studying same language
                language_peers_response = self.supabase.table("profiles").select("user_name").eq("target_language", user_profile["target_language"]).execute()
                language_peers = [p["user_name"] for p in language_peers_response.data] if language_peers_response.data else []
                
                # Combine all relevant users
                all_users = list(set(following_users + level_peers + language_peers))
                query = query.in_("user_name", all_users)
            else:
                query = query.in_("user_name", following_users)
            
            # Filter by post types
            if request.post_types:
                post_types = [pt.value for pt in request.post_types]
                query = query.in_("post_type", post_types)
            
            # Filter by language level
            if request.level_filter:
                # Get users at specified level
                level_users_response = self.supabase.table("profiles").select("user_name").eq("user_level", request.level_filter).execute()
                level_users = [u["user_name"] for u in level_users_response.data] if level_users_response.data else []
                query = query.in_("user_name", level_users)
            
            # Filter by target language
            if request.language_filter:
                # Get users studying specified language
                lang_users_response = self.supabase.table("profiles").select("user_name").eq("target_language", request.language_filter).execute()
                lang_users = [u["user_name"] for u in lang_users_response.data] if lang_users_response.data else []
                query = query.in_("user_name", lang_users)
            
            # Apply visibility filters
            visibility_filters = ["public"]
            if privacy_settings.show_posts_to_level == "same":
                visibility_filters.append("level_restricted")
            if privacy_settings.study_group_visibility:
                visibility_filters.append("study_group")
            
            query = query.in_("visibility", visibility_filters)
            
            # Order by creation date (newest first)
            query = query.order("created_at", desc=True)
            
            # Execute query
            response = query.execute()
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Error building intelligent query: {str(e)}")
            return []
    
    def _get_trending_content(self, target_language: str, user_level: str) -> List[TrendingContent]:
        """Get trending content for user's language and level"""
        try:
            # Get recent posts from users studying same language
            recent_posts_response = self.supabase.table("social_posts").select("content, post_type").eq("is_active", True).gte("created_at", (datetime.now() - timedelta(days=7)).isoformat()).execute()
            
            if not recent_posts_response.data:
                return []
            
            # Extract trending words and phrases
            trending_words = self._extract_trending_words(recent_posts_response.data, target_language)
            
            # Get trending topics
            trending_topics = self._extract_trending_topics(recent_posts_response.data)
            
            # Combine and format trending content
            trending_content = []
            
            for word, count in trending_words.most_common(10):
                trending_content.append(TrendingContent(
                    content_type="word",
                    content=word,
                    language=target_language,
                    level=user_level,
                    popularity_score=min(count / 10.0, 1.0),
                    usage_count=count,
                    last_updated=datetime.now().isoformat()
                ))
            
            for topic, count in trending_topics.most_common(5):
                trending_content.append(TrendingContent(
                    content_type="topic",
                    content=topic,
                    language=target_language,
                    level=user_level,
                    popularity_score=min(count / 5.0, 1.0),
                    usage_count=count,
                    last_updated=datetime.now().isoformat()
                ))
            
            return trending_content
            
        except Exception as e:
            logger.error(f"Error getting trending content: {str(e)}")
            return []
    
    def _extract_trending_words(self, posts: List[Dict[str, Any]], target_language: str) -> Counter:
        """Extract trending words from posts"""
        words = Counter()
        
        for post in posts:
            content = post.get("content", "")
            # Simple word extraction (you might want to use NLP libraries for better results)
            word_list = re.findall(r'\b[a-zA-Z]+\b', content.lower())
            
            # Filter by language relevance (simple heuristic)
            for word in word_list:
                if len(word) > 3:  # Only consider words longer than 3 characters
                    words[word] += 1
        
        return words
    
    def _extract_trending_topics(self, posts: List[Dict[str, Any]]) -> Counter:
        """Extract trending topics from posts"""
        topics = Counter()
        
        # Simple topic extraction based on post types and content
        for post in posts:
            post_type = post.get("post_type", "")
            content = post.get("content", "")
            
            # Map post types to topics
            topic_mapping = {
                "learning_tip": "Learning Tips",
                "achievement": "Achievements",
                "conversation": "Conversations",
                "milestone": "Milestones",
                "challenge": "Challenges"
            }
            
            if post_type in topic_mapping:
                topics[topic_mapping[post_type]] += 1
            
            # Extract topics from content (simple keyword matching)
            if "grammar" in content.lower():
                topics["Grammar"] += 1
            if "vocabulary" in content.lower():
                topics["Vocabulary"] += 1
            if "pronunciation" in content.lower():
                topics["Pronunciation"] += 1
            if "conversation" in content.lower():
                topics["Speaking"] += 1
        
        return topics
    
    def _get_content_recommendations(self, user_name: str, user_profile: Dict[str, Any], 
                                   posts: List[Dict[str, Any]]) -> List[ContentRecommendation]:
        """Get personalized content recommendations"""
        try:
            recommendations = []
            
            # Get user's learning history
            user_stats = self._get_user_learning_stats(user_name)
            
            # Recommend based on user's level and interests
            if user_profile["user_level"] in ["A1", "A2"]:
                recommendations.append(ContentRecommendation(
                    content_id="basic_grammar",
                    content_type="learning_tip",
                    title="Basic Grammar Tips",
                    content="Start with simple present tense and basic sentence structure",
                    relevance_score=0.9,
                    reason="Recommended for beginners",
                    author_level="A2",
                    target_language=user_profile["target_language"]
                ))
            
            # Recommend based on trending content
            trending_words = self._extract_trending_words(posts, user_profile["target_language"])
            for word, count in trending_words.most_common(3):
                recommendations.append(ContentRecommendation(
                    content_id=f"trending_{word}",
                    content_type="vocabulary",
                    title=f"Learn: {word.title()}",
                    content=f"'{word}' is trending among learners at your level",
                    relevance_score=0.7,
                    reason="Trending vocabulary",
                    author_level=user_profile["user_level"],
                    target_language=user_profile["target_language"],
                    trending_score=min(count / 10.0, 1.0)
                ))
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting content recommendations: {str(e)}")
            return []
    
    def _get_user_learning_stats(self, user_name: str) -> Dict[str, Any]:
        """Get user's learning statistics for recommendations"""
        try:
            # Get user's conversation history
            threads_response = self.supabase.table("conversation_thread").select("*").eq("user_name", user_name).execute()
            threads = threads_response.data if threads_response.data else []
            
            # Get user's posts
            posts_response = self.supabase.table("social_posts").select("*").eq("user_name", user_name).execute()
            posts = posts_response.data if posts_response.data else []
            
            return {
                "total_conversations": len(threads),
                "total_posts": len(posts),
                "active_learner": len(threads) > 5
            }
            
        except Exception as e:
            logger.error(f"Error getting user learning stats: {str(e)}")
            return {}
    
    def _apply_personalization(self, posts: List[Dict[str, Any]], user_name: str, 
                             personalization_score: float) -> List[Dict[str, Any]]:
        """Apply personalization to feed"""
        try:
            if personalization_score <= 0:
                return posts
            
            # Get user's interaction history
            user_interactions = self._get_user_interactions(user_name)
            
            # Score posts based on user preferences
            scored_posts = []
            for post in posts:
                score = self._calculate_post_relevance_score(post, user_interactions, personalization_score)
                scored_posts.append((post, score))
            
            # Sort by relevance score
            scored_posts.sort(key=lambda x: x[1], reverse=True)
            
            # Return posts in order of relevance
            return [post for post, score in scored_posts]
            
        except Exception as e:
            logger.error(f"Error applying personalization: {str(e)}")
            return posts
    
    def _get_user_interactions(self, user_name: str) -> Dict[str, Any]:
        """Get user's interaction history for personalization"""
        try:
            # Get user's likes
            likes_response = self.supabase.table("post_likes").select("post_id").eq("user_name", user_name).execute()
            liked_posts = [l["post_id"] for l in likes_response.data] if likes_response.data else []
            
            # Get user's comments
            comments_response = self.supabase.table("post_comments").select("post_id").eq("user_name", user_name).execute()
            commented_posts = [c["post_id"] for c in comments_response.data] if comments_response.data else []
            
            return {
                "liked_posts": liked_posts,
                "commented_posts": commented_posts,
                "total_interactions": len(liked_posts) + len(commented_posts)
            }
            
        except Exception as e:
            logger.error(f"Error getting user interactions: {str(e)}")
            return {}
    
    def _calculate_post_relevance_score(self, post: Dict[str, Any], user_interactions: Dict[str, Any], 
                                       personalization_score: float) -> float:
        """Calculate relevance score for a post"""
        try:
            base_score = 1.0
            
            # Boost score for posts from users the current user follows
            # (This would require additional logic to check follow relationships)
            
            # Boost score for posts of types the user interacts with
            if post["post_type"] in ["learning_tip", "achievement"]:
                base_score += 0.2
            
            # Boost score for recent posts
            post_age = datetime.now() - datetime.fromisoformat(post["created_at"].replace('Z', '+00:00'))
            if post_age.days < 1:
                base_score += 0.3
            elif post_age.days < 7:
                base_score += 0.1
            
            # Apply personalization score
            final_score = base_score * personalization_score
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating relevance score: {str(e)}")
            return 1.0
    
    def update_user_privacy_settings(self, user_name: str, settings: UserPrivacySettings) -> bool:
        """Update user privacy settings"""
        try:
            settings_dict = settings.dict()
            settings_dict["updated_at"] = datetime.now().isoformat()
            
            # Upsert privacy settings
            self.supabase.table("user_privacy_settings").upsert(settings_dict).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating privacy settings: {str(e)}")
            return False
    
    def get_trending_words(self, language: str, level: str, limit: int = 20) -> List[TrendingContent]:
        """Get trending words for specific language and level"""
        try:
            # Get recent posts from users at same level studying same language
            recent_posts_response = self.supabase.table("social_posts").select("content").eq("is_active", True).gte("created_at", (datetime.now() - timedelta(days=7)).isoformat()).execute()
            
            if not recent_posts_response.data:
                return []
            
            # Extract trending words
            trending_words = self._extract_trending_words(recent_posts_response.data, language)
            
            # Format as TrendingContent
            trending_content = []
            for word, count in trending_words.most_common(limit):
                trending_content.append(TrendingContent(
                    content_type="word",
                    content=word,
                    language=language,
                    level=level,
                    popularity_score=min(count / 10.0, 1.0),
                    usage_count=count,
                    last_updated=datetime.now().isoformat()
                ))
            
            return trending_content
            
        except Exception as e:
            logger.error(f"Error getting trending words: {str(e)}")
            return []
