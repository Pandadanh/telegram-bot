import { Module } from '@nestjs/common';
import { EmailService } from './email.service';
import { PrismaService } from '../prisma/prisma.service';
import { EmailController } from './email.controller';

@Module({
    providers: [EmailService, PrismaService],
    exports: [EmailService],
    controllers: [EmailController],
})
export class EmailModule { }
