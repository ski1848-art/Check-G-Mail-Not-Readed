# Multi-stage build for Next.js App
FROM node:22-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy package files
COPY package.json ./
RUN npm install

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Set environment variables for build (placeholders)
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXTAUTH_URL=http://placeholder
ENV NEXTAUTH_SECRET=placeholder
ENV GOOGLE_CLIENT_ID=placeholder
ENV GOOGLE_CLIENT_SECRET=placeholder
ENV FIRESTORE_PROJECT_ID=gmail-notifier-480807
ENV ALLOWED_EMAIL_DOMAIN=hotseller.co.kr
ENV ADMIN_EMAILS=ski1848@hotseller.co.kr

# Build Next.js application
RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Expose port (Cloud Run will inject PORT env var)
EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Start Next.js
CMD ["node", "server.js"]



