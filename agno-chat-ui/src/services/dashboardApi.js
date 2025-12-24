import { BASE_URL } from './config';

// Dashboard API calls
export const dashboardApi = {
    async getNews() {
        try {
            const res = await fetch(`${BASE_URL}/api/dashboard/news`);
            if (res.ok) {
                const data = await res.json();
                return data.news || [];
            }
            return [];
        } catch (e) {
            console.error('[Dashboard] Failed to fetch news:', e);
            return [];
        }
    },

    async getTokens() {
        try {
            const res = await fetch(`${BASE_URL}/api/dashboard/tokens`);
            if (res.ok) {
                const data = await res.json();
                return data.tokens || [];
            }
            return [];
        } catch (e) {
            console.error('[Dashboard] Failed to fetch tokens:', e);
            return [];
        }
    },

    async getFearGreed() {
        try {
            const res = await fetch(`${BASE_URL}/api/dashboard/fear-greed`);
            if (res.ok) {
                return await res.json();
            }
            return { value: 50, classification: 'Neutral' };
        } catch (e) {
            console.error('[Dashboard] Failed to fetch fear-greed:', e);
            return { value: 50, classification: 'Neutral' };
        }
    },

    async getIndicators() {
        try {
            const res = await fetch(`${BASE_URL}/api/dashboard/indicators`);
            if (res.ok) {
                const data = await res.json();
                return data.indicators || [];
            }
            return [];
        } catch (e) {
            console.error('[Dashboard] Failed to fetch indicators:', e);
            return [];
        }
    }
};
