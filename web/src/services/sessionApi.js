import { BASE_URL } from './config';

// Session management API calls
export const sessionApi = {
    async getSessions(userId) {
        try {
            console.log(`[Sessions] Fetching for user: ${userId}`);
            const res = await fetch(`${BASE_URL}/api/sessions?user_id=${userId}`);
            if (res.ok) {
                const data = await res.json();
                console.log(`[Sessions] Loaded ${data.sessions?.length || 0} sessions`);
                return data.sessions || [];
            }
            console.error('[Sessions] API error:', res.status);
            return null; // Return null on error to trigger retry
        } catch (e) {
            console.error('[Sessions] Failed to fetch:', e);
            return null;
        }
    },

    async getHistory(sessionId) {
        try {
            const res = await fetch(`${BASE_URL}/api/history?session_id=${sessionId}`);
            if (res.ok) {
                return await res.json();
            }
            return { messages: [] };
        } catch (e) {
            console.error('[Sessions] Failed to fetch history:', e);
            return { messages: [] };
        }
    },

    async renameSession(sessionId, newTitle) {
        try {
            const res = await fetch(`${BASE_URL}/api/session/${sessionId}/rename`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle })
            });
            return res.ok;
        } catch (e) {
            console.error('[Sessions] Failed to rename:', e);
            return false;
        }
    },

    async deleteSession(sessionId) {
        try {
            const res = await fetch(`${BASE_URL}/api/session/${sessionId}`, {
                method: 'DELETE'
            });
            return res.ok;
        } catch (e) {
            console.error('[Sessions] Failed to delete:', e);
            return false;
        }
    }
};
