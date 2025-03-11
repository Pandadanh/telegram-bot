import { Injectable } from '@nestjs/common';
import { Interval } from '@nestjs/schedule';
import { Bot } from 'grammy';
import { EmailService } from '../email/email.service';
import { Email } from 'src/email/email.entity';

@Injectable()
export class TelegramService {
    private chatId;
    private emails;
    private check;

    constructor(private bot: Bot, private emailService: EmailService) {
        this.init();
        this.emails = new Email();
        this.check = true;
        this.chatId = "7408813563";
    }

    async sendMessage(chatId: string, message: string): Promise<void> {
        await this.bot.api.sendMessage(chatId, message);
    }


    private init() {
        console.log("🚀 Đang khởi động bot...");

        this.bot.on('message', async (ctx) => {
            try {
                const userMessage = ctx.message.text;
                const replyToMessage = ctx.message.reply_to_message;

                if (replyToMessage) {
                    console.log('📩 Bạn đã reply tin nhắn:', replyToMessage.text);
                    console.log('📝 Nội dung reply:', userMessage);

                    if (this.emails != null && this.emails != undefined) {
                        const success = await this.emailService.saveEmailsReply(this.emails, userMessage);
                        if (success) {
                            const total = await this.emailService.getTotalUnreadExpense(new Date().getMonth() + 1);
                            console.log('Tổng chi tháng này:', total);
                            this.check = true;
                            this.emails = null;

                            const formattedTotal = total.toLocaleString("vi-VN");
                            await ctx.reply(`✅ Đã chi tiêu trong tháng này!\nTổng: ${formattedTotal}`);

                        } else {
                            await ctx.reply("❌ Lỗi khi lưu dữ liệu. Vui lòng thử lại.");
                        }
                    }
                } else {
                    // await ctx.reply("⚠️ Hãy reply tin nhắn để lưu chi tiêu!");
                    if (userMessage === '/reset_bot' || userMessage === 'Reset-bot')
                        this.check = true;

                    else if (userMessage === '/check_bot' || userMessage === 'Check-bot') {
                        console.log('Check bot');
                        this.check = true;
                        await this.emailService.runPythonScript();
                        await this.autoSendMessage();
                    }
                    else if (userMessage === '/check_outlay' || userMessage === 'Check-outlay') {
                        const total = await this.emailService.getTotalUnreadExpense(new Date().getMonth() + 1);
                        console.log('Tổng chi tháng này:', total);
                        const formattedTotal = total.toLocaleString("vi-VN");
                        await ctx.reply(`✅ Đã chi tiêu trong tháng này!\nTổng: ${formattedTotal}`);
                    }
                    else if (userMessage === '/help' || userMessage === 'help') {
                        await ctx.reply("Hiện tại hệ thống có các lệnh sau:\n1. /reset_bot: Để reset bot\n2. /check_bot: Để kiểm tra thông báo\n3. /check_outlay: Kiểm tra tiền đã tiêu trong tháng\n4. /help: Hiển thị các lệnh hỗ trợ\n5. /log_time: LogWork Jira");
                    }
                    else {
                        await ctx.reply("❌ Lệnh không hợp lệ. Hãy thử /help để xem danh sách lệnh hỗ trợ!");
                    }

                }
            } catch (error) {
                console.error('❌ Lỗi khi xử lý tin nhắn:', error);
            }

        });

        this.bot.start().then(() => console.log("✅ Bot đã khởi động!"));
    }

    // private init() {
    //     console.log("🚀 Đang khởi động bot...");

    //     this.bot.on('message', async (ctx) => {
    //         console.log("📩 Tin nhắn nhận được:", ctx.message);

    //         if (ctx.message.text) {
    //             console.log("📝 Nội dung:", ctx.message.text);
    //             await ctx.reply(`👋 Xin chào! Bạn vừa gửi: ${ctx.message.text}`);
    //         } else {
    //             console.log("⚠️ Không có nội dung tin nhắn!");
    //         }
    //     });

    //     this.bot.start().then(() => console.log("✅ Bot đã khởi động!"));
    // }



    @Interval(30000)
    async autoSendMessage() {
        try {

            // const currentHour = new Date().getHours(); // Lấy giờ hiện tại

            // if (currentHour >= 23 || currentHour < 6) {
            //     console.log("Ngoài giờ hoạt động (23h - 6h), không chạy.");
            //     return;
            // }

            if (!this.check) {
                console.log('Chưa có phản hồi, không cần gọi API');
                const email = this.emails;
                const money = parseFloat(email.price);
                const status = money < 0 ? 'giảm' : 'tăng';
                const formattedMoney = Math.abs(money).toLocaleString('vi-VN');
                const message = `Chào Hoàng Đăng\nTài khoản của bạn đã ${status} ${formattedMoney} VNĐ\nNội dung: ${email.note}\nCho tôi biết lý do chi tiêu của bạn nha!`;

                console.log('Gửi tin nhắn:', message);
                await this.sendMessage(this.chatId, message);

                return;
            }


            this.emails = await this.emailService.getUnreadEmails();
            this.check = false;
            console.log('Danh sách email chưa đọc:', this.emails);

            const email = this.emails; // Lấy email đầu tiên
            const money = parseFloat(email.price);
            const status = money < 0 ? 'giảm' : 'tăng';
            const formattedMoney = Math.abs(money).toLocaleString('vi-VN');
            const message = `Chào Hoàng Đăng\nTài khoản của bạn đã ${status} ${formattedMoney} VNĐ với nội dung: ${email.note}\nCho tôi biết lý do chi tiêu của bạn đi nha!`;

            console.log('Gửi tin nhắn:', message);
            await this.sendMessage(this.chatId, message);
        }
        catch (error) {
            console.error('❌ Không có gì để gửi:');
        }

    }

    async getMoneyByString(message: string): Promise<number> {
        const regex = /(\d[\d,.]*)\s*VND/;
        const match = message.match(regex);
        if (!match) {
            return 0;
        }
        const amountStr = match[1].replace(/,/g, '');
        return parseFloat(amountStr);
    }



}
