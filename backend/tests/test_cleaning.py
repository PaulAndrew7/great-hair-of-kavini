from app.cleaning import (SkillNormalizer, build_courses, clean_description, flag_shared_descriptions, make_course_id,
                          parse_difficulty, parse_rating, parse_skill_list, summarize)

GOALS = {
    "skills": {"Python": {"abbr": "Py", "title_patterns": ["^python\\b"]},
               "Statistics": {"abbr": "St", "title_patterns": ["\\bstatistics\\b"]}},
    "dependencies": [],
    "tracks": {},
}


def row(**kw):
    base = {"title": "Course", "Organization": "Org", "Skills": "[]", "Description": "About things.",
            "Level": "Beginner level", "rating": "4.5", "num_reviews": "10", "enrolled": "1,234",
            "Schedule": "", "Modules/Courses": "4 modules", "URL": "https://www.coursera.org/learn/x",
            "Instructor": "A. Person", "Satisfaction Rate": "", "Unnamed: 0": "0"}
    base.update(kw)
    return base


def test_skill_list_is_parsed_safely():
    assert parse_skill_list("['Python', 'SQL']") == ["Python", "SQL"]
    assert parse_skill_list('["Python"]') == ["Python"]
    assert parse_skill_list("__import__('os').system('echo hacked')") == []
    assert parse_skill_list("not a list") == []
    assert parse_skill_list(None) == []


def test_activity_counts_glued_by_scraper_are_removed():
    text = "Learn npm supply chains. 2 videos1 assignment 4 videos9 readings4 quizzes Next module text."
    assert clean_description(text) == "Learn npm supply chains. Next module text."


def test_missing_values_stay_missing():
    assert parse_rating("Rating not found") is None
    assert parse_rating("7.2") is None  # out of range
    assert parse_difficulty("") == "Unknown"
    assert parse_difficulty("Intermediate level") == "Intermediate"


def test_course_ids_are_stable_and_url_based():
    a = make_course_id("https://www.coursera.org/learn/X/", "Org", "T")
    b = make_course_id("https://www.coursera.org/learn/x", "Other", "Different title")
    assert a == b and a.startswith("c") and len(a) == 11


def test_aliases_merge_but_related_concepts_stay_separate():
    norm = SkillNormalizer({"Python": ["Python Programming"]}, ["Computer Programming", "data analysis", "Data Analysis", "Data Analysis"])
    assert norm.normalize_list(["Python Programming", "python", "Computer Programming"]) == ["Python", "Computer Programming"]
    assert norm.canonical("data analysis") == "Data Analysis"


def test_build_courses_handles_duplicates_missing_fields_and_evidence():
    rows = [
        row(title="Python for Everybody", Skills="['Programming']", URL="https://www.coursera.org/learn/py"),
        row(title="Python for Everybody", Skills="['Programming']", URL="https://www.coursera.org/learn/py"),  # exact duplicate
        row(title="Intro Stats", Skills="['Statistics']", Description="", rating="Rating not found",
            URL="https://www.coursera.org/learn/stats", Level=""),
    ]
    courses, report = build_courses(rows, {}, GOALS)
    assert report["dropped"]["exact_duplicate"] == 1
    by_title = {c["title"]: c for c in courses}
    stats = by_title["Intro Stats"]
    assert stats["description_quality"] == "Missing" and stats["rating"] is None and stats["difficulty"] == "Unknown"
    assert stats["track_skills"] == [{"skill": "Statistics", "source": "catalog tag", "label": "Statistics"}]
    py = by_title["Python for Everybody"]
    assert py["track_skills"][0]["source"] == "course title"  # 'Programming' tag is not Python


def test_shared_description_is_flagged_but_the_program_keeps_it():
    shared = "This specialization covers algebra, calculus and statistics in depth for learners."
    courses = [
        {"title": "Maths Specialization", "description": shared, "course_type": "Specialization",
         "description_quality": "Unreviewed", "quality_notes": []},
        {"title": "Algebra", "description": shared, "course_type": "Course",
         "description_quality": "Unreviewed", "quality_notes": []},
    ]
    flag_shared_descriptions(courses)
    assert courses[0]["description_quality"] == "Unreviewed"
    assert courses[1]["description_quality"] == "Suspect" and "Maths Specialization" in courses[1]["quality_notes"][0]


def test_summary_cuts_at_sentence_boundary():
    text = "First sentence here. " * 40
    out = summarize(text, 100)
    assert out.endswith(".") and len(out) <= 100
