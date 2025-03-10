import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { google } from 'googleapis';
import * as path from 'path';
import * as dotenv from 'dotenv';
import { GoogleAuth } from 'google-auth-library';

dotenv.config();

@Injectable()
export class EmailService {
    private auth;
    private readonly logger = new Logger(EmailService.name);

    constructor(private prisma: PrismaService) {
        const keyPath = path.join(__dirname, '../../credentials.json');
        this.auth = new GoogleAuth({
            keyFile: keyPath,
            scopes: ['https://www.googleapis.com/auth/gmail.readonly']
        });
    }

    async getAccessToken() {
        try {
            const client = await this.auth.getClient();
            const accessToken = await client.getAccessToken();
            console.log('Access Token:', accessToken);
            return accessToken;
        } catch (error) {
            console.error('Lỗi khi lấy Access Token:', error);
        }
    }

    async getDetailEmail(emailId: string) {
        console.log('Lấy email:', emailId);
        const accessToken = await this.getAccessToken();
        const gmail = google.gmail({ version: 'v1', auth: this.auth });

        try {
            const res = await gmail.users.messages.get({
                userId: 'me',
                id: emailId,
                format: 'metadata',
            });

            return {
                emailId,
                snippet: res.data.snippet || 'Không có nội dung',
            };
        } catch (error) {
            this.logger.error(`Lỗi khi lấy email ${emailId}:`, error);
            return null;
        }
    }

    async getUnreadEmails() {
        console.log('🔹 Bắt đầu lấy email chưa đọc...');

        // const accessToken = await this.getAccessToken();
        // console.log('🔹 Access Token:', accessToken);

        // if (!accessToken) {
        //     this.logger.error('❌ Không lấy được access token!');
        //     return [];
        // }

        const gmail = google.gmail({ version: 'v1', auth: this.auth });
        const yesterday = Math.floor(new Date().setDate(new Date().getDate() - 1) / 1000);
        const now = Math.floor(Date.now() / 1000);
        const query = `after:${yesterday} before:${now} from:support@timo.vn`;

        console.log('🔹 Truy vấn Gmail API với query:', query);



        try {
            console.log('🔹 Lấy danh sách email...', this.auth);
            console.log('🔹 Lấy danh sách email...', gmail);

            const res = await gmail.users.messages.list({ userId: 'me', q: query });

            console.log('✅ Phản hồi từ API:', res.data);

            const messages = res.data.messages || [];
            this.logger.log(`📩 Tìm thấy ${messages.length} email.`);

            if (messages.length === 0) {
                return [];
            }

            console.log('🔹 Kiểm tra email đã tồn tại trong DB...');
            const existingEmails = await this.prisma.email.findMany({
                where: { emailId: { in: messages.map(msg => msg.id) } },
                select: { emailId: true }
            });

            const existingEmailIds = new Set(existingEmails.map(e => e.emailId));

            const newEmails = messages.filter(msg => !existingEmailIds.has(msg.id));

            this.logger.log(`📌 Số email mới cần xử lý: ${newEmails.length}`);
            return newEmails;
        } catch (error) {
            this.logger.error('❌ Lỗi khi lấy danh sách email:', error);

            if (error.response) {
                console.error('❌ Chi tiết lỗi API:', error.response.data);
            }

            return [];
        }
    }

    async saveEmailsReply(email: { id: string, money: number }, expense: string) {
        console.log('Lưu email:', email, 'với chi tiêu:', expense);
        try {
            await this.prisma.email.create({
                data: {
                    emailId: email.id,
                    price: email.money,
                    month: new Date().getMonth() + 1,
                    expense,
                    createdAt: new Date()
                }
            });
        } catch (err) {
            console.error(`Lỗi khi insert email ${email.id}:`, err);
        }
    }

    async getTotalPrice(month: number) {
        try {
            const total = await this.prisma.email.aggregate({
                _sum: { price: true },
                where: { month }
            });

            return total._sum.price ?? 0;
        } catch (error) {
            return 0;
        }
    }
}