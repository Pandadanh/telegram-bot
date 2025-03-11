import re
import psycopg2
import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle

def get_credentials():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

DB_CONFIG = {
    "host": "localhost",
    "database": "basso",
    "user": "basso",
    "password": "123123",
    "port": 5432
}

def extract_transaction_info(text):
    """
    Trích xuất số tiền, loại giao dịch (+/-), và ghi chú từ nội dung email.
    """
    # Xác định giao dịch là tăng hay giảm
    transaction_type = None
    if "vừa tăng" in text.lower():
        transaction_type = "+"
    elif "vừa giảm" in text.lower():
        transaction_type = "-"
    
    # Trích xuất số tiền
    match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s?(VND|USD|đ)', text)
    price = 0.0
    if match:
        price = float(match.group(1).replace(".", "").replace(",", "")) # Chuyển về số
    
    # Trích xuất ghi chú
    note = None
    match_note = re.search(r'Mô tả:\s*(.+)', text)
    if match_note:
        note = match_note.group(1).strip()
    
    # Đặt dấu + hoặc - trước số tiền
    if transaction_type == "-":
        price = -price
    
    return price, note

def save_to_db(email_id, subject, snippet, price, note):
    """
    Lưu dữ liệu vào bảng Email trong PostgreSQL.
    """
    print(f"📧 Email: {email_id} | Số tiền: {price} | Ghi chú: {note}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        month = datetime.datetime.now().month
        
        query = """
        INSERT INTO "Email" ("emailId", "expense", "createdAt", "month", "price", "note") 
        VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
        ON CONFLICT ("emailId") DO NOTHING;
        """
        
        cursor.execute(query, (email_id, subject, month, price, note))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Đã lưu email {email_id} vào DB.")
    except Exception as e:
        print(f"❌ Lỗi khi lưu vào DB: {e}")

def fetch_unread_emails():
    """
    Lấy email chưa đọc trong 3 ngày gần nhất từ Gmail.
    """
    creds = get_credentials()
    if not creds:
        print("Không thể lấy credentials. Thoát chương trình.")
        return []

    try:
        service = build('gmail', 'v1', credentials=creds)
        today = datetime.date.today()
        three_days_ago = today - datetime.timedelta(days=3)
        query = f"from:support@timo.vn after:{three_days_ago.strftime('%Y/%m/%d')} before:{today.strftime('%Y/%m/%d')}"
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages:
            print("Không có email chưa đọc nào trong khoảng thời gian này.")
            return []

        for msg in messages:
            msg_id = msg['id']
            email_detail = service.users().messages().get(userId='me', id=msg_id).execute()
            headers = email_detail.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            snippet = email_detail.get("snippet", "")
            content = subject + " " + snippet  # Kết hợp tiêu đề và nội dung tóm tắt

            # Trích xuất số tiền, loại giao dịch và ghi chú
            price, note = extract_transaction_info(content)

            # Lưu vào DB
            save_to_db(msg_id, subject, snippet, price, note)

    except Exception as e:
        print(f"❌ Lỗi khi lấy email: {e}")

if __name__ == "__main__":
    fetch_unread_emails()
