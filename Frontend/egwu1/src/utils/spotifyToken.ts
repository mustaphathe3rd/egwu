export async function generateSpotifyWebPlaybackToken(): Promise<string> {
    try {
        const response = await fetch('/auth/token');
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Failed to obtain Spotify token:', errorText);
            throw new Error('Failed to obtain Spotify token');
        }
        const data = await response.json();
        return data.access_token;
    } catch (error) {
        console.error('Spotify token utility error:', error);
        throw error;
    }
}