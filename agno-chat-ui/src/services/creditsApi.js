import { BASE_URL } from './config';

// Credits API calls
export const creditsApi = {
    async getCredits(userId) {
        try {
            const res = await fetch(`${BASE_URL}/api/credits/${userId}`);
            if (res.ok) {
                const data = await res.json();
                return data.credits;
            }
            return null;
        } catch (e) {
            console.error('[Credits] Failed to fetch:', e);
            return null;
        }
    },

    async deductCredits(userId, amount) {
        try {
            const res = await fetch(`${BASE_URL}/api/credits/${userId}/deduct`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount })
            });
            if (res.ok) {
                const data = await res.json();
                return data.credits;
            }
            return null;
        } catch (e) {
            console.error('[Credits] Failed to deduct:', e);
            return null;
        }
    }
};
