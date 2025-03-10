import { Insert } from './../../node_modules/@sinclair/typebox/value/delta.d';
import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { google } from 'googleapis';
import axios from 'axios';
import * as dotenv from 'dotenv';

dotenv.config();

@Injectable()
export class EmailService {
    private auth;
    private readonly logger = new Logger(EmailService.name);
    private accessToken: string;

    constructor(private prisma: PrismaService) {
        this.auth = new google.auth.OAuth2(
            process.env.GOOGLE_CLIENT_ID,
            process.env.GOOGLE_CLIENT_SECRET,
            process.env.GOOGLE_REDIRECT_URI
        );
        this.loadTokenFromDB();
    }

    async loadTokenFromDB() {
        const tokenRecord = await this.prisma.oAuthToken.findFirst({ where: { id: '1' } });
        if (tokenRecord) {
            this.accessToken = tokenRecord.accessToken;
            this.auth.setCredentials({ access_token: this.accessToken });
        } else {
            this.logger.error('Không tìm thấy token trong database.');
        }
    }

    async ensureAccessToken() {
        if (!this.accessToken) {
            this.logger.warn('Access token không tồn tại hoặc đã hết hạn, đang lấy mới...');
            await this.refreshAccessToken();
        }
    }

    async refreshAccessToken() {
        const tokenRecord = await this.prisma.oAuthToken.findFirst({ where: { id: '1' } });
        if (tokenRecord?.refreshToken) {
            try {
                const response = await axios.post('https://oauth2.googleapis.com/token', new URLSearchParams({
                    client_id: process.env.GOOGLE_CLIENT_ID,
                    client_secret: process.env.GOOGLE_CLIENT_SECRET,
                    refresh_token: tokenRecord.refreshToken,
                    grant_type: 'refresh_token'
                }).toString(), {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
                });

                this.accessToken = response.data.access_token;
                this.auth.setCredentials({ access_token: this.accessToken });
                await this.updateTokenInDB(response.data);
            } catch (error) {
                this.logger.error('Lỗi khi refresh token', error.message);
            }
        } else {
            this.logger.error('Không có refresh token để làm mới access token.');
        }
    }

    async getDetailEmail(emailId: string) {
        console.log('Lấy email:', emailId);
        await this.ensureAccessToken();
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
        await this.ensureAccessToken();
        const gmail = google.gmail({ version: 'v1', auth: this.auth });

        const yesterday = Math.floor(new Date().setDate(new Date().getDate() - 1) / 1000);
        const now = Math.floor(Date.now() / 1000);
        const query = `after:${yesterday} before:${now} from:support@timo.vn`;

        const res = await gmail.users.messages.list({
            userId: 'me',
            q: query,
        });

        const messages = res.data.messages || [];
        this.logger.log(`Tìm thấy ${messages.length} email.`);

        if (messages.length === 0) {
            return [];
        }

        const existingEmails = await this.prisma.email.findMany({
            where: { emailId: { in: messages.map(msg => msg.id) } },
            select: { emailId: true }
        });

        const existingEmailIds = new Set(existingEmails.map(e => e.emailId));

        const newEmails = messages.filter(msg => !existingEmailIds.has(msg.id));
        this.logger.log(`Số email sẽ gửi cho bạn ${newEmails.length} email.`);


        return newEmails;
    }



    async updateTokenInDB(tokenData: any) {
        await this.prisma.oAuthToken.update({
            where: { id: '1' },
            data: {
                accessToken: tokenData.access_token,
                expiryDate: new Date(Date.now() + tokenData.expires_in * 1000)
            }
        });
        this.logger.log('Cập nhật access token trong database thành công!');
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
