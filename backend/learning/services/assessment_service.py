import json
import logging

from collections import Counter
from django.db import transaction
from django.utils import timezone

from learning.models import (
    Enrollment,
    Assessment,
    Question,
    AIGenerationJob,
)

from .groq_service import (
    generate_response,
    LearningAIError,
)


logger = logging.getLogger(__name__)

INITIAL_QUESTION_COUNT = 15
MCQ_COUNT = 12
WRITTEN_COUNT = 3


# ==========================================
# 1. Language-specific assessment topics
# ==========================================

LANGUAGE_TOPICS = {
    "cpp": [
        "Variables and Data Types",
        "Operators",
        "Conditional Statements",
        "Loops",
        "Arrays and Strings",
        "Functions",
        "Pointers and References",
        "Object-Oriented Programming",
        "STL Fundamentals",
    ],

    "python": [
        "Variables and Data Types",
        "Operators",
        "Conditional Statements",
        "Loops",
        "Lists and Tuples",
        "Dictionaries and Sets",
        "Functions",
        "Exception Handling",
        "Object-Oriented Programming",
    ],

    "javascript": [
        "Variables and Data Types",
        "Operators",
        "Conditional Statements",
        "Loops",
        "Arrays and Objects",
        "Functions",
        "Scope",
        "DOM Fundamentals",
        "Promises and Async Fundamentals",
    ],

    "java": [
        "Variables and Data Types",
        "Operators",
        "Conditional Statements",
        "Loops",
        "Arrays and Strings",
        "Methods",
        "Classes and Objects",
        "Inheritance and Polymorphism",
        "Exception Handling",
    ],

    "sql": [
        "SELECT Statements",
        "WHERE Clause",
        "Operators",
        "ORDER BY",
        "Aggregate Functions",
        "GROUP BY and HAVING",
        "Joins",
        "Subqueries",
        "Database Constraints",
    ],
}


# ==========================================
# 2. Assessment generation prompt
# ==========================================

def build_initial_assessment_prompt(language):

    language_name = Enrollment.Language(language).label
    topics = LANGUAGE_TOPICS[language]

    system_prompt = """
    You are an expert programming instructor
    and technical assessment designer.

    Your responsibility is to generate accurate,
    balanced programming assessments.

    Follow these rules:

    1. Return only a valid JSON object.
    2. Generate technically correct questions.
    3. Avoid duplicate or ambiguous questions.
    4. Use simple and understandable language.
    5. Include both conceptual and practical questions.
    6. Every MCQ must have exactly four unique options.
    7. Every MCQ must have exactly one correct answer.
    8. Written questions must have empty options.
    9. Include reference answers and explanations.
    10. Do not generate advanced-level questions.
    11. Distribute correct MCQ answers across positions.
    12. Cover a broad range of the supplied topics.
    """

    user_prompt = f"""
    Generate an initial skill assessment for
    the programming language: {language_name}.

    Topics:
    {json.dumps(topics)}

    Assessment requirements:

    - Exactly 15 questions.
    - Exactly 12 multiple-choice questions.
    - Exactly 3 written questions.
    - Written questions must include both coding
      and theory questions.
    - Exactly 8 basic questions.
    - Exactly 7 intermediate questions.
    - Each MCQ carries 1 mark.
    - Each written question carries 3 marks.
    - Total assessment marks: 21.

    Allowed question types:
    mcq, coding, theory

    Allowed difficulty levels:
    basic, intermediate

    Use the supplied topic names exactly.

    For SQL, use standard SQL syntax.
    For SQL coding questions involving tables,
    provide the necessary table schema.

    Return JSON using this structure:

    {{
        "language": "{language}",
        "title": "{language_name} Initial Assessment",
        "questions": [
            {{
                "question_type": "mcq",
                "topic": "Topic name",
                "difficulty": "basic",
                "question_text": "Question text",
                "options": [
                    "Option A",
                    "Option B",
                    "Option C",
                    "Option D"
                ],
                "correct_answer": "Option B",
                "explanation": "Correct answer explanation",
                "marks": 1
            }},
            {{
                "question_type": "coding",
                "topic": "Topic name",
                "difficulty": "intermediate",
                "question_text": "Write a program...",
                "options": [],
                "correct_answer": "Reference solution",
                "explanation": "Solution and scoring criteria",
                "marks": 3
            }}
        ]
    }}

    Generate all 15 questions.
    """

    return system_prompt, user_prompt


