import os
import logging
import asyncio
import psycopg2
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import requests
import json
import google.generativeai as genai
import pytesseract
from PIL import Image
import io
from googlesearch import search
import aiohttp
from bs4 import BeautifulSoup
import re
import base64
import cloudinary
import cloudinary.uploader
import cloudinary.api
import uuid

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Get environment variables
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Database configuration
DB_CONFIG = {
    "host": os.getenv('DB_HOST'),
    "database": os.getenv('DB_NAME'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "port": os.getenv('DB_PORT')
}

# Gmail API configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class EmailBot:
    def __init__(self):
        self.check = True
        self.current_email = None
        self.application = Application.builder().token(TOKEN).build()
        self.ai_report_mode = {}  # Dictionary to track AI report mode for each user
        self.search_mode = {}  # Dictionary to track search mode for each user
        self.place_search_mode = {}  # Dictionary to track place search mode for each user

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text('Xin chào! Tôi là bot theo dõi chi tiêu. Hãy sử dụng /help để xem các lệnh có sẵn!')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
        📱 Các lệnh có sẵn:

        🔧 Lệnh Cơ Bản:
        1. /help: Hiển thị các lệnh hỗ trợ
        2. /reset_bot: Reset bot
        3. /name_love: Hiển thị tên người yêu

        💰 Quản Lý Tài Chính:
        4. /check_bot: Kiểm tra thông báo
        5. /check_outlay: Kiểm tra tiền đã tiêu trong tháng
        6. /report: Xem thống kê chi tiêu theo danh mục
        7. /check_outlay_web: Xem báo cáo chi tiêu trực quan

        🤖 Tính Năng AI:
        8. /bot_ai_gen_report: Bật chế độ phân tích tin nhắn thoại
        9. /bot_ai_gen_report_image: Bật chế độ phân tích ảnh
        10. /exit: Thoát chế độ phân tích

        🔍 Tính Năng Tìm Kiếm:
        11. /search: Tìm kiếm thông tin với AI
        12. /place_search: Tìm kiếm địa điểm và hiển thị Google Maps
        """
        await update.message.reply_text(help_text)

    async def reset_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset_bot command"""
        try:
            # Run getDataFromGmail.py with venv python
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await update.message.reply_text(f"🔄 Đang cập nhật dữ liệu từ Gmail... ({current_time})")
            
            # Use python3 from virtual environment
            subprocess.run(['venv/bin/python3', 'getDataFromGmail.py'], check=True)
            
            # Check for unread transactions
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            query = """
            SELECT COUNT(*) 
            FROM "Email" 
            WHERE "isRead" = false;
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            unread_count = result[0] if result[0] else 0
            
            if unread_count > 0:
                await update.message.reply_text(
                    f"✅ Đã cập nhật dữ liệu!\n"
                    f"📝 Có {unread_count} giao dịch chưa ghi chú.\n"
                    f"Sử dụng /check_bot để xem chi tiết."
                )
            else:
                await update.message.reply_text("✅ Đã cập nhật dữ liệu!\n📝 Không có giao dịch nào chưa ghi chú.")
            
            self.check = True
            self.current_email = None
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running getDataFromGmail.py: {e}")
            await update.message.reply_text("❌ Lỗi khi cập nhật dữ liệu từ Gmail!")
        except Exception as e:
            logging.error(f"Error in reset_bot: {e}")
            await update.message.reply_text("❌ Lỗi khi reset bot!")

    async def check_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check_bot command"""
        try:
            # Get unread emails
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            query = """
            SELECT "emailId", "price", "note", "createdAt" 
            FROM "Email" 
            WHERE "isRead" = false 
            ORDER BY "createdAt" DESC;
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if results:
                message = "📝 Danh sách giao dịch chưa ghi chú:\n\n"
                for email in results:
                    money = float(email[1])
                    status = 'giảm' if money < 0 else 'tăng'
                    formatted_money = "{:,.0f}".format(abs(money))
                    created_at = email[3].strftime("%Y-%m-%d %H:%M:%S")
                    message += f"💰 {formatted_money} VNĐ ({status})\n📄 {email[2]}\n🕒 {created_at}\n\n"
                
                message += "Vui lòng reply để ghi chú chi tiết theo định dạng:\nDANH_MUC - chi tiết"
                await update.message.reply_text(message)
            else:
                await update.message.reply_text("✅ Không có giao dịch nào chưa ghi chú!")
            
            self.check = True
        except Exception as e:
            logging.error(f"Error checking unread transactions: {e}")
            await update.message.reply_text("❌ Lỗi khi kiểm tra giao dịch!")

    async def check_outlay(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check_outlay command"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            query = """
            SELECT SUM("price") FROM "Email" 
            WHERE "month" = %s AND "isRead" = true AND "price" < 0;
            """
            
            cursor.execute(query, (datetime.now().month,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            total = result[0] if result[0] else 0
            formatted_total = "{:,.0f}".format(total)
            await update.message.reply_text(f"✅ Đã chi tiêu trong tháng này!\nTổng: {formatted_total}")
        except Exception as e:
            logging.error(f"Error getting total expense: {e}")
            await update.message.reply_text("❌ Lỗi khi lấy tổng chi tiêu!")

    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /report command"""
        try:
            # Get month from command arguments
            args = context.args
            if not args:
                await update.message.reply_text(
                    "❌ Vui lòng chỉ định tháng!\n"
                    "Cú pháp: /report <tháng>\n"
                    "Ví dụ: /report 3"
                )
                return

            try:
                month = int(args[0])
                if month < 1 or month > 12:
                    await update.message.reply_text("❌ Tháng phải từ 1 đến 12!")
                    return
            except ValueError:
                await update.message.reply_text("❌ Tháng phải là số!")
                return

            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # Get expenses grouped by category
            query = """
            SELECT 
                "category",
                COUNT(*) as transaction_count,
                SUM("price") as total_amount,
                array_agg("expense") as expenses,
                array_agg("note") as notes
            FROM "Email" 
            WHERE "month" = %s
            AND "isRead" = true
            AND "category" IS NOT NULL
            GROUP BY "category"
            ORDER BY total_amount ASC;
            """
            
            cursor.execute(query, (month,))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if results:
                message = f"📊 Thống kê chi tiêu tháng {month}:\n\n"
                total_spent = 0
                
                for category, count, amount, expenses, notes in results:
                    formatted_amount = "{:,.0f}".format(abs(amount))
                    status = 'chi' if amount < 0 else 'thu'
                    
                    message += f"📌 {category}:\n"
                    message += f"💰 Tổng: {formatted_amount} VNĐ ({status})\n"
                    message += f"📝 Chi tiết:\n"
                    
                    # Add each expense with bullet point
                    for expense, note in zip(expenses, notes):
                        if note:
                            message += f"• {expense} ({note})\n"
                        else:
                            message += f"• {expense}\n"
                    
                    message += "\n"
                    total_spent += amount
                
                # Add total summary
                formatted_total = "{:,.0f}".format(abs(total_spent))
                status = 'chi' if total_spent < 0 else 'thu'
                message += f"📈 Tổng cộng: {formatted_total} VNĐ ({status})"
                
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(f"📊 Chưa có dữ liệu chi tiêu trong tháng {month}!")
                
        except Exception as e:
            logging.error(f"Error generating report: {e}")
            await update.message.reply_text("❌ Lỗi khi tạo báo cáo!")

    async def name_love(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /name_love command"""
        await update.message.reply_text("❤️ Hoàng Đăng vs Thy Uyên ❤️")

    async def check_outlay_web(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check_outlay_web command"""
        await update.message.reply_text(
            "🌐 Xem báo cáo chi tiêu trực quan tại:\n"
            "https://pandadanh.github.io/report-Financial/"
        )

    async def bot_ai_gen_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /bot_ai_gen_report command"""
        user_id = update.effective_user.id
        self.ai_report_mode[user_id] = True
        
        await update.message.reply_text(
            "🤖 Chế độ tạo báo cáo AI đã được kích hoạt!\n\n"
            "Bạn có thể gửi tin nhắn thoại để tôi phân tích.\n"
            "Mỗi tin nhắn thoại sẽ được phân tích thành 3 phần:\n"
            "1. Hôm qua đã làm gì\n"
            "2. Hôm nay sẽ làm gì\n"
            "3. Những khó khăn\n"
        )

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        user_id = update.effective_user.id
        self.search_mode[user_id] = True
        
        await update.message.reply_text(
            "🔍 Chế độ tìm kiếm đã được kích hoạt!\n\n"
            "Bạn muốn tìm kiếm gì?"
        )

    async def place_search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /place_search command"""
        user_id = update.effective_user.id
        self.place_search_mode[user_id] = True
        
        await update.message.reply_text(
            "📍 Chế độ tìm kiếm địa điểm đã được kích hoạt!\n\n"
            "Bạn muốn tìm kiếm địa điểm gì?"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        try:
            message = update.message.text
            user_id = update.effective_user.id
            reply_to_message = update.message.reply_to_message

            # Check if user is in search mode
            if user_id in self.search_mode:
                await self.process_search_query(update, message)
                return

            # Check if user is in place search mode
            if user_id in self.place_search_mode:
                await self.process_place_search_query(update, message)
                return

            if reply_to_message:
                try:
                    # Log the received message for debugging
                    logging.info(f"Received reply message: {message}")
                    
                    # Validate reply syntax
                    if ' - ' not in message:
                        await update.message.reply_text(
                            "❌ Cú pháp không đúng!\n"
                            "Vui lòng nhập theo định dạng:\n"
                            "DANH_MUC - chi tiết\n"
                            "Ví dụ: MUA_SAM - mua quần áo",
                            quote=False
                        )
                        return

                    # Parse reply message
                    category, expense = message.split(' - ', 1)
                    category = category.strip().upper()
                    expense = expense.strip()

                    # Log parsed data
                    logging.info(f"Parsed category: {category}, expense: {expense}")

                    # Validate category and expense
                    if not category or not expense:
                        await update.message.reply_text(
                            "❌ Danh mục hoặc chi tiết không được để trống!\n"
                            "Vui lòng nhập theo định dạng:\n"
                            "DANH_MUC - chi tiết\n"
                            "Ví dụ: MUA_SAM - mua quần áo",
                            quote=False
                        )
                        return

                    # Extract transaction info from replied message
                    replied_text = reply_to_message.text
                    price_match = re.search(r'(\d+(?:,\d+)*) VNĐ', replied_text)
                    note_match = re.search(r'Nội dung: (.+?)(?:\n|$)', replied_text)
                    
                    if not price_match or not note_match:
                        await update.message.reply_text(
                            "❌ Không thể tìm thấy thông tin giao dịch trong tin nhắn được trả lời!",
                            quote=False
                        )
                        return
                        
                    # Convert price string to number
                    price_str = price_match.group(1).replace(',', '')
                    price = float(price_str)
                    if 'giảm' in replied_text:
                        price = -price
                        
                    note = note_match.group(1).strip()
                    
                    # Save reply as note with category and expense
                    conn = psycopg2.connect(**DB_CONFIG)
                    cursor = conn.cursor()
                    
                    try:
                        # Find the transaction in database
                        query = """
                        SELECT "emailId" FROM "Email"
                        WHERE "price" = %s AND "note" = %s AND "isRead" = false
                        ORDER BY "createdAt" DESC LIMIT 1;
                        """
                        
                        cursor.execute(query, (price, note))
                        result = cursor.fetchone()
                        
                        if not result:
                            await update.message.reply_text(
                                "❌ Không tìm thấy giao dịch tương ứng trong cơ sở dữ liệu!",
                                quote=False
                            )
                            return
                            
                        # Update the transaction
                        update_query = """
                        UPDATE "Email" 
                        SET "isRead" = true,
                            "category" = %s,
                            "expense" = %s
                        WHERE "emailId" = %s
                        RETURNING "emailId";
                        """
                        
                        cursor.execute(update_query, (category, expense, result[0]))
                        update_result = cursor.fetchone()
                        conn.commit()
                        
                        if update_result:
                            # Get total expense after update
                            total = await self.get_total_expense()
                            formatted_total = "{:,.0f}".format(abs(total))
                            
                            # Send success messages
                            await update.message.reply_text(
                                f"✅ Đã lưu thông tin chi tiêu!\nDanh mục: {category}\nChi tiết: {expense}",
                                quote=False
                            )
                            
                            await update.message.reply_text(
                                f"💰 Tổng chi tiêu trong tháng này: {formatted_total} VNĐ",
                                quote=False
                            )
                        else:
                            await update.message.reply_text(
                                "❌ Không thể cập nhật thông tin! Vui lòng thử lại.",
                                quote=False
                            )
                            
                    except Exception as e:
                        logging.error(f"Database error: {str(e)}")
                        await update.message.reply_text(
                            "❌ Lỗi khi cập nhật cơ sở dữ liệu! Vui lòng thử lại.",
                            quote=False
                        )
                        conn.rollback()
                    finally:
                        cursor.close()
                        conn.close()
                    
                except Exception as e:
                    logging.error(f"Error processing reply: {str(e)}")
                    await update.message.reply_text(
                        "❌ Có lỗi xảy ra khi xử lý phản hồi! Vui lòng thử lại.",
                        quote=False
                    )
            else:
                if message in ['/reset_bot', 'Reset-bot']:
                    self.check = True
                    self.current_email = None
                    await update.message.reply_text("✅ Bot đã được reset!")
                elif message in ['/check_bot', 'Check-bot']:
                    await self.check_bot(update, context)
                elif message in ['/check_outlay', 'Check-outlay']:
                    await self.check_outlay(update, context)
                elif message in ['/report', 'Report']:
                    await self.report_command(update, context)
                elif message in ['/help', 'help']:
                    await self.help_command(update, context)
                elif message in ['/name_love', 'Name-love']:
                    await self.name_love(update, context)
                elif message in ['/check_outlay_web', 'Check-outlay-web']:
                    await self.check_outlay_web(update, context)
                elif message in ['/bot_ai_gen_report', 'Bot-AI-gen-report']:
                    await self.bot_ai_gen_report(update, context)
                elif message in ['/search', 'Search']:
                    await self.search_command(update, context)
                elif message in ['/place_search', 'Place-search']:
                    await self.place_search_command(update, context)
                else:
                    await update.message.reply_text("❌ Lệnh không hợp lệ. Hãy thử /help để xem danh sách lệnh hỗ trợ!")

        except Exception as e:
            logging.error(f"Error handling message: {e}")

    async def process_search_query(self, update: Update, query: str):
        """Process a search query and ask for more"""
        try:
            user_id = update.effective_user.id
            # Configure Gemini API
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Create prompt for enhancing search query
            prompt = f"""
            Hãy tạo câu truy vấn tìm kiếm chi tiết và đầy đủ hơn từ câu truy vấn sau:
            "{query}"
            
            Hãy:
            1. Thêm các từ khóa liên quan
            2. Làm rõ mục đích tìm kiếm
            3. Thêm các tiêu chí cụ thể
            4. Giữ nguyên ý nghĩa gốc
            
            Chỉ trả về câu truy vấn đã được cải thiện, không thêm giải thích.
            """
            
            # Generate enhanced query using Gemini
            response = model.generate_content(prompt)
            enhanced_query = response.text.strip()
            
            # Send initial message
            await update.message.reply_text(
                f"🔍 Đang tìm kiếm với câu truy vấn:\n{enhanced_query}\n\n"
                "Vui lòng đợi trong giây lát..."
            )
            
            # Perform web search
            search_results = []
            async with aiohttp.ClientSession() as session:
                # Get top 5 search results
                for url in search(enhanced_query, num_results=5):
                    try:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # Extract title
                                title = soup.title.string if soup.title else url
                                
                                # Extract description
                                meta_desc = soup.find('meta', {'name': 'description'})
                                description = meta_desc['content'] if meta_desc else "Không có mô tả"
                                
                                # Clean up text
                                title = re.sub(r'\s+', ' ', title).strip()
                                description = re.sub(r'\s+', ' ', description).strip()
                                
                                search_results.append({
                                    'title': title,
                                    'description': description,
                                    'url': url
                                })
                    except Exception as e:
                        logging.error(f"Error fetching {url}: {e}")
                        continue
            
            # Format and send results
            if search_results:
                message = "📊 Kết quả tìm kiếm:\n\n"
                for i, result in enumerate(search_results, 1):
                    message += f"{i}. {result['title']}\n"
                    message += f"📝 {result['description']}\n"
                    message += f"🔗 {result['url']}\n\n"
                
                message += "Bạn có thể dùng lệnh /search để tìm kiếm tiếp."
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(
                    "❌ Không tìm thấy kết quả nào!\n\n"
                    "Bạn có thể dùng lệnh /search để tìm kiếm lại."
                )
            
            # Automatically exit search mode
            if user_id in self.search_mode:
                del self.search_mode[user_id]
                
        except Exception as e:
            await update.message.reply_text(
                "❌ Có lỗi xảy ra khi tìm kiếm!\n\n"
                "Bạn có thể dùng lệnh /search để thử lại."
            )
            # Ensure we exit search mode even on error
            if user_id in self.search_mode:
                del self.search_mode[user_id]
            logging.error(f"Error in search: {e}")

    async def get_total_expense(self):
        """Get total expense for current month"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            query = """
            SELECT SUM("price") FROM "Email" 
            WHERE "month" = %s AND "isRead" = true;
            """
            
            cursor.execute(query, (datetime.now().month,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return result[0] if result[0] else 0
        except Exception as e:
            logging.error(f"Error getting total expense: {e}")
            return 0

    async def run_gmail_script(self):
        """Run getDataFromGmail.py every hour"""
        while True:
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logging.info(f"Running getDataFromGmail.py at {current_time}")
                # Use python3 from virtual environment
                subprocess.run(['venv/bin/python3', 'getDataFromGmail.py'], check=True)
                logging.info("getDataFromGmail.py completed successfully")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error running getDataFromGmail.py: {e}")
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
            
            await asyncio.sleep(3600)  # Wait for 1 hour

    async def check_unread_transactions(self):
        """Check for unread transactions every 15 seconds"""
        while True:
            try:
                # Get unread email
                conn = psycopg2.connect(**DB_CONFIG)
                cursor = conn.cursor()
                
                query = """
                SELECT "emailId", "price", "note" 
                FROM "Email" 
                WHERE "isRead" = false 
                ORDER BY "createdAt" DESC 
                LIMIT 1;
                """
                
                cursor.execute(query)
                result = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if result and self.check:  # Only send if we have an unread email and check is True
                    self.current_email = {
                        "emailId": result[0],
                        "price": result[1],
                        "note": result[2]
                    }
                    
                    # Send notification
                    money = float(self.current_email["price"])
                    status = 'giảm' if money < 0 else 'tăng'
                    formatted_money = "{:,.0f}".format(abs(money))
                    message = f"Chào Hoàng Đăng\nTài khoản của bạn đã {status} {formatted_money} VNĐ\nNội dung: {self.current_email['note']}\nCho tôi biết lý do chi tiêu của bạn nha!"
                    
                    await self.application.bot.send_message(chat_id=CHAT_ID, text=message)
                    self.check = False
                    logging.info(f"Sent notification for transaction: {formatted_money} VNĐ")
                    
                    # Start auto-resend task
                    asyncio.create_task(self.auto_resend_notification())
            
            except Exception as e:
                logging.error(f"Error checking unread transactions: {e}")
            
            await asyncio.sleep(15)  # Wait for 15 seconds

    async def auto_resend_notification(self):
        """Auto resend notification after 5 seconds if no response"""
        while self.current_email and not self.check:
            await asyncio.sleep(15)  # Wait for 5 seconds
            
            # Check if email is still unread
            try:
                conn = psycopg2.connect(**DB_CONFIG)
                cursor = conn.cursor()
                
                query = """
                SELECT "isRead" FROM "Email" 
                WHERE "emailId" = %s;
                """
                
                cursor.execute(query, (self.current_email["emailId"],))
                result = cursor.fetchone()
                cursor.close()
                conn.close()
                
                if result and not result[0]:  # If still unread
                    # Resend notification
                    money = float(self.current_email["price"])
                    status = 'giảm' if money < 0 else 'tăng'
                    formatted_money = "{:,.0f}".format(abs(money))
                    message = f"Chào Hoàng Đăng\nTài khoản của bạn đã {status} {formatted_money} VNĐ\nNội dung: {self.current_email['note']}\nCho tôi biết lý do chi tiêu của bạn nha!"
                    
                    await self.application.bot.send_message(chat_id=CHAT_ID, text=message)
                    logging.info(f"Re-sent notification for transaction: {formatted_money} VNĐ")
                else:
                    break  # Stop if email is read
                    
            except Exception as e:
                logging.error(f"Error in auto-resend: {e}")
                break

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages"""
        try:
            user_id = update.effective_user.id
            
            # Check if user is in AI report mode
            if user_id not in self.ai_report_mode:
                await update.message.reply_text(
                    "❌ Bạn cần sử dụng lệnh /bot_ai_gen_report trước khi gửi tin nhắn thoại!"
                )
                return
                
            # Check if the message is a text message with /exit
            if update.message.text and update.message.text.lower() == '/exit':
                await self.exit_ai_report(update, context)
                return

            # Download the voice message
            voice = update.message.voice
            voice_file = await context.bot.get_file(voice.file_id)
            
            # Create temporary files for audio processing
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as ogg_file, \
                 tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                
                # Download voice message as OGG file
                await voice_file.download_to_drive(ogg_file.name)
                
                # Convert OGG to WAV using pydub
                audio = AudioSegment.from_ogg(ogg_file.name)
                audio.export(wav_file.name, format="wav")
                
                # Initialize speech recognition
                recognizer = sr.Recognizer()
                
                # Transcribe audio to text
                with sr.AudioFile(wav_file.name) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language='vi-VN')  # Vietnamese language
                    
                    # Configure Gemini API
                    genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    
                    # Create prompt for analysis
                    prompt = f"""
                    Hãy phân tích và tóm tắt nội dung sau thành 3 phần:
                    1. Hôm qua đã làm gì
                    2. Hôm nay sẽ làm gì
                    3. Những khó khăn
                    
                    Nội dung: {text}
                    
                    Hãy trả lời theo định dạng:
                    HÔM QUA:
                    - Điểm 1
                    - Điểm 2
                    ...
                    
                    HÔM NAY:
                    - Điểm 1
                    - Điểm 2
                    ...
                    
                    KHÓ KHĂN:
                    - Điểm 1
                    - Điểm 2
                    ...
                    """
                    
                    # Generate response using Gemini
                    response = model.generate_content(prompt)
                    
                    if response.text:
                        # Send both original transcription and AI summary
                        await update.message.reply_text(
                            "🎤 Nội dung tin nhắn thoại của bạn:\n\n"
                            f"📝 {text}\n\n"
                            "🤖 Phân tích AI:\n\n"
                            f"{response.text}\n\n"
                            "Gửi tin nhắn thoại khác hoặc /exit để thoát."
                        )
                    else:
                        # If AI analysis fails, just send the transcription
                        await update.message.reply_text(
                            "🎤 Nội dung tin nhắn thoại của bạn:\n\n"
                            f"📝 {text}\n\n"
                            "❌ Không thể phân tích AI lúc này.\n"
                            "Gửi tin nhắn thoại khác hoặc /exit để thoát."
                        )
                
                # Clean up temporary files
                os.unlink(ogg_file.name)
                os.unlink(wav_file.name)
                
        except sr.UnknownValueError:
            await update.message.reply_text("❌ Không thể nhận dạng giọng nói. Vui lòng thử lại!")
        except sr.RequestError as e:
            await update.message.reply_text("❌ Lỗi khi kết nối với dịch vụ nhận dạng giọng nói!")
            logging.error(f"Speech recognition error: {e}")
        except Exception as e:
            await update.message.reply_text("❌ Có lỗi xảy ra khi xử lý tin nhắn thoại!")
            logging.error(f"Error handling voice message: {e}")

    async def bot_ai_gen_report_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /bot_ai_gen_report_image command"""
        user_id = update.effective_user.id
        self.ai_report_mode[user_id] = 'image'
        
        await update.message.reply_text(
            "🤖 Chế độ phân tích ảnh đã được kích hoạt!\n\n"
            "Bạn có thể gửi ảnh để tôi phân tích.\n"
            "Tôi sẽ:\n"
            "1. Chuyển ảnh thành văn bản\n"
            "2. Định dạng văn bản\n"
            "3. Gửi lại kết quả\n"
        )

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle image messages"""
        try:
            user_id = update.effective_user.id
            
            # Check if user is in image analysis mode
            if user_id in self.ai_report_mode and self.ai_report_mode[user_id] == 'image':
                # Check if the message is a text message with /exit
                if update.message.text and update.message.text.lower() == '/exit':
                    await self.exit_ai_report(update, context)
                    return
                    
                # Get the image file
                photo = update.message.photo[-1]  # Get the largest size
                file = await context.bot.get_file(photo.file_id)
                
                # Download the image
                image_bytes = await file.download_as_bytearray()
                
                # Convert to PIL Image
                image = Image.open(io.BytesIO(image_bytes))
                
                # Extract text using OCR
                text = pytesseract.image_to_string(image, lang='vie')
                
                if not text.strip():
                    await update.message.reply_text("❌ Không thể nhận dạng văn bản từ ảnh. Vui lòng thử lại!")
                    return
                
                # Configure Gemini API
                genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
                model = genai.GenerativeModel('gemini-2.0-flash')
                
                # Create prompt for formatting
                prompt = f"""
                Hãy định dạng và làm rõ văn bản sau một cách chuyên nghiệp và dễ đọc:
                
                {text}
                
                Hãy:
                1. Sửa lỗi chính tả
                2. Thêm dấu câu nếu cần
                3. Định dạng lại cấu trúc câu
                4. Giữ nguyên ý nghĩa gốc
                """
                
                # Generate formatted text using Gemini
                response = model.generate_content(prompt)
                
                if response.text:
                    await update.message.reply_text(
                        "📸 Văn bản từ ảnh của bạn:\n\n"
                        f"📝 {text}\n\n"
                        "✨ Văn bản đã được định dạng:\n\n"
                        f"{response.text}\n\n"
                        "Gửi ảnh khác hoặc /exit để thoát."
                    )
                else:
                    await update.message.reply_text(
                        "📸 Văn bản từ ảnh của bạn:\n\n"
                        f"📝 {text}\n\n"
                        "❌ Không thể định dạng văn bản lúc này.\n"
                        "Gửi ảnh khác hoặc /exit để thoát."
                    )
                
        except Exception as e:
            await update.message.reply_text("❌ Có lỗi xảy ra khi xử lý ảnh!")
            logging.error(f"Error handling image: {e}")

    async def process_place_search_query(self, update: Update, query: str):
        """Process a place search query and ask for more"""
        try:
            # Configure Gemini API
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Create prompt for enhancing search query
            prompt = f"""
            Hãy tạo câu truy vấn tìm kiếm địa điểm chi tiết và đầy đủ hơn từ câu truy vấn sau:
            "{query}"
            
            Hãy:
            1. Thêm từ khóa "location" hoặc "place"
            2. Thêm từ khóa "address" hoặc "địa chỉ"
            3. Thêm từ khóa "review" hoặc "đánh giá"
            4. Giữ nguyên ý nghĩa gốc
            
            Chỉ trả về câu truy vấn đã được cải thiện, không thêm giải thích.
            """
            
            # Generate enhanced query using Gemini
            response = model.generate_content(prompt)
            enhanced_query = response.text.strip()
            
            # Send initial message
            await update.message.reply_text(
                f"🔍 Đang tìm kiếm địa điểm với câu truy vấn:\n{enhanced_query}\n\n"
                "Vui lòng đợi trong giây lát..."
            )
            
            # Perform web search
            search_results = []
            async with aiohttp.ClientSession() as session:
                # Get top 5 search results
                for url in search(enhanced_query, num_results=5):
                    try:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # Extract title
                                title = soup.title.string if soup.title else url
                                
                                # Extract description
                                meta_desc = soup.find('meta', {'name': 'description'})
                                description = meta_desc['content'] if meta_desc else "Không có mô tả"
                                
                                # Clean up text
                                title = re.sub(r'\s+', ' ', title).strip()
                                description = re.sub(r'\s+', ' ', description).strip()
                                
                                # Create Google Maps search URL
                                maps_query = f"{title} {description}"
                                maps_query = re.sub(r'[^\w\s]', '', maps_query)  # Remove special characters
                                maps_url = f"https://www.google.com/maps/search/{maps_query.replace(' ', '+')}"
                                
                                search_results.append({
                                    'title': title,
                                    'description': description,
                                    'url': url,
                                    'maps_url': maps_url
                                })
                    except Exception as e:
                        logging.error(f"Error fetching {url}: {e}")
                        continue
            
            # Format and send results
            if search_results:
                message = "📍 Kết quả tìm kiếm địa điểm:\n\n"
                for i, result in enumerate(search_results, 1):
                    message += f"{i}. {result['title']}\n"
                    message += f"📝 {result['description']}\n"
                    message += f"🔗 {result['url']}\n"
                    message += f"🗺️ Google Maps: {result['maps_url']}\n\n"
                
                message += "Bạn muốn tìm kiếm địa điểm nào nữa không?\nGửi /exit để thoát chế độ tìm kiếm."
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(
                    "❌ Không tìm thấy địa điểm nào!\n\n"
                    "Bạn muốn tìm kiếm địa điểm nào nữa không?\nGửi /exit để thoát chế độ tìm kiếm."
                )
                
        except Exception as e:
            await update.message.reply_text(
                "❌ Có lỗi xảy ra khi tìm kiếm địa điểm!\n\n"
                "Bạn muốn tìm kiếm địa điểm nào nữa không?\nGửi /exit để thoát chế độ tìm kiếm."
            )
            logging.error(f"Error in place search: {e}")

    def run(self):
        """Start the bot and the schedulers"""
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("reset_bot", self.reset_bot))
        self.application.add_handler(CommandHandler("check_bot", self.check_bot))
        self.application.add_handler(CommandHandler("check_outlay", self.check_outlay))
        self.application.add_handler(CommandHandler("report", self.report_command))
        self.application.add_handler(CommandHandler("name_love", self.name_love))
        self.application.add_handler(CommandHandler("check_outlay_web", self.check_outlay_web))
        self.application.add_handler(CommandHandler("bot_ai_gen_report", self.bot_ai_gen_report))
        self.application.add_handler(CommandHandler("bot_ai_gen_report_image", self.bot_ai_gen_report_image))
        self.application.add_handler(CommandHandler("search", self.search_command))
        self.application.add_handler(CommandHandler("place_search", self.place_search_command))
        
        # Add message handlers
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_image))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Create event loop
        loop = asyncio.get_event_loop()
        
        # Start both schedulers
        loop.create_task(self.run_gmail_script())
        loop.create_task(self.check_unread_transactions())
        
        # Start the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = EmailBot()
    bot.run()