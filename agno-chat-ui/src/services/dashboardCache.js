/**
 * Dashboard数据缓存服务
 * 
 * 功能：
 * 1. localStorage持久化缓存
 * 2. 智能缓存过期策略
 * 3. 先显示缓存，后台静默刷新
 * 4. 缓存版本控制
 */

const CACHE_VERSION = 'v1';
const CACHE_PREFIX = `dashboard_cache_${CACHE_VERSION}_`;

// 缓存配置（毫秒）
const CACHE_CONFIG = {
    news: {
        key: 'news',
        ttl: 10 * 60 * 1000,      // 10分钟有效期
        staleWhileRevalidate: 60 * 60 * 1000,  // 1小时内可以使用过期数据
    },
    tokens: {
        key: 'tokens',
        ttl: 60 * 1000,           // 1分钟有效期
        staleWhileRevalidate: 5 * 60 * 1000,   // 5分钟内可以使用过期数据
    },
    fearGreed: {
        key: 'fearGreed',
        ttl: 30 * 60 * 1000,      // 30分钟有效期
        staleWhileRevalidate: 2 * 60 * 60 * 1000, // 2小时内可以使用过期数据
    },
    indicators: {
        key: 'indicators',
        ttl: 5 * 60 * 1000,       // 5分钟有效期
        staleWhileRevalidate: 30 * 60 * 1000,  // 30分钟内可以使用过期数据
    },
    trending: {
        key: 'trending',
        ttl: 5 * 60 * 1000,       // 5分钟有效期
        staleWhileRevalidate: 15 * 60 * 1000,  // 15分钟内可以使用过期数据
    },
    onchainHot: {
        key: 'onchainHot',
        ttl: 10 * 60 * 1000,      // 10分钟有效期
        staleWhileRevalidate: 30 * 60 * 1000,  // 30分钟内可以使用过期数据
    },
};

/**
 * 获取缓存数据
 * @param {string} type - 缓存类型（news, tokens, fearGreed, indicators, trending）
 * @returns {object|null} - { data, isStale, isFresh }
 */
export function getCache(type) {
    const config = CACHE_CONFIG[type];
    if (!config) return null;

    try {
        const raw = localStorage.getItem(`${CACHE_PREFIX}${config.key}`);
        if (!raw) return null;

        const { data, timestamp } = JSON.parse(raw);
        const age = Date.now() - timestamp;

        // 完全过期（超过staleWhileRevalidate）
        if (age > config.staleWhileRevalidate) {
            return null;
        }

        // 判断是否新鲜或过期但可用
        const isFresh = age < config.ttl;
        const isStale = !isFresh;

        return { data, isFresh, isStale, age };
    } catch (e) {
        console.warn(`[DashboardCache] Failed to read cache for ${type}:`, e);
        return null;
    }
}

/**
 * 设置缓存数据
 * @param {string} type - 缓存类型
 * @param {any} data - 要缓存的数据
 */
export function setCache(type, data) {
    const config = CACHE_CONFIG[type];
    if (!config) return;

    try {
        const cacheData = {
            data,
            timestamp: Date.now(),
        };
        localStorage.setItem(`${CACHE_PREFIX}${config.key}`, JSON.stringify(cacheData));
    } catch (e) {
        console.warn(`[DashboardCache] Failed to write cache for ${type}:`, e);
        // 如果localStorage满了，清理旧缓存
        clearOldCaches();
    }
}

/**
 * 清理所有Dashboard缓存
 */
export function clearAllCaches() {
    try {
        Object.keys(localStorage).forEach(key => {
            if (key.startsWith('dashboard_cache_')) {
                localStorage.removeItem(key);
            }
        });
        console.log('[DashboardCache] All caches cleared');
    } catch (e) {
        console.warn('[DashboardCache] Failed to clear caches:', e);
    }
}

/**
 * 清理旧版本缓存
 */
function clearOldCaches() {
    try {
        Object.keys(localStorage).forEach(key => {
            if (key.startsWith('dashboard_cache_') && !key.startsWith(CACHE_PREFIX)) {
                localStorage.removeItem(key);
            }
        });
    } catch (e) {
        // ignore
    }
}

/**
 * 获取所有缓存的Dashboard数据
 * 用于首屏快速渲染
 * @returns {object} - { news, tokens, fearGreed, indicators, trending }
 */
export function getAllCachedData() {
    const result = {
        news: null,
        tokens: null,
        fearGreed: null,
        indicators: null,
        trending: null,
        hasAnyData: false,
        needsRefresh: [],
    };

    Object.keys(CACHE_CONFIG).forEach(type => {
        const cached = getCache(type);
        if (cached) {
            result[type] = cached.data;
            result.hasAnyData = true;
            if (cached.isStale) {
                result.needsRefresh.push(type);
            }
        } else {
            result.needsRefresh.push(type);
        }
    });

    return result;
}

/**
 * 获取缓存统计信息（调试用）
 */
export function getCacheStats() {
    const stats = {};
    Object.keys(CACHE_CONFIG).forEach(type => {
        const cached = getCache(type);
        if (cached) {
            stats[type] = {
                isFresh: cached.isFresh,
                ageSeconds: Math.round(cached.age / 1000),
            };
        } else {
            stats[type] = { missing: true };
        }
    });
    return stats;
}

// 导出配置供调试
export { CACHE_CONFIG };
