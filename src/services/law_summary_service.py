"""
Legal Summary Service
Generates intelligent constitutional law summaries with customizable focus and formatting.
"""

import logging
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from models.law_summary_models import (
    LegalSummaryRequest,
    LegalSummaryResponse,
    SummarySection,
    SummaryReference,
    SummaryMetadata,
    SummaryValidationResult,
    SummaryType,
    SummaryAudience,
    FocusArea,
    ConstitutionalScope
)
from repositories.neo4j_repository import Neo4jRepository
from utils.llm_client import LlmClient
from services.query_service import QueryService

logger = logging.getLogger(__name__)


class LegalSummaryService:
    """Service for generating comprehensive legal summaries"""

    def __init__(self):
        self.neo4j_repo = Neo4jRepository()
        self.llm_client = LlmClient()
        self.query_service = QueryService()

        # Constitutional knowledge for summary generation
        self.constitutional_structure = {
            'fundamental_rights': {
                'part': 'Part III',
                'articles': ['Art-12', 'Art-13', 'Art-14', 'Art-15', 'Art-16', 'Art-17', 'Art-18', 'Art-19', 'Art-20', 'Art-21', 'Art-22'],
                'key_concepts': ['equality', 'liberty', 'due_process', 'positive_discrimination', 'judicial_review'],
                'landmark_cases': ['Maneka Gandhi', 'Kesavananda Bharati', 'Minerva Mills', 'ADM Jabalpur']
            },
            'directive_principles': {
                'part': 'Part IV',
                'articles': ['Art-36', 'Art-37', 'Art-38', 'Art-39', 'Art-40', 'Art-41', 'Art-42', 'Art-43', 'Art-44', 'Art-45', 'Art-46', 'Art-47', 'Art-48', 'Art-49', 'Art-50', 'Art-51'],
                'key_concepts': ['social_justice', 'economic_welfare', 'uniform_civil_code', 'environmental_protection'],
                'landmark_cases': ['State of Madras v. Champakam', 'Minerva Mills', 'Unnikrishnan']
            },
            'emergency_provisions': {
                'part': 'Part XVIII',
                'articles': ['Art-352', 'Art-353', 'Art-354', 'Art-355', 'Art-356', 'Art-357', 'Art-358', 'Art-359', 'Art-360'],
                'key_concepts': ['national_emergency', 'presidential_rule', 'financial_emergency', 'suspension_of_rights'],
                'landmark_cases': ['Minerva Mills', '44th Amendment case', 'S.R. Bommai']
            }
        }

        # Audience-specific writing styles
        self.writing_styles = {
            SummaryAudience.LAW_STUDENT: {
                'tone': 'educational and clear',
                'complexity': 'medium',
                'include_examples': True,
                'include_cases': True,
                'technical_depth': 'moderate'
            },
            SummaryAudience.EXAM_ASPIRANT: {
                'tone': 'concise and exam-focused',
                'complexity': 'medium',
                'include_examples': True,
                'include_cases': True,
                'technical_depth': 'exam-relevant'
            },
            SummaryAudience.LEGAL_PROFESSIONAL: {
                'tone': 'professional and comprehensive',
                'complexity': 'high',
                'include_examples': False,
                'include_cases': True,
                'technical_depth': 'detailed'
            },
            SummaryAudience.GENERAL_PUBLIC: {
                'tone': 'simple and accessible',
                'complexity': 'low',
                'include_examples': True,
                'include_cases': False,
                'technical_depth': 'basic'
            }
        }

    async def generate_legal_summary(
        self,
        request: LegalSummaryRequest,
        user_id: str = "system"
    ) -> LegalSummaryResponse:
        """Generate a comprehensive legal summary based on the request"""
        start_time = time.time()

        try:
            # 1. Analyze topic and determine scope
            topic_analysis = self._analyze_topic(request)

            # 2. Retrieve relevant constitutional content
            constitutional_content = await self._retrieve_constitutional_content(
                request, topic_analysis, user_id
            )

            # 3. Generate summary content
            summary_content = await self._generate_summary_content(
                request, constitutional_content, topic_analysis
            )

            # 4. Structure the summary based on type
            structured_content = self._structure_summary(
                summary_content, request.summary_type, request.structure
            )

            # 5. Extract key elements and references
            key_elements = self._extract_key_elements(constitutional_content, summary_content)

            # 6. Generate educational aids
            educational_aids = await self._generate_educational_aids(
                request, summary_content, key_elements
            )

            # 7. Calculate metadata
            metadata = self._calculate_summary_metadata(
                summary_content, request, start_time
            )

            # 8. Validate summary quality
            validation_result = await self._validate_summary(
                summary_content, request, key_elements
            )

            processing_time = int((time.time() - start_time) * 1000)

            return LegalSummaryResponse(
                title=self._generate_title(request.topic, request.scope),
                content=summary_content,
                sections=structured_content['sections'],
                topic=request.topic,
                summary_type=request.summary_type,
                audience=request.audience,
                key_articles=key_elements['articles'],
                key_concepts=key_elements['concepts'],
                landmark_cases=key_elements['cases'],
                constitutional_parts=key_elements['parts'],
                references=key_elements['references'],
                suggested_reading=educational_aids['suggested_reading'],
                related_topics=educational_aids['related_topics'],
                metadata=metadata,
                quick_facts=educational_aids['quick_facts'],
                exam_tips=educational_aids['exam_tips'],
                practice_questions=educational_aids['practice_questions'],
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Error generating legal summary: {e}", exc_info=True)
            raise e

    def _analyze_topic(self, request: LegalSummaryRequest) -> Dict[str, Any]:
        """Analyze the topic to understand constitutional domain and scope"""
        topic_lower = request.topic.lower()

        analysis = {
            'constitutional_domain': 'general',
            'specific_articles': [],
            'constitutional_parts': [],
            'key_themes': [],
            'complexity_level': 'medium'
        }

        # Identify constitutional domain
        for domain, info in self.constitutional_structure.items():
            domain_keywords = [domain.replace('_', ' ')] + info['key_concepts']
            if any(keyword in topic_lower for keyword in domain_keywords):
                analysis['constitutional_domain'] = domain
                analysis['constitutional_parts'].append(info['part'])
                break

        # Extract specific article mentions
        article_pattern = r'article\s*(\d+[a-z]*)'
        articles = re.findall(article_pattern, topic_lower)
        analysis['specific_articles'] = [f"Art-{art.upper()}" for art in articles]

        # Identify themes
        theme_keywords = {
            'rights': ['right', 'freedom', 'liberty', 'equality'],
            'governance': ['government', 'parliament', 'executive', 'administration'],
            'judiciary': ['court', 'judge', 'judicial', 'justice'],
            'emergency': ['emergency', 'crisis', 'suspension'],
            'amendment': ['amendment', 'change', 'modification']
        }

        for theme, keywords in theme_keywords.items():
            if any(keyword in topic_lower for keyword in keywords):
                analysis['key_themes'].append(theme)

        return analysis

    async def _retrieve_constitutional_content(
        self,
        request: LegalSummaryRequest,
        topic_analysis: Dict[str, Any],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant constitutional content for summary generation"""

        try:
            search_queries = []

            # Build queries based on filters and analysis
            if request.filters and request.filters.specific_articles:
                search_queries.extend(request.filters.specific_articles)
            elif topic_analysis['specific_articles']:
                search_queries.extend(topic_analysis['specific_articles'])

            # Add topic-based queries
            search_queries.append(request.topic)

            # Add domain-specific queries
            domain = topic_analysis['constitutional_domain']
            if domain != 'general' and domain in self.constitutional_structure:
                domain_info = self.constitutional_structure[domain]
                search_queries.extend(domain_info['key_concepts'][:3])  # Top 3 concepts

            # Retrieve content
            all_content = []
            collection_ids = ["constitution-golden-source"]

            for query in search_queries[:8]:  # Limit queries
                try:
                    content_chunks = await self.query_service.retrieve_context(
                        query=query,
                        user_id=user_id,
                        collection_ids=collection_ids,
                        top_k=5,
                        file_ids=None,
                        enable_reranking=True
                    )
                    all_content.extend(content_chunks)

                except Exception as e:
                    logger.warning(f"Failed to retrieve content for query '{query}': {e}")

            # Remove duplicates and filter by relevance
            unique_content = self._filter_and_deduplicate_content(all_content, request)

            return unique_content[:15]  # Limit to top 15 pieces

        except Exception as e:
            logger.error(f"Error retrieving constitutional content: {e}")
            return []

    def _filter_and_deduplicate_content(
        self,
        content: List[Dict[str, Any]],
        request: LegalSummaryRequest
    ) -> List[Dict[str, Any]]:
        """Filter and deduplicate content based on relevance"""

        if not content:
            return []

        # Remove duplicates by text content
        unique_content = []
        seen_texts = set()

        for item in content:
            text = item.get('text', '')
            text_hash = hash(text[:100])  # Use first 100 chars as hash

            if text_hash not in seen_texts and len(text) > 50:  # Minimum content length
                seen_texts.add(text_hash)
                unique_content.append(item)

        # Filter by specific criteria if provided
        if request.filters:
            if request.filters.specific_articles:
                filtered_content = []
                for item in unique_content:
                    text = item.get('text', '').lower()
                    if any(article.lower().replace('art-', 'article ') in text
                           for article in request.filters.specific_articles):
                        filtered_content.append(item)
                unique_content = filtered_content

        # Sort by relevance score
        unique_content.sort(key=lambda x: float(x.get('score', 0)), reverse=True)

        return unique_content

    async def _generate_summary_content(
        self,
        request: LegalSummaryRequest,
        constitutional_content: List[Dict[str, Any]],
        topic_analysis: Dict[str, Any]
    ) -> str:
        """Generate the main summary content using LLM"""

        if not constitutional_content:
            return self._generate_fallback_summary(request.topic)

        # Build context from constitutional content
        context = "\n\n".join([
            f"Source: {content.get('section_title', 'Unknown')}\n{content.get('text', '')}"
            for content in constitutional_content
        ])

        # Get writing style for audience
        style = self.writing_styles.get(request.audience, self.writing_styles[SummaryAudience.LAW_STUDENT])

        # Build focus instructions
        focus_instructions = self._build_focus_instructions(request.focus_areas)

        # Build audience-specific instructions
        audience_instructions = self._build_audience_instructions(request.audience, style)

        # Create prompt
        prompt = f"""
Generate a comprehensive legal summary on the topic: "{request.topic}"

Context from Constitutional provisions:
{context}

Requirements:
- Target audience: {request.audience.value.replace('_', ' ')}
- Summary type: {request.summary_type.value.replace('_', ' ')}
- Target length: approximately {request.target_words} words
- Complexity level: {request.complexity_level}

{audience_instructions}

Focus areas to emphasize:
{focus_instructions}

Structure:
1. Brief introduction to the topic
2. Key constitutional provisions and their significance
3. Important legal principles and concepts
4. Practical implications and applications
5. Conclusion with key takeaways

Formatting guidelines:
- Use clear, {style['tone']} language
- Include specific article references where relevant
- {"Include practical examples" if style['include_examples'] else "Focus on legal principles"}
- {"Include landmark cases" if style['include_cases'] else "Minimize case law references"}

Generate a well-structured summary that meets these requirements:
"""

        try:
            summary_content = await self.llm_client.generate_response(prompt)
            return summary_content.strip()

        except Exception as e:
            logger.error(f"Error generating summary content: {e}")
            return self._generate_fallback_summary(request.topic)

    def _build_focus_instructions(self, focus_areas: List[FocusArea]) -> str:
        """Build instructions based on focus areas"""

        focus_descriptions = {
            FocusArea.KEY_PROVISIONS: "Emphasize the most important constitutional provisions",
            FocusArea.EXCEPTIONS: "Highlight exceptions, limitations, and special cases",
            FocusArea.LANDMARK_CASES: "Include significant court decisions and their impact",
            FocusArea.AMENDMENTS: "Cover constitutional amendments and their significance",
            FocusArea.PRACTICAL_APPLICATION: "Focus on real-world applications and implications",
            FocusArea.COMPARATIVE_ANALYSIS: "Compare different provisions or constitutional systems",
            FocusArea.HISTORICAL_CONTEXT: "Provide historical background and evolution",
            FocusArea.EXAM_FOCUS: "Emphasize exam-relevant facts and commonly tested concepts"
        }

        instructions = []
        for area in focus_areas:
            if area in focus_descriptions:
                instructions.append(f"- {focus_descriptions[area]}")

        return "\n".join(instructions)

    def _build_audience_instructions(self, audience: SummaryAudience, style: Dict[str, str]) -> str:
        """Build audience-specific instructions"""

        audience_instructions = {
            SummaryAudience.LAW_STUDENT: "Write for law students learning constitutional law. Include clear explanations of legal concepts, examples, and connections between different provisions.",

            SummaryAudience.EXAM_ASPIRANT: "Write for CLAT/UGC NET exam preparation. Focus on frequently tested concepts, important facts for memorization, and exam-relevant applications.",

            SummaryAudience.LEGAL_PROFESSIONAL: "Write for practicing lawyers and legal professionals. Use precise legal terminology, focus on practical implications, and include comprehensive analysis.",

            SummaryAudience.GENERAL_PUBLIC: "Write for the general public with minimal legal background. Use simple language, avoid technical jargon, and explain concepts clearly with examples.",

            SummaryAudience.RESEARCHER: "Write for academic researchers. Include comprehensive analysis, theoretical foundations, and scholarly perspective on constitutional principles.",

            SummaryAudience.JUDICIARY_ASPIRANT: "Write for judicial service exam preparation. Focus on judicial interpretation, procedural aspects, and application of constitutional law in judicial decisions."
        }

        return audience_instructions.get(audience, audience_instructions[SummaryAudience.LAW_STUDENT])

    def _structure_summary(
        self,
        content: str,
        summary_type: SummaryType,
        structure_config: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Structure the summary based on the requested type"""

        sections = []

        if summary_type == SummaryType.BULLET_POINTS:
            sections = self._create_bullet_point_structure(content)
        elif summary_type == SummaryType.OUTLINE:
            sections = self._create_outline_structure(content)
        elif summary_type == SummaryType.TABLE:
            sections = self._create_table_structure(content)
        else:
            # Default paragraph structure
            sections = self._create_paragraph_structure(content)

        return {'sections': sections}

    def _create_bullet_point_structure(self, content: str) -> List[SummarySection]:
        """Create bullet point structured sections"""

        # Simple implementation - could be enhanced with more sophisticated parsing
        paragraphs = content.split('\n\n')
        sections = []

        current_section = None
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if this looks like a heading (short, ends with :, etc.)
            if len(para) < 100 and (para.endswith(':') or para.isupper() or
                                   any(keyword in para.lower() for keyword in ['introduction', 'key', 'important', 'conclusion'])):
                # Start new section
                if current_section:
                    sections.append(current_section)
                current_section = SummarySection(
                    title=para.replace(':', ''),
                    content="",
                    references=[],
                    key_concepts=[]
                )
            else:
                # Add to current section
                if current_section:
                    if current_section.content:
                        current_section.content += f"\n\n{para}"
                    else:
                        current_section.content = para
                else:
                    # Create a default section if none exists
                    current_section = SummarySection(
                        title="Overview",
                        content=para,
                        references=[],
                        key_concepts=[]
                    )

        # Add the last section
        if current_section:
            sections.append(current_section)

        return sections

    def _create_paragraph_structure(self, content: str) -> List[SummarySection]:
        """Create paragraph-based structure"""

        return [SummarySection(
            title="Summary",
            content=content,
            references=[],
            key_concepts=[]
        )]

    def _create_outline_structure(self, content: str) -> List[SummarySection]:
        """Create hierarchical outline structure"""
        # Simplified implementation
        return self._create_bullet_point_structure(content)

    def _create_table_structure(self, content: str) -> List[SummarySection]:
        """Create table-based structure"""
        # Simplified implementation
        return self._create_paragraph_structure(content)

    def _extract_key_elements(
        self,
        constitutional_content: List[Dict[str, Any]],
        summary_content: str
    ) -> Dict[str, Any]:
        """Extract key elements from content and summary"""

        # Extract articles mentioned
        article_pattern = r'Article\s*(\d+[A-Z]*)|Art[.-]\s*(\d+[A-Z]*)'
        article_matches = re.findall(article_pattern, summary_content, re.IGNORECASE)
        articles = []
        for match in article_matches:
            article_num = match[0] or match[1]
            if article_num:
                articles.append(f"Art-{article_num.upper()}")

        # Extract constitutional parts
        part_pattern = r'Part\s+([IVX]+)'
        part_matches = re.findall(part_pattern, summary_content, re.IGNORECASE)
        parts = [f"Part {part.upper()}" for part in part_matches]

        # Extract concepts (simplified)
        concepts = []
        concept_keywords = ['fundamental rights', 'directive principles', 'emergency', 'federalism',
                          'equality', 'liberty', 'justice', 'amendment', 'judicial review']

        for keyword in concept_keywords:
            if keyword in summary_content.lower():
                concepts.append(keyword)

        # Extract cases (simplified)
        case_pattern = r'([A-Z][a-z]+\s+(?:v\.|vs\.)\s+[A-Z][a-z]+|[A-Z][a-z]+\s+case)'
        case_matches = re.findall(case_pattern, summary_content)
        cases = [case.replace(' case', '') for case in case_matches]

        # Create references
        references = []
        for article in articles[:5]:  # Limit to 5
            references.append(SummaryReference(
                type="article",
                reference=article,
                title=f"Article {article.replace('Art-', '')}",
                relevance="Core constitutional provision discussed in summary"
            ))

        return {
            'articles': list(set(articles)),
            'concepts': concepts[:10],  # Limit to 10
            'cases': cases[:5],  # Limit to 5
            'parts': list(set(parts)),
            'references': references
        }

    async def _generate_educational_aids(
        self,
        request: LegalSummaryRequest,
        summary_content: str,
        key_elements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate educational aids like quick facts, exam tips, etc."""

        # Generate quick facts
        quick_facts = []
        if key_elements['articles']:
            quick_facts.append(f"Key Articles: {', '.join(key_elements['articles'][:5])}")
        if key_elements['parts']:
            quick_facts.append(f"Constitutional Parts: {', '.join(key_elements['parts'])}")
        if key_elements['concepts']:
            quick_facts.append(f"Main Concepts: {', '.join(key_elements['concepts'][:3])}")

        # Generate exam tips
        exam_tips = []
        if request.audience in [SummaryAudience.EXAM_ASPIRANT, SummaryAudience.LAW_STUDENT]:
            exam_tips.extend([
                "Focus on memorizing article numbers and their key provisions",
                "Understand the relationship between different constitutional provisions",
                "Practice with previous year questions on this topic"
            ])

        # Generate practice questions (simplified)
        practice_questions = []
        if key_elements['articles']:
            for article in key_elements['articles'][:2]:
                practice_questions.append(f"What are the key provisions of {article}?")
                practice_questions.append(f"Explain the significance of {article} in the constitutional framework.")

        # Suggested reading
        suggested_reading = [
            "Constitution of India (Bare Act)",
            "Constitutional Law of India by J.N. Pandey",
            "Supreme Court landmark judgments"
        ]
        if key_elements['concepts']:
            for concept in key_elements['concepts'][:2]:
                suggested_reading.append(f"Detailed study material on {concept}")

        # Related topics
        related_topics = []
        domain_relations = {
            'fundamental_rights': ['directive_principles', 'judicial_review', 'constitutional_remedies'],
            'directive_principles': ['fundamental_rights', 'social_justice', 'state_policy'],
            'emergency_provisions': ['federalism', 'center_state_relations', 'fundamental_rights_suspension']
        }

        topic_lower = request.topic.lower()
        for domain, related in domain_relations.items():
            if domain.replace('_', ' ') in topic_lower:
                related_topics.extend(related)
                break

        return {
            'quick_facts': quick_facts,
            'exam_tips': exam_tips,
            'practice_questions': practice_questions,
            'suggested_reading': suggested_reading[:5],
            'related_topics': related_topics[:5]
        }

    def _calculate_summary_metadata(
        self,
        content: str,
        request: LegalSummaryRequest,
        start_time: float
    ) -> SummaryMetadata:
        """Calculate metadata for the summary"""

        word_count = len(content.split())
        reading_time = max(1, word_count // 200)  # Assume 200 words per minute

        # Simple complexity scoring based on content analysis
        complexity_indicators = ['judicial', 'constitutional', 'interpretation', 'doctrine', 'jurisprudence']
        complexity_score = min(0.9, sum(1 for indicator in complexity_indicators if indicator in content.lower()) / len(complexity_indicators))

        # Coverage score based on word count vs target
        target_words = request.target_words
        coverage_score = min(1.0, word_count / target_words)

        return SummaryMetadata(
            word_count=word_count,
            reading_time_minutes=reading_time,
            complexity_score=complexity_score,
            coverage_score=coverage_score,
            accuracy_confidence=0.85,  # Default confidence
            last_updated=datetime.now().isoformat()
        )

    async def _validate_summary(
        self,
        content: str,
        request: LegalSummaryRequest,
        key_elements: Dict[str, Any]
    ) -> SummaryValidationResult:
        """Validate the quality and accuracy of the summary"""

        try:
            issues = []
            quality_score = 1.0

            # Check word count
            word_count = len(content.split())
            target_words = request.target_words
            if word_count < target_words * 0.8 or word_count > target_words * 1.2:
                issues.append(f"Word count ({word_count}) significantly different from target ({target_words})")
                quality_score -= 0.1

            # Check constitutional accuracy (basic)
            if key_elements['articles']:
                # Basic validation of article numbers
                for article in key_elements['articles']:
                    if not re.match(r'Art-\d+[A-Z]*', article):
                        issues.append(f"Invalid article format: {article}")
                        quality_score -= 0.1

            # Check completeness
            has_introduction = any(word in content.lower() for word in ['introduction', 'overview', 'begin'])
            has_conclusion = any(word in content.lower() for word in ['conclusion', 'summary', 'takeaway'])

            if not (has_introduction or has_conclusion):
                issues.append("Summary lacks clear introduction or conclusion")
                quality_score -= 0.1

            return SummaryValidationResult(
                is_valid=len(issues) == 0,
                constitutional_accuracy=len([i for i in issues if 'article' in i.lower()]) == 0,
                factual_accuracy=True,  # Simplified
                completeness=has_introduction and has_conclusion,
                clarity=True,  # Simplified
                audience_appropriateness=True,  # Simplified
                issues_found=issues,
                suggestions=[],
                missing_elements=[],
                overall_quality=max(0.0, quality_score),
                readability_score=0.8  # Simplified
            )

        except Exception as e:
            logger.error(f"Error validating summary: {e}")
            return SummaryValidationResult(
                is_valid=False,
                constitutional_accuracy=False,
                factual_accuracy=False,
                completeness=False,
                clarity=False,
                audience_appropriateness=False,
                issues_found=[f"Validation error: {str(e)}"],
                suggestions=[],
                missing_elements=[],
                overall_quality=0.0,
                readability_score=0.0
            )

    def _generate_fallback_summary(self, topic: str) -> str:
        """Generate a basic fallback summary when content retrieval fails"""

        return f"""
{topic} - Constitutional Overview

This summary provides a basic overview of {topic} in the Indian constitutional context.

Key Points:
• {topic} is an important aspect of Indian constitutional law
• It involves various constitutional provisions and principles
• Understanding this topic requires knowledge of relevant articles and their interpretations
• This area has been shaped by both constitutional text and judicial interpretation

For a comprehensive understanding of {topic}, please refer to:
- Relevant constitutional articles
- Supreme Court landmark judgments
- Constitutional law textbooks
- Academic commentary on the subject

Note: This is a basic overview. For detailed analysis, please ensure proper constitutional content is available.
"""

    def _generate_title(self, topic: str, scope: ConstitutionalScope) -> str:
        """Generate an appropriate title for the summary"""

        scope_prefixes = {
            ConstitutionalScope.SPECIFIC_ARTICLE: "Article-specific Analysis:",
            ConstitutionalScope.CONSTITUTIONAL_PART: "Constitutional Part Analysis:",
            ConstitutionalScope.THEMATIC: "Thematic Study:",
            ConstitutionalScope.COMPREHENSIVE: "Comprehensive Overview:"
        }

        prefix = scope_prefixes.get(scope, "Legal Summary:")
        return f"{prefix} {topic.title()}"


# Initialize service instance
legal_summary_service = LegalSummaryService()