import asyncio
from app.email_sender import send_email
from app.settings import settings

async def test():
    try:
        send_email(
            to_email="Narutousomaki741@gmail.com",  # send to yourself for testing
            subject="Test from Maritime Jobs",
            body="This is a test email.",
            reply_to="askdaoudi@gmail.com",
            attachment_data=b"dummy resume content",
            attachment_name="test.txt",
        )
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())