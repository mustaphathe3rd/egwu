import api from '@/services/api'

export async function generateSpotifyWebPlaybackToken(): Promise<string> {
    try {
        const response = await api.get('/playback-token/');
        if (!response.ok) {
            throw new Error('Failed to obtain Spotify playback token');
        }
        return response.data.access_token;
    } catch (error) {
        console.error('Spotify playback token error:', error);
        throw error;
    }
}