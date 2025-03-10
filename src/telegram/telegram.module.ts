import { Module } from '@nestjs/common';
import { TelegramService } from './telegram.service';
import { Bot } from 'grammy';
import { EmailModule } from 'src/email/email.module';
import { PrismaService } from 'src/prisma/prisma.service';

@Module({
    imports: [EmailModule],
    providers: [
        {
            provide: Bot,
            useFactory: () => {
                return new Bot(process.env.TELEGRAM_TOKEN);
            },
        },
        TelegramService,
        PrismaService
    ],
    exports: [TelegramService],
})
export class TelegramModule { }
