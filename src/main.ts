import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ConfigService } from '@nestjs/config';
import { WsAdapter } from '@nestjs/platform-ws';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);
  const port = 4000;

  // Cho phép WebSocket hoạt động
  app.useWebSocketAdapter(new WsAdapter(app));

  // Cấu hình CORS (nếu cần)
  app.enableCors({
    origin: '*',
  });

  await app.listen(port, '0.0.0.0');
  console.log(`🚀 Server is running on http://0.0.0.0:${port}`);
}
bootstrap();
