// API Configuration
export const AGENT_ID = 'crypto-analyst-agent';

// 从环境变量读取 API 地址，开发环境默认 localhost，生产环境从 .env 配置
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
