from django.db import models
from django.conf import settings
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
)


# ==========================================
# 1. Enrollment Model
# ==========================================

class Enrollment(models.Model):

    class Language(models.TextChoices):
        CPP = "cpp", "C++"
        PYTHON = "python", "Python"
        JAVASCRIPT = "javascript", "JavaScript"
        JAVA = "java", "Java"
        SQL = "sql", "SQL"

    class SkillLevel(models.TextChoices):
        UNASSESSED = "unassessed", "Not Assessed"
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class Status(models.TextChoices):
        PENDING = "pending", "Assessment Pending"
        ACTIVE = "active", "Learning in Progress"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_enrollments"
    )

    language = models.CharField(
        max_length=20,
        choices=Language.choices
    )

    skill_level = models.CharField(
        max_length=20,
        choices=SkillLevel.choices,
        default=SkillLevel.UNASSESSED
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    current_day = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(30)
        ]
    )

    strengths = models.JSONField(
        default=list,
        blank=True
    )

    weaknesses = models.JSONField(
        default=list,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "language"],
                name="unique_user_language_enrollment"
            )
        ]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.get_language_display()}"
        )


# ==========================================
# 2. Assessment Model
# ==========================================

class Assessment(models.Model):

    class AssessmentType(models.TextChoices):
        INITIAL = "initial", "Initial Assessment"
        DAILY = "daily", "Daily Assessment"

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="assessments"
    )

    assessment_type = models.CharField(
        max_length=20,
        choices=AssessmentType.choices
    )

    day_number = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(30)]
    )

    title = models.CharField(max_length=200)

    total_questions = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1)]
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "enrollment",
                    "assessment_type",
                    "day_number"
                ],
                name="unique_learning_assessment"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        assessment_type="initial",
                        day_number=0
                    )
                    |
                    models.Q(
                        assessment_type="daily",
                        day_number__gte=1,
                        day_number__lte=30,
                        total_questions=5
                    )
                ),
                name="valid_learning_assessment"
            )
        ]

    def __str__(self):
        return self.title


# ==========================================
# 3. Question Model
# ==========================================

class Question(models.Model):

    class Difficulty(models.TextChoices):
        BASIC = "basic", "Basic"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class QuestionType(models.TextChoices):
        MCQ = "mcq", "Multiple Choice"
        CODING = "coding", "Coding Question"
        THEORY = "theory", "Theory Question"

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.MCQ
    )

    topic = models.CharField(max_length=150)

    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices
    )

    question_text = models.TextField()

    options = models.JSONField(
        default=list,
        blank=True
    )

    correct_answer = models.TextField()

    explanation = models.TextField(blank=True)

    marks = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    order = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    class Meta:
        ordering = ["order"]

        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "order"],
                name="unique_assessment_question_order"
            )
        ]

    def __str__(self):
        return f"{self.topic} - Question {self.order}"



# ==========================================
# 4. Learning Day Model
# ==========================================

class LearningDay(models.Model):

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="learning_days"
    )

    day_number = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(30)
        ]
    )

    title = models.CharField(max_length=200)

    topic = models.CharField(max_length=150)

    difficulty = models.CharField(
        max_length=20,
        choices=Question.Difficulty.choices
    )

    learning_objectives = models.JSONField(
        default=list,
        blank=True
    )

    explanation = models.TextField(blank=True)

    code_examples = models.JSONField(
        default=list,
        blank=True
    )

    practical_tasks = models.JSONField(
        default=list,
        blank=True
    )

    estimated_minutes = models.PositiveIntegerField(
        default=60
    )

    is_content_generated = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["day_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "day_number"],
                name="unique_enrollment_learning_day"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    day_number__gte=1,
                    day_number__lte=30
                ),
                name="valid_learning_day_number"
            )
        ]

    def __str__(self):
        return f"Day {self.day_number} - {self.title}"


# ==========================================
# 5. Assessment Attempt Model
# ==========================================

class AssessmentAttempt(models.Model):

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        EVALUATING = "evaluating", "Evaluating"
        EVALUATED = "evaluated", "Evaluated"
        FAILED = "failed", "Evaluation Failed"

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="attempts"
    )

    attempt_number = models.PositiveIntegerField(
        default=1
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS
    )

    total_marks = models.PositiveIntegerField(
        default=0
    )

    obtained_marks = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)]
    )

    percentage = models.FloatField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )

    passed = models.BooleanField(default=False)

    ai_feedback = models.TextField(blank=True)

    strengths = models.JSONField(
        default=list,
        blank=True
    )

    weaknesses = models.JSONField(
        default=list,
        blank=True
    )

    recommendations = models.JSONField(
        default=list,
        blank=True
    )

    started_at = models.DateTimeField(
        auto_now_add=True
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    evaluated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "attempt_number"],
                name="unique_assessment_attempt"
            )
        ]

    def __str__(self):
        return (
            f"{self.assessment.title} - "
            f"Attempt {self.attempt_number}"
        )


