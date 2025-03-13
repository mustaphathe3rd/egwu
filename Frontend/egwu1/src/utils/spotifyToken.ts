export async function generateSpotifyWebPlaybackToken(): Promise<string> {
    try {
        const response = await fetch('/auth/token');
        if (!response.ok) {
            throw new Error('Failed to obtain Spotify token');
        }
        const data = await response.json();
        return data.access_token;
    } catch (error) {
        console.error('Spotify token error:', error);
        throw error;
    }
}