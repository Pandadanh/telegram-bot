import {
    WebSocketGateway,
    WebSocketServer,
    SubscribeMessage,
    MessageBody,
} from '@nestjs/websockets';
import { Server } from 'ws';

@WebSocketGateway(3000, { transports: ['websocket'] }) // WebSocket chạy trên cổng 3000
export class WebSocketService {
    @WebSocketServer()
    server: Server;

    @SubscribeMessage('message')
    handleMessage(@MessageBody() data: string): void {
        console.log(`Received message: ${data}`);
        this.server.clients.forEach((client) => {
            client.send(`Echo: ${data}`);
        });
    }
}