# ==========================================
# 6. User Answer Model
# ==========================================

class UserAnswer(models.Model):

    attempt = models.ForeignKey(
        AssessmentAttempt,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="user_answers"
    )

    submitted_answer = models.TextField(blank=True)

    is_correct = models.BooleanField(
        null=True,
        blank=True
    )

    marks_awarded = models.FloatField(
        default=0,
        validators=[MinValueValidator(0)]
    )

    ai_feedback = models.TextField(blank=True)

    is_evaluated = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_attempt_question_answer"
            )
        ]

    def __str__(self):
        return (
            f"Attempt {self.attempt_id} - "
            f"Question {self.question_id}"
        )


# ==========================================
# 7. Day Progress Model
# ==========================================

class DayProgress(models.Model):

    class Status(models.TextChoices):
        LOCKED = "locked", "Locked"
        UNLOCKED = "unlocked", "Unlocked"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    learning_day = models.OneToOneField(
        LearningDay,
        on_delete=models.CASCADE,
        related_name="progress"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LOCKED
    )

    lesson_completed = models.BooleanField(
        default=False
    )

    practical_completed = models.BooleanField(
        default=False
    )

    assessment_completed = models.BooleanField(
        default=False
    )

    best_score = models.FloatField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )

    unlocked_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return (
            f"{self.learning_day} - "
            f"{self.get_status_display()}"
        )


# ==========================================
# 8. Topic Mastery Model
# ==========================================

class TopicMastery(models.Model):

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="topic_masteries"
    )

    topic = models.CharField(max_length=150)

    initial_score = models.FloatField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )

    mastery_score = models.FloatField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )

    total_questions = models.PositiveIntegerField(
        default=0
    )

    correct_answers = models.PositiveIntegerField(
        default=0
    )

    recommended_difficulty = models.CharField(
        max_length=20,
        choices=Question.Difficulty.choices,
        default=Question.Difficulty.BASIC
    )

    last_practiced_at = models.DateTimeField(
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "topic"],
                name="unique_enrollment_topic_mastery"
            )
        ]

    @property
    def improvement(self):

        if self.initial_score is None:
            return None

        return round(
            self.mastery_score - self.initial_score,
            2
        )

    def __str__(self):
        return f"{self.topic} - {self.mastery_score}%"



# ==========================================
# 9. Learning Activity Model
# ==========================================

class LearningActivity(models.Model):

    class ActivityType(models.TextChoices):
        LESSON = "lesson", "Lesson Completed"
        PRACTICAL = "practical", "Practical Completed"
        ASSESSMENT = "assessment", "Assessment Completed"
        DAY_COMPLETED = "day_completed", "Day Completed"

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="activities"
    )

    learning_day = models.ForeignKey(
        LearningDay,
        on_delete=models.CASCADE,
        related_name="activities",
        null=True,
        blank=True
    )

    activity_type = models.CharField(
        max_length=30,
        choices=ActivityType.choices
    )

    description = models.TextField(blank=True)

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["enrollment", "created_at"]
            )
        ]

    def __str__(self):
        return (
            f"{self.enrollment} - "
            f"{self.get_activity_type_display()}"
        )



# ==========================================
# 10. AI Generation Job Model
# ==========================================

class AIGenerationJob(models.Model):

    class JobType(models.TextChoices):
        INITIAL_ASSESSMENT = (
            "initial_assessment",
            "Initial Assessment"
        )

        ASSESSMENT_EVALUATION = (
            "assessment_evaluation",
            "Assessment Evaluation"
        )

        ROADMAP = (
            "roadmap",
            "Roadmap Generation"
        )

        DAILY_LESSON = (
            "daily_lesson",
            "Daily Lesson Generation"
        )

        DAILY_ASSESSMENT = (
            "daily_assessment",
            "Daily Assessment Generation"
        )

        ROADMAP_ADAPTATION = (
            "roadmap_adaptation",
            "Roadmap Adaptation"
        )

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="ai_jobs"
    )

    job_type = models.CharField(
        max_length=40,
        choices=JobType.choices
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    idempotency_key = models.CharField(
        max_length=150,
        unique=True
    )

    request_data = models.JSONField(
        default=dict,
        blank=True
    )

    response_data = models.JSONField(
        default=dict,
        blank=True
    )

    attempt_count = models.PositiveIntegerField(
        default=0
    )

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["status", "created_at"]
            )
        ]

    def __str__(self):
        return (
            f"{self.get_job_type_display()} - "
            f"{self.get_status_display()}"
        )