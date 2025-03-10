/*
  Warnings:

  - Added the required column `month` to the `Email` table without a default value. This is not possible if the table is not empty.
  - Added the required column `price` to the `Email` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "Email" ADD COLUMN     "month" INTEGER NOT NULL,
ADD COLUMN     "price" DOUBLE PRECISION NOT NULL;
