import type { NextConfig } from "next";

// 배포 환경에서는 nginx 가 /api 를 백엔드로 넘기지만,
// 로컬 개발에서는 Next 가 직접 프록시해야 한다.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // AI 호출이라 오래 걸린다. 기본값 30초로는 응답이 오기 전에 프록시가
    // 연결을 끊어 500이 난다.
    //
    // 가장 오래 걸리는 것은 문구 생성(/draft)이다. 카드 9~10장을 한 번에 쓰면서
    // 서로 말이 겹치지 않게 해야 해서 추론 강도가 medium 이고, 실측 120~130초다.
    // 120초로는 딱 경계에 걸쳐서 카드가 많으면 그대로 500 이 난다.
    //
    // 배포에서는 nginx 가 /api 를 백엔드로 바로 넘기므로 이 값을 타지 않는다.
    // deploy/nginx/cardnews.conf 의 proxy_read_timeout 과 함께 봐야 한다.
    proxyTimeout: 300_000,
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
