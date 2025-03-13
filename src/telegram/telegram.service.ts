import { Injectable, Logger } from '@nestjs/common';
import { Interval } from '@nestjs/schedule';
import axios from 'axios';

@Injectable()
export class TelegramService {
    private readonly logger = new Logger(TelegramService.name);
    private readonly botToken = '7722494289:AAGa3672BL-INBLI2rVPTWfddLLxkMN9bjA';
    private readonly apiUrl = `https://api.telegram.org/bot${this.botToken}`;
    private lastUpdateId = 0; // Lưu ID cập nhật cuối cùng

    // Hàm gọi API Telegram mỗi 1 giây
    @Interval(1000)
    async fetchMessages() {
        try {
            const response = await axios.get(`${this.apiUrl}/getUpdates`, {
                params: { offset: this.lastUpdateId + 1 }, // Lấy tin nhắn mới
            });

            const updates = response.data.result;
            if (updates.length > 0) {
                for (const update of updates) {
                    this.handleMessage(update);
                    this.lastUpdateId = update.update_id; // Cập nhật ID mới nhất
                }
            }
        } catch (error) {
            this.logger.error('Lỗi khi lấy tin nhắn:', error.message);
        }
    }

    // Hàm xử lý tin nhắn
    async handleMessage(update: any) {
        const message = update.message;
        if (!message) return;

        const chatId = message.chat.id;
        const text = message.text;

        this.logger.log(`📩 Tin nhắn từ ${chatId}: ${text}`);

        // Trả lời tin nhắn
        await this.sendMessage(chatId, `Bạn vừa gửi: ${text}`);
    }

    // Hàm gửi tin nhắn
    async sendMessage(chatId: number, text: string) {
        await axios.post(`${this.apiUrl}/sendMessage`, { chat_id: chatId, text });
    }
}
