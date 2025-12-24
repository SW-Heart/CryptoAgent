import { v4 as uuidv4 } from 'uuid';

// 为未登录用户生成临时 ID
export const getOrCreateTempUserId = () => {
    let tempId = localStorage.getItem('agno_temp_user_id');
    if (!tempId) {
        tempId = `temp_${uuidv4()}`;
        localStorage.setItem('agno_temp_user_id', tempId);
    }
    return tempId;
};

// Format price helper
export const formatPrice = (p) => {
    if (p >= 1000) return `$${(p / 1000).toFixed(1)}K`;
    if (p >= 1) return `$${p.toFixed(2)}`;
    return `$${p.toFixed(4)}`;
};

// Format large numbers (billions, trillions)
export const formatLargeNumber = (n) => {
    if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    return `$${n.toLocaleString()}`;
};

// Format percentage
export const formatPercent = (p) => {
    const sign = p >= 0 ? '+' : '';
    return `${sign}${p.toFixed(2)}%`;
};
