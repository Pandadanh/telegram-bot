import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn } from 'typeorm';

@Entity()
export class Email {
    @PrimaryGeneratedColumn()
    id: number;

    @Column()
    emailId: string;

    @Column()
    expense: string;

    @CreateDateColumn()
    createdAt: Date;

    @Column()
    month: number;

    @Column('double precision')
    price: number;

    @Column({ default: false })
    isRead: boolean;

    @Column({ default: 'Others' })
    category: string;

    @Column({ nullable: true })
    note: string;
}
