from flask import Flask, render_template, request, jsonify
from functions import users, courses, enrollments, grades
import threading, requests
from flask import jsonify
from config import SOURCE_DOMAIN, HEADERS_SRC


app = Flask(__name__)
transfer_logs = {}

@app.route("/")
def dashboard():
    course_list = courses.export_courses()
    if "error" in course_list:
        return jsonify({
            'error': course_list.get('error'),
            'status_code': course_list.get('status_code')
        })
    return render_template("dashboard.html", courses=course_list, logs=transfer_logs)

@app.route("/fetch_courses")
def fetch_courses():
    """Fetch courses between start and end ID (for AJAX)."""
    try:
        start_id = int(request.args.get("start_id", 0))
        end_id = int(request.args.get("end_id", 0))
        course = courses.export_courses(start_id, end_id)
        return jsonify(course)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/transfer", methods=["POST"])
def transfer():
    selected = request.json.get("courses", [])
    thread = threading.Thread(target=run_transfer, args=(selected,))
    thread.start()
    return jsonify({"status": "started"})

def run_transfer(course_ids):
    for cid in course_ids:
        log = {"status": "processing", "details": []}
        transfer_logs[cid] = log
        try:
            # 1. Export course details
            log["details"].append(f"Fetching course details for ID {cid}...")
            course_data_list = courses.export_courses(int(cid), int(cid))

            if not course_data_list:
                log["status"] = "error"
                log["details"].append(f"No course found with ID {cid}. Skipping.")
                continue

            # course_data = [c for c in courses.export_courses() if c["id"] == int(cid)][0]
            course_data = course_data_list[0]
            
            # 2. Import course to target Canvas
            new_course = courses.import_course(course_data)
            log["details"].append(f"Course '{course_data['name']}' imported.")

            # 3. Transfer Course Content (modules, assignments, quizzes, pages, files)
            log["details"].append("Exporting and importing course content...")
            import_result = courses.transfer_course_content(cid, new_course["id"])
            if import_result:
                log["details"].append("Course content imported successfully.")
            else:
                log["details"].append("Failed to transfer course content.")

            # 4. Export enrollments
            enrolls = enrollments.export_enrollments(cid)

            print('Enrollment to Target Started')
            for e in enrolls:
                email = e["user"].get("login_id") or e["user"].get("email")
                enrollmentType = e["type"] or e["role"]
                src_user_id = e["user_id"]
                
                if not email:
                    print(f"Skipping enrollment — no email found for user {email}")
                    continue

                if email:
                    print('email', email)
                    new_student_enrollment = enrollments.import_enrollment_by_email(new_course["id"], email, enrollmentType)

                    # 3.1 Transfer Grades for each enrolled Student
                    if "error" not in new_student_enrollment:
                        user = new_student_enrollment.get("user", {})
                        user_id = user.get("id")
                        email = user.get("login_id") or user.get("email")

                        if not user_id:
                            print(f"Skipping grade transfer for user (no ID): {email}")
                            continue

                        print(f"Transferring grades for {email} (User ID: {user_id})...")
                        grades.transfer_user_grades(cid, new_course["id"], user_id, src_user_id)
                    else:
                        print(f"Skipping grade transfer — enrollment failed for {email}: {new_student_enrollment['error']}")

                    print('*'*50)

            log["details"].append(f"{len(enrolls)} students enrolled.")
            log["details"].append("Grade transfer completed for all enrolled users.")
            print('End of Enrollment')

            # # 4. Transfer Grades for each enrolled Student
            # print('-*' * 50)
            # print('Starting Grade Transfer...')
            # for e in enrolls:
            #     print('e', e)
            #     user = e.get("user", {})
            #     user_id = user.get("id")
            #     email = user.get("login_id") or user.get("email")

            #     if not user_id:
            #         print(f"Skipping grade transfer for user (no ID): {email}")
            #         continue

            #     print(f"Transferring grades for {email} (User ID: {user_id})...")
            #     grades.transfer_user_grades(cid, new_course["id"], user_id)
            #     print('-' * 50)

            # log["details"].append("Grade transfer completed for all enrolled users.")

            log["status"] = "success"
        except Exception as ex:
            log["status"] = "error"
            log["details"].append(str(ex))

@app.route("/fetch_students/<int:course_id>")
def fetch_students(course_id):
    """
    Fetches and displays all students and teachers in a Canvas course.
    """
    enrollments_url = f"{SOURCE_DOMAIN}/api/v1/courses/{course_id}/enrollments?per_page=100"
    response = requests.get(enrollments_url, headers=HEADERS_SRC)

    if response.status_code != 200:
        return f"<h3>Error fetching enrollments for course {course_id}</h3><pre>{response.text}</pre>", 500

    enrollments = response.json()
    students = [e["user"].get('login_id') for e in enrollments if e["type"] == "StudentEnrollment"]
    teachers = [e["user"].get('login_id') for e in enrollments if e["type"] == "TeacherEnrollment"]
    designer = [e["user"].get('login_id') for e in enrollments if e["type"] == "DesignerEnrollment"]
    tas = [e["user"].get('login_id') for e in enrollments if e["type"] == "TaEnrollment"]
    observers = [e["user"].get('login_id') for e in enrollments if e["type"] == "ObserverEnrollment"]

    return render_template("students_list.html", course_id=course_id, students=students, teachers=teachers, designer=designer, tas=tas, observers=observers)

if __name__ == "__main__":
    app.run(debug=True)