# ==========================================
# 3. Validate AI-generated assessment
# ==========================================

def validate_assessment(data, language):

    if not isinstance(data, dict):
        raise LearningAIError(
            "Assessment must be a JSON object."
        )

    if data.get("language") != language:
        raise LearningAIError(
            "Generated assessment language is incorrect."
        )

    title = data.get("title")

    if (
        not isinstance(title, str)
        or not title.strip()
        or len(title) > 200
    ):
        raise LearningAIError(
            "Invalid assessment title."
        )

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise LearningAIError(
            "Questions must be a list."
        )

    if len(questions) != INITIAL_QUESTION_COUNT:
        raise LearningAIError(
            "Assessment must contain exactly 15 questions."
        )

    type_counts = Counter()
    difficulty_counts = Counter()
    seen_questions = set()

    required_fields = [
        "question_type",
        "topic",
        "difficulty",
        "question_text",
        "options",
        "correct_answer",
        "explanation",
        "marks",
    ]

    for index, question in enumerate(questions, start=1):

        if not isinstance(question, dict):
            raise LearningAIError(
                f"Question {index} must be an object."
            )

        for field in required_fields:
            if field not in question:
                raise LearningAIError(
                    f"Question {index}: Missing {field}"
                )

        text_fields = [
            "question_type",
            "topic",
            "difficulty",
            "question_text",
            "correct_answer",
            "explanation",
        ]

        for field in text_fields:
            if (
                not isinstance(question[field], str)
                or not question[field].strip()
            ):
                raise LearningAIError(
                    f"Question {index}: Invalid {field}"
                )

        question_type = question["question_type"]
        difficulty = question["difficulty"]

        if question_type not in [
            "mcq",
            "coding",
            "theory",
        ]:
            raise LearningAIError(
                f"Question {index}: Invalid question type"
            )

        if difficulty not in [
            "basic",
            "intermediate",
        ]:
            raise LearningAIError(
                f"Question {index}: Invalid difficulty"
            )

        if question["topic"] not in LANGUAGE_TOPICS[language]:
            raise LearningAIError(
                f"Question {index}: Invalid topic"
            )

        normalized_question = " ".join(
            question["question_text"].lower().split()
        )

        if normalized_question in seen_questions:
            raise LearningAIError(
                "Duplicate question detected."
            )

        seen_questions.add(normalized_question)

        options = question["options"]
        marks = question["marks"]

        if type(marks) is not int:
            raise LearningAIError(
                f"Question {index}: Marks must be integers"
            )

        # Validate MCQs
        if question_type == "mcq":

            if (
                not isinstance(options, list)
                or len(options) != 4
            ):
                raise LearningAIError(
                    f"Question {index}: Requires 4 options"
                )

            if any(
                not isinstance(option, str)
                or not option.strip()
                for option in options
            ):
                raise LearningAIError(
                    f"Question {index}: Invalid options"
                )

            normalized_options = {
                option.strip().casefold()
                for option in options
            }

            if len(normalized_options) != 4:
                raise LearningAIError(
                    f"Question {index}: Duplicate options"
                )

            if question["correct_answer"] not in options:
                raise LearningAIError(
                    f"Question {index}: Invalid correct answer"
                )

            if marks != 1:
                raise LearningAIError(
                    f"Question {index}: MCQ must carry 1 mark"
                )

        # Validate written questions
        else:

            if options != []:
                raise LearningAIError(
                    f"Question {index}: Options must be empty"
                )

            if marks != 3:
                raise LearningAIError(
                    f"Question {index}: Must carry 3 marks"
                )

        type_counts[question_type] += 1
        difficulty_counts[difficulty] += 1

    if type_counts["mcq"] != MCQ_COUNT:
        raise LearningAIError(
            "Exactly 12 MCQs are required."
        )

    written_count = (
        type_counts["coding"]
        + type_counts["theory"]
    )

    if written_count != WRITTEN_COUNT:
        raise LearningAIError(
            "Exactly 3 written questions are required."
        )

    if (
        type_counts["coding"] == 0
        or type_counts["theory"] == 0
    ):
        raise LearningAIError(
            "Both coding and theory questions are required."
        )

    if (
        difficulty_counts["basic"] != 8
        or difficulty_counts["intermediate"] != 7
    ):
        raise LearningAIError(
            "Invalid difficulty distribution."
        )

    return data


