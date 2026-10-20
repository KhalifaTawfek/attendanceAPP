from prometheus_client import Counter

attendance_submissions = Counter(
    "attendance_submissions_total", "Attendance submissions received", ["late"]
)
attendance_reviews = Counter(
    "attendance_reviews_total", "Attendance reviews performed by admins", ["status"]
)
login_attempts = Counter("login_attempts_total", "Login attempts", ["result"])
