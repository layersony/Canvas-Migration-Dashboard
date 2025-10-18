from config import *
from functions.utils import paginate, put
import requests

def get_assignments(course_id, headers):
    """Fetch all assignments (including quizzes) for a given course."""
    url = f"{course_id}/assignments"
    domain = SOURCE_DOMAIN if headers == HEADERS_SRC else TARGET_DOMAIN
    full_url = f"{domain}/api/v1/courses/{url}"
    return paginate(full_url, headers)

def get_student_submission(course_id, assignment_id, user_id):
    """Fetch a student's submission (grade) for a specific assignment."""
    print(f'Fetching Student Submission For {assignment_id}')
    url = f"{SOURCE_DOMAIN}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}"
    res = requests.get(url, headers=HEADERS_SRC)
    if res.status_code == 200:
        return res.json()
    return None

def grade_exists(course_id, assignment_id, user_id):
    """Check if a grade already exists in the target Canvas instance."""
    url = f"{TARGET_DOMAIN}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}"
    res = requests.get(url, headers=HEADERS_DST)
    if res.status_code == 200:
        submission = res.json()
        grade = submission.get("score") or submission.get("grade")
        return grade is not None
    return False

def import_grade(course_id, assignment_id, user_id, score):
    """Push a grade to the target Canvas course (if not already graded)."""
    if grade_exists(course_id, assignment_id, user_id):
        print(f"Skipping existing grade for assignment {assignment_id}, user {user_id}")
        return {"status": "skipped"}

    url = f"{TARGET_DOMAIN}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}"
    data = {"submission[posted_grade]": score}
    res = put(url, HEADERS_DST, data)

    if res and res.status_code in (200, 201):
        print(f"Imported grade for user {user_id} on assignment {assignment_id}")
        return {"status": "imported", "response": res.json()}
    else:
        print(f"Failed to import grade: {res.status_code} - {res.text if res else 'No response'}")
        return {"status": "failed", "error": res.text if res else "No response"}

def build_assignment_mapping(source_course_id, target_course_id):
    """
    Match source and target assignments by name.
    Returns {source_assignment_id: target_assignment_id}
    """
    print("Building assignment ID mapping...")

    source_assignments = get_assignments(source_course_id, HEADERS_SRC)
    target_assignments = get_assignments(target_course_id, HEADERS_DST)

    mapping = {}
    for s in source_assignments:
        for t in target_assignments:
            if s["name"].strip().lower() == t["name"].strip().lower():
                mapping[s["id"]] = t["id"]
                break

    print(f"Found {len(mapping)} matching assignments.")
    return mapping

def transfer_user_grades(source_course_id, target_course_id, user_id, src_user_id):
    """
    Transfer all available grades (assignments, quizzes, attendance) 
    for a specific student using mapped assignment IDs.
    """
    print(f"\n Transferring all grades for User {user_id}...")

    assignment_map = build_assignment_mapping(source_course_id, target_course_id)
    if not assignment_map:
        print("[ERROR] Could not map assignments between source and target.")
        return

    imported, skipped = 0, 0

    for source_assignment_id, target_assignment_id in assignment_map.items():

        submission = get_student_submission(source_course_id, source_assignment_id, src_user_id)
        
        if not submission:
            continue

        score = submission.get("score")
          
        if score is None:
            continue
        
        res = import_grade(target_course_id, target_assignment_id, user_id, score)

        if not res:
            print("No result returned, continuing...")
            skipped += 1
            continue

        if res["status"] == "imported":
            imported += 1
            print('Imported Successfully')
        else:
            skipped += 1

        print('`'*40)

    print(f"\n Grade transfer complete for user {user_id}")
    print(f"   → Imported: {imported}")
    print(f"   → Skipped: {skipped}")
