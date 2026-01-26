import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  callbacks: {
    async signIn({ user }) {
      console.log("로그인 시도 유저:", user.email);
      if (!user.email) {
        console.error("이메일 정보가 없습니다.");
        return false;
      }

      const allowedDomain = process.env.ALLOWED_EMAIL_DOMAIN;
      const adminEmails = process.env.ADMIN_EMAILS?.split(",").map(e => e.trim()) || [];
      
      console.log("허용 도메인:", allowedDomain);
      console.log("관리자 리스트:", adminEmails);

      // Check domain
      if (allowedDomain && user.email.endsWith(`@${allowedDomain}`)) {
        console.log("도메인 일치로 로그인 허용");
        return true;
      }

      // Check allowlist
      if (adminEmails.includes(user.email)) {
        console.log("관리자 리스트 일치로 로그인 허용");
        return true;
      }

      console.error("권한이 없는 이메일입니다:", user.email);
      return false;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
});

export { handler as GET, handler as POST };