# ==========================================
# 4. Generate and save initial assessment
# ==========================================

def generate_initial_assessment(enrollment):

    language = enrollment.language

    if language not in LANGUAGE_TOPICS:
        raise LearningAIError(
            "Unsupported programming language."
        )

    # Return an existing assessment if available
    existing_assessment = Assessment.objects.filter(
        enrollment=enrollment,
        assessment_type=Assessment.AssessmentType.INITIAL,
        day_number=0,
    ).first()

    if existing_assessment:
        return existing_assessment

    # Create or retrieve AI generation job
    job, created = AIGenerationJob.objects.get_or_create(
        idempotency_key=(
            f"initial_assessment_{enrollment.id}"
        ),
        defaults={
            "enrollment": enrollment,
            "job_type": (
                AIGenerationJob.JobType.INITIAL_ASSESSMENT
            ),
            "request_data": {
                "language": language,
                "total_questions": INITIAL_QUESTION_COUNT,
                "mcq_count": MCQ_COUNT,
                "written_count": WRITTEN_COUNT,
            },
        },
    )

    # Atomically claim pending or failed job
    claimed = AIGenerationJob.objects.filter(
        pk=job.pk,
        status__in=[
            AIGenerationJob.Status.PENDING,
            AIGenerationJob.Status.FAILED,
        ],
    ).update(
        status=AIGenerationJob.Status.PROCESSING,
        started_at=timezone.now(),
        updated_at=timezone.now(),
        completed_at=None,
        error_message="",
    )

    if not claimed:
        existing_assessment = Assessment.objects.filter(
            enrollment=enrollment,
            assessment_type=Assessment.AssessmentType.INITIAL,
            day_number=0,
        ).first()

        if existing_assessment:
            return existing_assessment

        raise LearningAIError(
            "Assessment generation is already in progress "
            "or requires recovery."
        )

    job.refresh_from_db()
    job.attempt_count += 1
    job.save(update_fields=[
        "attempt_count",
        "updated_at",
    ])

    try:

        system_prompt, user_prompt = (
            build_initial_assessment_prompt(language)
        )

        # Generate assessment using Groq
        data = generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=True,
        )

        # Validate generated questions
        data = validate_assessment(data, language)

        # Save assessment and questions together
        with transaction.atomic():

            assessment, created = (
                Assessment.objects.get_or_create(
                    enrollment=enrollment,
                    assessment_type=(
                        Assessment.AssessmentType.INITIAL
                    ),
                    day_number=0,
                    defaults={
                        "title": data["title"],
                        "total_questions": INITIAL_QUESTION_COUNT,
                    },
                )
            )

            if created:

                question_objects = []

                for index, question in enumerate(
                    data["questions"],
                    start=1,
                ):

                    question_objects.append(
                        Question(
                            assessment=assessment,
                            question_type=question["question_type"],
                            topic=question["topic"],
                            difficulty=question["difficulty"],
                            question_text=question["question_text"],
                            options=question["options"],
                            correct_answer=question["correct_answer"],
                            explanation=question["explanation"],
                            marks=question["marks"],
                            order=index,
                        )
                    )

                Question.objects.bulk_create(
                    question_objects
                )

            job.status = AIGenerationJob.Status.COMPLETED
            job.response_data = data
            job.completed_at = timezone.now()
            job.save()

        return assessment

    except Exception as error:

        logger.exception(
            "Initial assessment generation failed."
        )

        job.status = AIGenerationJob.Status.FAILED

        job.error_message = (
            str(error)
            if isinstance(error, LearningAIError)
            else "Unexpected assessment generation error."
        )

        job.completed_at = timezone.now()
        job.save()

        if isinstance(error, LearningAIError):
            raise

        raise LearningAIError(
            "Unable to generate assessment. "
            "Please try again."
        ) from error