from dotenv import load_dotenv
import os

load_dotenv()

# Origin (learn)
SOURCE_DOMAIN = "https://learn.moringaschool.com"
SOURCE_TOKEN  = os.getenv('SOURCE_TOKEN')

# target (lms)
TARGET_DOMAIN = "https://lms.moringaschool.com"
TARGET_TOKEN  = os.getenv('TARGET_TOKEN')

# headers
HEADERS_SRC = {"Authorization": f"Bearer {SOURCE_TOKEN}"}
HEADERS_DST = {"Authorization": f"Bearer {TARGET_TOKEN}"}
