-- CreateTable
CREATE TABLE "Email" (
    "id" SERIAL NOT NULL,
    "emailId" TEXT NOT NULL,
    "expense" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Email_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Email_emailId_key" ON "Email"("emailId");
