// API Configuration
// Agent IDs for mode switching
export const AGENT_ANALYST_ID = 'crypto-analyst-agent';
export const AGENT_TRADER_ID = 'trading-strategy-agent';
export const AGENT_SWAP_ID = 'swap-agent';  // A2UI DEX 交易 Agent
export const AGENT_ID = AGENT_ANALYST_ID; // Default, for backward compatibility

// 从环境变量读取 API 地址
// 生产环境使用空字符串（同源请求），开发环境可以通过 .env 设置
export const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

