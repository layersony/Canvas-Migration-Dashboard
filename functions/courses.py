from config import *
from functions.utils import paginate, post
import requests, time

def export_courses(start_id=0, end_id=0):
    """
    Loop through course IDs from start_id to end_id and fetch
    their details individually from the source Canvas instance.
    Skips invalid or deleted course IDs.
    """
    courses = []
    for course_id in range(start_id, end_id + 1):
        url = f"{SOURCE_DOMAIN}/api/v1/courses/{course_id}"
        res = requests.get(url, headers=HEADERS_SRC)

        if res.status_code == 200:
            course_data = res.json()
            # skip deleted or unpublished courses if needed
            if course_data.get("workflow_state") not in ("deleted", None):
                courses.append(course_data)
                print(f"Found course {course_data['name']} (ID: {course_id})")
        elif res.status_code == 404:
            print(f"No course found with ID {course_id}")
        else:
            print(f"Error fetching course {course_id}: {res.status_code} - {res.text}")

        time.sleep(0.1)  # prevent API rate limit

    print(f"Total valid courses found: {len(courses)}")
    return courses

def import_course(course):
    """
    Check if a course already exists in the target Canvas LMS by course_code or name.
    If found, reuse it. Otherwise, create a new one.
    """
    course_code = course.get("course_code") or f"Course_{course['id']}"
    name = course.get("name", f"Unnamed Course {course['id']}")
    
    # Check if course already exists in the target LMS
    check_url = f"{TARGET_DOMAIN}/api/v1/accounts/1/courses?search_term={course_code}"
    res = requests.get(check_url, headers=HEADERS_DST)

    if res.status_code == 200:
        existing_courses = res.json()
        for c in existing_courses:
            if c.get("course_code") == course_code or c.get("name") == name:
                print(f"Course already exists on target: '{name}' (ID: {c['id']})")
                return c  # Return the existing course instead of creating a new one

    # Create new course if not found
    create_url = f"{TARGET_DOMAIN}/api/v1/accounts/1/courses"
    data = {
        "course[name]": name,
        "course[course_code]": course_code,
        "course[is_public]": False,
    }

    create_res = requests.post(create_url, headers=HEADERS_DST, data=data)
    
    if create_res.status_code in (200, 201):
        new_course = create_res.json()
        print(f"Created new course on target: '{name}' (ID: {new_course['id']})")
        return new_course
    else:
        print(f"Failed to create course '{name}': {create_res.status_code} - {create_res.text}")
        return None

def publish_course(course_id):
    """
    Publishes a Canvas course by setting workflow_state to 'available'
    """
    url = f"{TARGET_DOMAIN}/api/v1/courses/{course_id}"
    print(url)

    data = {
        "course[workflow_state]": "available"
    }

    res = requests.put(url, headers=HEADERS_DST, data=data)
    if res.status_code in (200, 201):
        print(f"Course ID {course_id} published successfully.")
        return res.json()
    else:
        print(f"Failed to publish course ID {course_id}: {res.status_code} - {res.text}")
        return None
    
# ---------------------------
# COURSE CONTENT EXPORT/IMPORT
# ---------------------------

def export_course_content(course_id):
    """
    Export course content from source Canvas as a Common Cartridge file.
    """

    url = f"{SOURCE_DOMAIN}/api/v1/courses/{course_id}/content_exports"
    data = {"export_type": "common_cartridge"}
    res = requests.post(url, headers=HEADERS_SRC, data=data)

    if res.status_code not in (200, 201):
        print(f"Failed to start export for course {course_id}: {res.text}")
        return None

    export_job = res.json()
    export_id = export_job["id"]

    # Poll for completion
    while True:
        status_url = f"{SOURCE_DOMAIN}/api/v1/courses/{course_id}/content_exports/{export_id}"
        status_res = requests.get(status_url, headers=HEADERS_SRC).json()

        if status_res["workflow_state"] == "exported":
            file_url = status_res["attachment"]["url"]
            print(f"Export ready: {file_url}")
            return file_url
        elif status_res["workflow_state"] in ("failed", "cancelled"):
            print(f"Export failed: {status_res}")
            return None
        time.sleep(5)

def download_export_file(file_url, filename):
    """Download the exported .imscc file."""
    res = requests.get(file_url)

    if res.status_code == 200:
        with open(filename, "wb") as f:
            f.write(res.content)
        print(f"File saved locally: {filename}")
        return filename
    
    print(f"Failed to download export file: {res.status_code}")
    return None

def import_course_content(target_course_id, file_url):
    """Import downloaded .imscc file into target Canvas course."""
    import_url = f"{TARGET_DOMAIN}/api/v1/courses/{target_course_id}/content_migrations"

    try:
        data = {
            "import_type": "common_cartridge_importer",
            "select": "all",
            "selective_import": False,
            "migration_type": "common_cartridge_importer",
            "settings[file_url]": file_url,
        }

        clean_headers = {
            k: v for k, v in HEADERS_DST.items() if k.lower() != "content-type"
        }

        res = requests.post(import_url, headers=clean_headers, data=data)

        if res.status_code not in (200, 201):
            print(f"[ERROR] Failed to import content for course {target_course_id}")
            print(f"→ Status code: {res.status_code}")
            print(f"→ URL: {import_url}")
            print(f"→ Response headers: {res.headers}")

            try:
                print(f"→ Response JSON: {res.json()}")
            except Exception:
                print(f"→ Response text: {res.text}")
            return None

        import_job = res.json()
        print(f"Import started for course {target_course_id}")
        print(f"→ Import ID: {import_job.get('id')}")
        print(f"→ Progress URL: {import_job.get('progress_url')}")
        return import_job
    
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")

def transfer_course_content(source_course_id, target_course_id):
    """
    Full export → import workflow.
    """

    print(f"Checking if target course {target_course_id} already has content...")
    
    target_modules_url = f"{TARGET_DOMAIN}/api/v1/courses/{target_course_id}/modules"
    tar_res = requests.get(target_modules_url, headers=HEADERS_DST)

    if tar_res.status_code == 200:
        modules = tar_res.json()
        if modules:
            print(f"Target course {target_course_id} already has content. Skipping import.")
            return {"status": "skipped", "reason": "content already exists"}
    else:
        print(f"Failed to check target course modules: {tar_res.status_code} - {tar_res.text}")


    print('Starting to export')
    file_url = export_course_content(source_course_id)

    if not file_url:
        return None

    print('file_url', file_url)

    print('Start import file')
    import_job = import_course_content(target_course_id, file_url)

    return import_job
