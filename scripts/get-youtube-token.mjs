#!/usr/bin/env node
/**
 * Get YouTube OAuth Refresh Token
 * Run: node scripts/get-youtube-token.mjs
 *
 * Steps:
 * 1. Opens authorization URL in browser (or shows it)
 * 2. You approve access to your YouTube account
 * 3. Paste the "code" from redirect URL
 * 4. Script prints your REFRESH_TOKEN — paste it in .env
 */
import { createInterface } from 'readline';
import { readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const envPath = resolve(__dir, '../.env');

// Load .env
function loadEnv() {
  const lines = readFileSync(envPath, 'utf8').split('\n');
  const env = {};
  for (const line of lines) {
    const m = line.match(/^([^#=]+)=(.*)$/);
    if (m) env[m[1].trim()] = m[2].trim();
  }
  return env;
}

// Update .env with new value
function updateEnv(key, value) {
  let content = readFileSync(envPath, 'utf8');
  const regex = new RegExp(`^#?\\s*${key}=.*$`, 'm');
  if (regex.test(content)) {
    content = content.replace(regex, `${key}=${value}`);
  } else {
    content += `\n${key}=${value}\n`;
  }
  writeFileSync(envPath, content);
}

const env = loadEnv();
const CLIENT_ID = env.YOUTUBE_CLIENT_ID;
const CLIENT_SECRET = env.YOUTUBE_CLIENT_SECRET;

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error('❌ YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET not found in .env');
  process.exit(1);
}

const SCOPES = [
  'https://www.googleapis.com/auth/youtube.upload',
  'https://www.googleapis.com/auth/youtube',
  'https://www.googleapis.com/auth/youtube.readonly',
].join(' ');

const REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob';

const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
authUrl.searchParams.set('client_id', CLIENT_ID);
authUrl.searchParams.set('redirect_uri', REDIRECT_URI);
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('scope', SCOPES);
authUrl.searchParams.set('access_type', 'offline');
authUrl.searchParams.set('prompt', 'consent');

console.log('\n═══════════════════════════════════════════════════');
console.log('   YouTube OAuth — Получение Refresh Token');
console.log('═══════════════════════════════════════════════════\n');
console.log('1. Открой эту ссылку в браузере:\n');
console.log(authUrl.toString());
console.log('\n2. Войди в Google аккаунт и разреши доступ к YouTube');
console.log('3. Скопируй "код подтверждения" (код авторизации)\n');

const rl = createInterface({ input: process.stdin, output: process.stdout });

rl.question('Вставь код авторизации сюда: ', async (code) => {
  rl.close();
  code = code.trim();

  if (!code) {
    console.error('❌ Код не введён');
    process.exit(1);
  }

  console.log('\nОбмениваю код на токены...');

  try {
    const response = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET,
        redirect_uri: REDIRECT_URI,
        grant_type: 'authorization_code',
      }),
    });

    const data = await response.json();

    if (data.error) {
      console.error('❌ Ошибка:', data.error_description || data.error);
      process.exit(1);
    }

    const { refresh_token, access_token } = data;

    if (!refresh_token) {
      console.error('❌ Refresh token не получен. Попробуй снова — убедись что consent=prompt');
      process.exit(1);
    }

    console.log('\n✅ Токены получены!\n');
    console.log(`REFRESH_TOKEN: ${refresh_token}\n`);

    // Auto-save to .env
    updateEnv('YOUTUBE_REFRESH_TOKEN', refresh_token);
    console.log('✅ YOUTUBE_REFRESH_TOKEN автоматически сохранён в .env');
    console.log('\nСистема готова к загрузке видео на YouTube!');
    console.log('Запусти: bash scripts/start-content-automation.sh\n');

  } catch (err) {
    console.error('❌ Ошибка запроса:', err.message);
    process.exit(1);
  }
});
