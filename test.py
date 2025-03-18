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

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text('Xin chào! Tôi là bot theo dõi chi tiêu. Hãy sử dụng /help để xem các lệnh có sẵn!')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
        Các lệnh có sẵn:
        1. /reset_bot: Reset bot
        2. /check_bot: Kiểm tra thông báo
        3. /check_outlay: Kiểm tra tiền đã tiêu trong tháng
        4. /report: Xem thống kê chi tiêu theo danh mục
        5. /help: Hiển thị các lệnh hỗ trợ
        6. /name_love: Hiển thị tên người yêu
        """
        await update.message.reply_text(help_text)

    async def reset_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset_bot command"""
        try:
            # Run getDataFromGmail.py
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await update.message.reply_text(f"🔄 Đang cập nhật dữ liệu từ Gmail... ({current_time})")
            
            subprocess.run(['python', 'getDataFromGmail.py'], check=True)
            
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

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        try:
            message = update.message.text
            reply_to_message = update.message.reply_to_message

            if reply_to_message:
                if self.current_email:
                    try:
                        # Validate reply syntax
                        if ' - ' not in message:
                            await update.message.reply_text(
                                "❌ Cú pháp không đúng!\n"
                                "Vui lòng nhập theo định dạng:\n"
                                "DANH_MUC - chi tiết\n"
                                "Ví dụ: MUA_SAM - mua quần áo"
                            )
                            return

                        # Parse reply message
                        category, expense = message.split(' - ', 1)
                        category = category.strip().upper()
                        expense = expense.strip()

                        # Validate category and expense
                        if not category or not expense:
                            await update.message.reply_text(
                                "❌ Danh mục hoặc chi tiết không được để trống!\n"
                                "Vui lòng nhập theo định dạng:\n"
                                "DANH_MUC - chi tiết\n"
                                "Ví dụ: MUA_SAM - mua quần áo"
                            )
                            return

                        # Save reply as note with category and expense
                        conn = psycopg2.connect(**DB_CONFIG)
                        cursor = conn.cursor()
                        
                        query = """
                        UPDATE "Email" 
                        SET "isRead" = true,
                            "category" = %s,
                            "expense" = %s
                        WHERE "emailId" = %s;
                        """
                        
                        cursor.execute(query, (category, expense, self.current_email["emailId"]))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        
                        self.current_email = None
                        self.check = True
                        
                        total = await self.get_total_expense()
                        formatted_total = "{:,.0f}".format(total)
                        await update.message.reply_text(f"✅ Đã lưu thông tin chi tiêu!\nDanh mục: {category}\nChi tiết: {expense}\nTổng chi tiêu tháng: {formatted_total}")
                    except Exception as e:
                        logging.error(f"Error saving reply: {e}")
                        await update.message.reply_text("❌ Lỗi khi lưu phản hồi! Vui lòng thử lại.")
                else:
                    await update.message.reply_text("⚠️ Không có email nào đang chờ phản hồi!")
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
                else:
                    await update.message.reply_text("❌ Lệnh không hợp lệ. Hãy thử /help để xem danh sách lệnh hỗ trợ!")

        except Exception as e:
            logging.error(f"Error handling message: {e}")

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
                subprocess.run(['python', 'getDataFromGmail.py'], check=True)
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