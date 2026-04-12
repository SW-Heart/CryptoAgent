import { BASE_URL } from './config';

async function request(path, options = {}) {
    const response = await fetch(`${BASE_URL}${path}`, options);

    if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Request failed: ${response.status}`);
    }

    // Some DELETE responses might be 204 No Content
    if (response.status === 204) return null;

    return response.json();
}

export function getJson(path) {
    return request(path);
}

export function postJson(path, body) {
    return request(path, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
    });
}

export function putJson(path, body) {
    return request(path, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
    });
}

export function deleteJson(path) {
    return request(path, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        },
    });
}

export function uploadFile(path, file) {
    const formData = new FormData();
    formData.append('file', file);
    return request(path, {
        method: 'POST',
        body: formData,
    });
}
