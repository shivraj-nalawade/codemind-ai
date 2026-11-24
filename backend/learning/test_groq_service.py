import json

from learning.services.groq_service import (
    generate_response,
    LearningAIError,
)


def main():

    system_prompt = """
    You are an expert programming tutor.
    Generate accurate programming assessment questions.
    Return only valid JSON.
    """

    user_prompt = """
    Generate 3 basic Python multiple-choice questions.

    Follow this JSON structure:

    {
        "language": "Python",
        "questions": [
            {
                "id": 1,
                "topic": "Variables",
                "difficulty": "basic",
                "question": "Question text",
                "options": [
                    "Option A",
                    "Option B",
                    "Option C",
                    "Option D"
                ],
                "correct_answer": "Option A",
                "explanation": "Explain the correct answer"
            }
        ]
    }

    Generate exactly 3 questions.
    """

    try:
        result = generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=True
        )

        print("\nGroq Service Test Successful!")
        print("\nGenerated Assessment:\n")

        print(json.dumps(result, indent=4))

        print("\nResponse Type:", type(result).__name__)
        print("Language:", result["language"])
        print("Total Questions:", len(result["questions"]))

    except LearningAIError as error:
        print("Learning AI Error:", error)


if __name__ == "__main__":
    main()