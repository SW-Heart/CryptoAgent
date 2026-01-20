// API Configuration
// Agent IDs for mode switching
export const AGENT_ANALYST_ID = 'crypto-analyst-agent';
export const AGENT_TRADER_ID = 'trading-strategy-agent';
export const AGENT_SWAP_ID = 'swap-agent';  // A2UI DEX 交易 Agent
export const AGENT_ID = AGENT_ANALYST_ID; // Default, for backward compatibility

// 从环境变量读取 API 地址，开发环境默认 localhost，生产环境从 .env 配置
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

