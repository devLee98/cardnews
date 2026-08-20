import type { NextConfig } from "next";

// 배포 환경에서는 nginx 가 /api 를 백엔드로 넘기지만,
// 로컬 개발에서는 Next 가 직접 프록시해야 한다.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // 카드 구성안 생성은 AI 호출이라 30~40초가 걸린다.
    // 기본값 30초로는 응답이 오기 전에 프록시가 연결을 끊어 500이 난다.
    proxyTimeout: 120_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
