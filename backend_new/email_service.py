import smtplib
from email.mime.text import MIMEText

def send_alert_email(to_email, student_name, risk_score, course, instructor):
    sender_email = "dhanyaprabhu05@gmail.com"
    sender_password = "xvgmivgvmmaoekoc"

    msg = MIMEText(
        f"""
        🚨 HIGH RISK STUDENT ALERT 🚨

        Instructor Responsible: {instructor}

        Student: {student_name}
        Course : {course}
        Risk Score: {risk_score}

        Please review immediately in the dashboard.
        """
    )

    msg["Subject"] = f"[ALERT for {instructor}] High Risk Student: {student_name}"
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print("Email alert sent successfully.")
    except Exception as e:
        print("Email sending failed:", str(e))

