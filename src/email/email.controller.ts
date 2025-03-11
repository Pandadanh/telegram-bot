import { Controller, Get, Logger } from '@nestjs/common';
import { EmailService } from './email.service';

@Controller('email')
export class EmailController {
    private readonly logger = new Logger(EmailController.name);

    constructor(private readonly emailService: EmailService) { }

    @Get('unread')
    async getUnreadEmails() {
        try {
            const emails = await this.emailService.getOAuthClient();
            return { success: true, data: emails };
        } catch (error) {
            this.logger.error('Lỗi khi lấy email chưa đọc:', error);
            return { success: false, message: 'Không thể lấy email chưa đọc', error: error.message };
        }
    }

    @Get('run-script')
    async runPythonScript() {
        try {
            const result = await this.emailService.runPythonScript();
            return { success: true, data: result };
        } catch (error) {
            return { success: false, error };
        }
    }
}
