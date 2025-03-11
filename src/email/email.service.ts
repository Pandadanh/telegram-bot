import { Injectable, Logger } from '@nestjs/common';
import { google } from 'googleapis';
import { PrismaService } from '../prisma/prisma.service';
import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';
import { Email } from './email.entity';
import { Interval } from '@nestjs/schedule';

@Injectable()
export class EmailService {
    private readonly logger = new Logger(EmailService.name);
    private readonly SCOPES = ['https://www.googleapis.com/auth/gmail.readonly'];
    private credentialsPath = path.join(__dirname, '../../credentials.json');

    constructor(private readonly prisma: PrismaService) { }

    async getOAuthClient() {
        try {
            // 🔹 Đọc file credentials.json
            const credentials = JSON.parse(fs.readFileSync(this.credentialsPath, 'utf-8'));
            const { client_secret, client_id, redirect_uris } = credentials.installed;
            const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, redirect_uris[0]);

            // 🔹 Kiểm tra token trong database
            let tokenData = await this.prisma.oAuthToken.findFirst({
                orderBy: { createdAt: 'desc' }, // Lấy token mới nhất
            });

            if (tokenData) {
                oAuth2Client.setCredentials({
                    access_token: tokenData.accessToken,
                    refresh_token: tokenData.refreshToken,
                    expiry_date: tokenData.expiryDate.getTime(),
                });

                // 🔹 Làm mới token nếu hết hạn
                if (new Date().getTime() >= tokenData.expiryDate.getTime()) {
                    this.logger.log('Token hết hạn, tiến hành làm mới...');
                    const refreshedToken = await oAuth2Client.refreshAccessToken();
                    const newToken = refreshedToken.credentials;

                    await this.prisma.oAuthToken.create({
                        data: {
                            accessToken: newToken.access_token,
                            refreshToken: newToken.refresh_token || tokenData.refreshToken, // Giữ refresh token nếu không có mới
                            expiryDate: new Date(newToken.expiry_date),
                        },
                    });

                    oAuth2Client.setCredentials(newToken);
                }
            } else {
                this.logger.warn('Không tìm thấy token OAuth, cần đăng nhập lại.');
                return await this.getNewToken(oAuth2Client);
            }

            return oAuth2Client;
        } catch (error) {
            this.logger.error('Lỗi khi lấy OAuth client:', error);
            throw error;
        }
    }

    private async getNewToken(oAuth2Client: any) {
        try {
            this.logger.log('Mở trình duyệt để xác thực...');
            const authUrl = oAuth2Client.generateAuthUrl({
                access_type: 'offline',
                scope: this.SCOPES,
            });

            console.log(`Vui lòng truy cập link này để xác thực: ${authUrl}`);

            // 🚨 Dừng lại tại đây vì cần user nhập code từ trình duyệt vào server
            throw new Error('Cần user nhập code xác thực');
        } catch (error) {
            this.logger.error('Lỗi khi lấy token mới:', error);
            throw error;
        }
    }

    @Interval(1800000) // 30 phút
    async runPythonScript(): Promise<string> {
        return new Promise((resolve, reject) => {

            const currentHour = new Date().getHours(); // Lấy giờ hiện tại

            if (currentHour >= 23 || currentHour < 6) {
                console.log("Ngoài giờ hoạt động (23h - 6h), không chạy.");
                return;
            }

            const scriptPath = path.resolve(
                'C:/Users/Admin/Desktop/word/persional/OneForAll/chi-project/PersonalFinancialManagement/telegram-bot/test.py',
            );

            const pythonProcess = spawn('python', ['-X', 'utf8', scriptPath]);

            let output = '';
            pythonProcess.stdout.on('data', (data) => {
                output += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                console.error(`Lỗi từ Python: ${data}`);
                reject(data.toString());
            });

            pythonProcess.on('close', (code) => {
                if (code === 0) {
                    resolve(output);
                } else {
                    reject(`Lỗi khi chạy script với mã lỗi: ${code}`);
                }
            });
        });
    }


    async getUnreadEmails() {
        console.log('📧 Đang lấy email chưa đọc...');
        return this.prisma.email.findFirst({
            where: { isRead: false },
            orderBy: { createdAt: 'asc' },
        });
    }


    // Hàm chuẩn hóa category: Viết hoa, bỏ dấu, thay dấu cách bằng "_"
    private normalizeCategory(text: string): string {
        const removeDiacritics = (str: string) =>
            str.normalize('NFD').replace(/[\u0300-\u036f]/g, ''); // Loại bỏ dấu tiếng Việt

        return removeDiacritics(text)
            .toUpperCase() // Chuyển thành chữ hoa
            .replace(/\s+/g, '_'); // Thay dấu cách bằng "_"
    }

    async saveEmailsReply(email: any, userMessage: string): Promise<boolean> {
        try {
            const [categoryRaw, noteExpense] = userMessage.split(' - ');
            if (!categoryRaw || !noteExpense) {
                throw new Error('⚠️ Tin nhắn không đúng định dạng. Hãy nhập: "ăn uống - đi ăn với ba mẹ"');
            }

            const category = this.normalizeCategory(categoryRaw.trim());
            const expense = noteExpense.trim();

            await this.prisma.email.update({
                where: { id: email.id },
                data: {
                    category,
                    expense,
                    isRead: true,
                },
            });

            console.log(`✅ Đã lưu chi tiêu: ${category} - ${expense}`);
            return true;
        } catch (error) {
            console.error('❌ Lỗi khi lưu chi tiêu:', error.message);
            return false;
        }
    }

    async getTotalUnreadExpense(month: number): Promise<number> {
        const currentYear = new Date().getFullYear(); // Lấy năm hiện tại
        const startDate = new Date(currentYear, month - 1, 1); // Ngày đầu tháng
        const endDate = new Date(currentYear, month, 0, 23, 59, 59); // Ngày cuối tháng

        const total = await this.prisma.email.aggregate({
            _sum: { price: true },
            where: {
                isRead: true, // Chỉ lấy email chưa đọc
                price: { lt: 0 }, // Chỉ lấy khoản chi tiêu (giảm tiền)
                createdAt: {
                    gte: startDate, // Lớn hơn hoặc bằng ngày đầu tháng
                    lte: endDate,   // Nhỏ hơn hoặc bằng ngày cuối tháng
                },
            },
        });

        return total._sum.price ?? 0; // Trả về tổng tiền, nếu null thì trả 0
    }

    async getTotal(month: number): Promise<number> {
        const currentYear = new Date().getFullYear(); // Lấy năm hiện tại
        const startDate = new Date(currentYear, month - 1, 1); // Ngày đầu tháng
        const endDate = new Date(currentYear, month, 0, 23, 59, 59); // Ngày cuối tháng

        const total = await this.prisma.email.aggregate({
            _sum: { price: true },
            where: {
                isRead: false, // Chỉ lấy email chưa đọc
                price: { gt: 0 }, // Chỉ lấy khoản chi tiêu (giảm tiền)
                createdAt: {
                    gte: startDate, // Lớn hơn hoặc bằng ngày đầu tháng
                    lte: endDate,   // Nhỏ hơn hoặc bằng ngày cuối tháng
                },
            },
        });

        return total._sum.price ?? 0; // Trả về tổng tiền, nếu null thì trả 0
    }

}
