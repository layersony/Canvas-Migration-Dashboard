from config import *
from functions.utils import paginate, post
import requests

def export_enrollments(course_id):
    """
    Exports all student enrollments (with user emails) from the source Canvas course.
    """
    print('Getting Enrollments')
    url = f"{SOURCE_DOMAIN}/api/v1/courses/{course_id}/enrollments?include[]=email"
    return paginate(url, HEADERS_SRC)

def get_user_by_email(email):
    """
    Fetches a user from the target Canvas by login email.
    Returns the user object if found, else None.
    """
    url = f"{TARGET_DOMAIN}/api/v1/accounts/1/users?search_term={email}"
    res = requests.get(url, headers=HEADERS_DST)
    
    if res.status_code != 200:
        print(f"Failed to search for {email}: {res.status_code}")
        return None
    
    users = res.json()
    for u in users:
        # Canvas user emails are usually in 'login_id' or 'email'
        if u.get("login_id", "").lower() == email.lower() or u.get("email", "").lower() == email.lower():
            return u

    print(f"No user found in target Canvas for email: {email}")
    return None

def import_enrollment_by_email(course_id, email, enrollmentType):
    """
    Enrolls a User into the target course using their email.
    - Looks up user by email in target instance.
    - Skips if already enrolled.
    """
    print('Fetching User in Target')
    user = get_user_by_email(email)
    if not user:
        print(f"Skipping enrollment — user not found for email: {email}")
        return {"error": "user not found"}

    user_id = user["id"]

    # Check existing enrollments
    print(f'Checking Existing Enrollment')
    check_url = f"{TARGET_DOMAIN}/api/v1/courses/{course_id}/enrollments?user_id={user_id}"
    check_res = requests.get(check_url, headers=HEADERS_DST)

    if check_res.status_code == 200:
        existing = check_res.json()
        if existing and any(e["user_id"] == user_id for e in existing):
            print(f"User {email} (ID {user_id}) already enrolled in course {course_id}. Skipping.")
            return existing[0]

    # Enroll if not found
    print('Enrolling Student')
    enroll_url = f"{TARGET_DOMAIN}/api/v1/courses/{course_id}/enrollments"
    data = {
        "enrollment[user_id]": user_id,
        "enrollment[type]": enrollmentType,
        "enrollment[enrollment_state]": "active",
        "enrollment[notify]": False
    }

    enroll_res = requests.post(enroll_url, headers=HEADERS_DST, data=data)

    if enroll_res.status_code in (200, 201):
        enrollment = enroll_res.json()
        print(f"Enrolled {email} (ID {user_id}) into course {course_id} - Enrollment Type {enrollmentType}")
        return enrollment
    else:
        print(f"Failed to enroll {email}: {enroll_res.status_code} - {enroll_res.text}")
        return None
    
