/** @type {import('next').NextConfig} */
// Внутри docker-compose API доступен по имени сервиса `api`; для локального запуска
// вне Docker задайте API_URL (например, API_URL=http://localhost:8000 npm run dev).
const API_TARGET = process.env.API_URL || 'http://api:8000';

const nextConfig = {
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${API_TARGET}/:path*` }];
  },
};

module.exports = nextConfig;
