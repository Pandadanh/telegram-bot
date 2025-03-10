import { Injectable } from '@nestjs/common';
import { Cron, Interval } from '@nestjs/schedule';
import { Bot } from 'grammy';
import { EmailService } from '../email/email.service';

@Injectable()
export class TelegramService {
    constructor(private readonly bot: Bot, private emailService: EmailService) {
        this.init();
    }

    async sendMessage(chatId: string, message: string): Promise<void> {
        await this.bot.api.sendMessage(chatId, message);
    }

    private chatId = "7408813563";
    private emails = [];
    private check = true;

    private init() {
        this.bot.on('message', async (ctx) => {
            const userMessage = ctx.message.text;
            const replyToMessage = ctx.message.reply_to_message;

            if (replyToMessage) {
                console.log('Bạn đã reply tin nhắn:', replyToMessage.text);
                console.log('Nội dung reply:', userMessage);

                if (this.emails.length > 0) {
                    const emailToSave = this.emails[0];
                    this.emails = this.emails.filter(email => email.id !== emailToSave.id);

                    await this.emailService.saveEmailsReply(emailToSave, userMessage);
                    const total = await this.emailService.getTotalPrice(new Date().getMonth() + 1);
                    this.check = true;

                    await ctx.reply(`Đã chi tiêu trong tháng này! Tổng: ${total}`);
                } else {
                    await ctx.reply("Không có email nào để lưu.");
                }
            }
        });

        this.bot.start();
    }

    @Interval(60000)
    async autoSendMessage() {
        if (!this.check) {
            console.log("Chưa có phản hồi, không cần gọi API");
            return;
        }

        if (this.emails == undefined || this.emails.length === 0) {
            this.emails = await this.emailService.getUnreadEmails();
        }

        this.check = false;
        console.log(this.emails);
        console.log('Gửi tin nhắn tự động mỗi 1 phút!');

        if (this.emails.length > 0) {
            const emailDetail = await this.emailService.getDetailEmail(this.emails[0].id);
            const money = await this.getMoneyByString(emailDetail.snippet);

            this.emails[0] = { ...this.emails[0], money };

            await this.sendMessage(this.chatId, `Tài khoản bạn vừa thay đổi: ${money} VND`);
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
