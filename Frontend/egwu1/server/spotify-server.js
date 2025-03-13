import express from 'express';
import dotenv, { configDotenv } from 'dotenv';
import request from 'request';

let access_token = '';
const port = 5000;

dotenv.config();

const spotify_client_id = process.env.CLIENT_ID;
const spotify_client_secret = process.env.CLIENT_SECRET;

const app = express();

const generateRandomString = (length) => {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

    for (let i = 0; i < length; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}

app.get('/', (req, res) => {
    res.send('Server is running');
});

app.get('/auth/login', (req, res) => {
    const scope = "streaming \
    user-read-email \
    user-read-private \
    user-modify-playback-state";

    const state = generateRandomString(16);

    const auth_query_parameters = new URLSearchParams({
        response_type: "code",
        client_id: spotify_client_id,
        scope: scope,
        redirect_uri: "http://localhost:5173/auth/callback",
        state: state
    });

    res.redirect('https://accounts.spotify.com/authorize/?' + auth_query_parameters.toString());
});

app.get('/auth/callback', (req,res) => {
    const code = req.query.code;

    const authOptions = {
        url: 'https://accounts.spotify.com/api/token',
        form: {
            code: code,
            redirect_uri: "http://localhost:5173/auth/callback",
            grant_type: "authorization_code"
        },
        headers: {
            'Authorization': 'Basic ' + (Buffer.from(spotify_client_id + ':' + spotify_client_secret).toString('base64')),
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        json: true
    };

    request.post(authOptions, function(error, response, body) {
        if(!error && response.statusCode === 200) {
            access_token = body.access_token;
            res.redirect('/');
        }
    });
});

app.get('/auth/token', (req, res) => {
    res.json({ access_token: access_token });
});

app.listen(port, () => {
    console.log(`Server is running on port ${port}`);
});