/**
 * WhatsApp Web Service - FINAL PRODUCTION VERSION
 * הגדרות מותאמות:
 * - וידאו: תמיד צפייה ישירה (דחיסה מעל 40MB)
 * - אודיו: דחיסה מדורגת (קלה/אגרסיבית) לפי הגודל
 */

const express = require('express');
const cors = require('cors');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs').promises; 
const fsSync = require('fs');      
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');
const { execSync } = require('child_process'); 

// ============================================
// ⚙️ הגדרות ותנאים (Configuration)
// ============================================

const CONFIG = {
    // גבולות כלליים
    NO_COMPRESSION_LIMIT_MB: 70,   // עד 70MB שולחים מקור (גבול WhatsApp למעשה)
    MAX_INPUT_SIZE_MB: 700,        // קבצים מעל זה ייחסמו מיידית (למניעת תקיעת שרת)
    
    // הגדרות וידאו (FFmpeg)
    VIDEO_CRF: 28,               // איכות (נמוך=איכותי יותר, גבוה=דחוס יותר. 28 זה הממוצע המומלץ)
    VIDEO_PRESET: 'fast',        // איזון בין מהירות עיבוד לגודל קובץ
    
    // הגדרות אודיו מדורגות
    AUDIO_TIER_1_LIMIT_MB: 70,    // עד 70MB: דחיסה קלה, מעל 70MB: דחיסה אגרסיבית
    AUDIO_BITRATE_LIGHT: '128k',  // איכות טובה
    AUDIO_BITRATE_HEAVY: '64k',   // איכות רדיו (לקבצים מעל 70MB)
    
    // זמנים
    TIMEOUT_PROCESSING_SEC: 1200, // 20 דקות (נותן זמן לקבצים ענקיים של 250MB+)
    
    LOG_VERBOSE: true
};

// ============================================
// 📝 לוגים (Logging)
// ============================================

function log(emoji, message, data = null) {
    let output = `${emoji} ${message}`;
    if (data && CONFIG.LOG_VERBOSE) {
        if (data.fileData) data.fileData = '[BASE64 DATA]';
        output += `\n   ${JSON.stringify(data, null, 2)}`;
    }
    console.log(output);
}

function logError(message, error, data = null) {
    console.error(`❌ ${message}`);
    if (error) {
        console.error(`   Error: ${error.message || error}`);
        if (error.stack && CONFIG.LOG_VERBOSE) {
            console.error(`   Stack: ${error.stack}`);
        }
    }
    if (data && CONFIG.LOG_VERBOSE) {
        console.error(`   Data: ${JSON.stringify(data, null, 2)}`);
    }
}

function logSuccess(message, data = null) {
    log('✅', message, data);
}

// ============================================
// 🚀 אתחול הבוט (Initialization)
// ============================================

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

let client = null;
let isReady = false;
let qrCodeData = null;

function initializeWhatsApp() {
    log('🚀', 'Initializing WhatsApp Client...');
    
    // ניקוי client קודם אם קיים
    if (client) {
        try {
            client.destroy();
        } catch (e) {
            log('⚠️', 'Error destroying previous client', { error: e.message });
        }
        client = null;
    }
    
    try {
        client = new Client({
            authStrategy: new LocalAuth({
                clientId: 'bot-session',
                dataPath: './whatsapp_auth'
            }),
            // תיקון לשגיאת Evaluation Failed
            webVersionCache: {
                type: 'remote',
                remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.2412.54.html',
            },
            puppeteer: {
                headless: true,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-blink-features=AutomationControlled'
                ]
            }
        });

        client.on('qr', (qr) => {
            log('📱', 'QR Code received');
            qrcode.generate(qr, { small: true });
            qrCodeData = qr;
            isReady = false;
        });

        client.on('ready', () => {
            logSuccess('WhatsApp Client is ready!');
            isReady = true;
            qrCodeData = null;
        });

        client.on('authenticated', () => {
            logSuccess('Authenticated!');
        });

        client.on('disconnected', (reason) => {
            logError('WhatsApp client disconnected', null, { reason });
            isReady = false;
            // ניסיון לאתחל מחדש אחרי 5 שניות
            setTimeout(() => {
                log('🔄', 'Attempting to reinitialize WhatsApp client...');
                initializeWhatsApp();
            }, 5000);
        });

        client.on('auth_failure', (msg) => {
            logError('Authentication failed', null, { message: msg });
            isReady = false;
        });

        // טיפול בשגיאות באתחול
        client.on('loading_screen', (percent, message) => {
            log('⏳', `Loading: ${percent}% - ${message}`);
        });

        // אתחול עם טיפול בשגיאות
        client.initialize().catch((error) => {
            logError('Failed to initialize WhatsApp client', error);
            isReady = false;
            
            // אם זו שגיאת Protocol, נסה לנקות session ולאתחל מחדש
            if (error.message && error.message.includes('Protocol error')) {
                log('⚠️', 'Protocol error detected - this might be due to a corrupted session');
                log('💡', 'Try deleting the whatsapp_auth folder and restarting the server');
                log('💡', 'Or wait a few seconds and the server will attempt to reinitialize...');
                
                // ניסיון לאתחל מחדש אחרי 10 שניות
                setTimeout(() => {
                    log('🔄', 'Attempting to reinitialize after Protocol error...');
                    initializeWhatsApp();
                }, 10000);
            }
        });
    } catch (error) {
        logError('Error creating WhatsApp client', error);
        isReady = false;
        
        // ניסיון לאתחל מחדש אחרי 10 שניות
        setTimeout(() => {
            log('🔄', 'Attempting to reinitialize after error...');
            initializeWhatsApp();
        }, 10000);
    }
}

// ============================================
// 🛠️ מנוע הדחיסה החכם (Smart Engine)
// ============================================

function getFileSizeMB(filePath) {
    const stats = fsSync.statSync(filePath);
    return stats.size / (1024 * 1024);
}

/**
 * בודק אם קובץ וידאו הוא בפורמט תואם (H.264 + AAC)
 * @param {string} filePath - נתיב לקובץ
 * @returns {Promise<{isCompatible: boolean, videoCodec: string, audioCodec: string, needsConversion: boolean}>}
 */
async function checkVideoFormat(filePath) {
    try {
        const ext = path.extname(filePath).toLowerCase();
        
        // רק קבצי וידאו
        if (!['.mp4', '.mov', '.avi', '.mkv'].includes(ext)) {
            return { isCompatible: true, videoCodec: '', audioCodec: '', needsConversion: false };
        }
        
        // בדיקת קודק וידאו
        let videoCodec = '';
        try {
            const videoOutput = execSync(
                'ffprobe', [
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=codec_name,codec_tag_string',
                    '-of', 'default=noprint_wrappers=1',
                    filePath
                ],
                { encoding: 'utf-8', timeout: 10000 }
            );
            
            for (const line of videoOutput.split('\n')) {
                if (line.startsWith('codec_name=')) {
                    videoCodec = line.split('=')[1].trim().toLowerCase();
                }
            }
        } catch (e) {
            log('⚠️', `Could not check video codec: ${e.message}`);
            // אם לא הצלחנו לבדוק, נניח שצריך המרה
            return { isCompatible: false, videoCodec: 'unknown', audioCodec: 'unknown', needsConversion: true };
        }
        
        // בדיקת קודק אודיו
        let audioCodec = '';
        try {
            const audioOutput = execSync(
                'ffprobe', [
                    '-v', 'error',
                    '-select_streams', 'a:0',
                    '-show_entries', 'stream=codec_name,codec_tag_string',
                    '-of', 'default=noprint_wrappers=1',
                    filePath
                ],
                { encoding: 'utf-8', timeout: 10000 }
            );
            
            for (const line of audioOutput.split('\n')) {
                if (line.startsWith('codec_name=')) {
                    audioCodec = line.split('=')[1].trim().toLowerCase();
                }
            }
        } catch (e) {
            // אם אין אודיו, זה בסדר (וידאו אילם)
            audioCodec = 'none';
        }
        
        // בדיקה אם תואם H.264 + AAC
        const isH264 = videoCodec === 'h264' || videoCodec.startsWith('avc');
        const isAAC = audioCodec === 'aac' || audioCodec.includes('mp4a') || audioCodec === 'none';
        
        const isCompatible = isH264 && isAAC;
        
        if (!isCompatible) {
            log('⚠️', `Video format not compatible: video=${videoCodec}, audio=${audioCodec}. Will convert to H.264+AAC.`);
        } else {
            log('✅', `Video format compatible: H.264 + ${audioCodec === 'none' ? 'no audio' : 'AAC'}`);
        }
        
        return {
            isCompatible,
            videoCodec,
            audioCodec,
            needsConversion: !isCompatible
        };
        
    } catch (error) {
        log('⚠️', `Error checking video format: ${error.message}. Will attempt conversion.`);
        return { isCompatible: false, videoCodec: 'unknown', audioCodec: 'unknown', needsConversion: true };
    }
}

/**
 * ממיר וידאו לפורמט תואם (H.264 + AAC)
 * @param {string} inputPath - נתיב קלט
 * @param {string} outputPath - נתיב פלט
 * @returns {Promise<boolean>}
 */
function convertToCompatibleFormat(inputPath, outputPath) {
    return new Promise((resolve, reject) => {
        log('🔄', `Converting video to H.264+AAC format...`);
        
        ffmpeg(inputPath)
            .videoCodec('libx264')
            .audioCodec('aac')
            .audioBitrate('128k')
            .outputOptions([
                '-preset fast',
                '-crf 23',
                '-movflags +faststart'
            ])
            .output(outputPath)
            .on('end', () => {
                logSuccess(`Video converted successfully!`);
                resolve(true);
            })
            .on('error', (err) => {
                logError('Video conversion failed', err);
                reject(err);
            })
            .run();
    });
}

async function processMediaIfNeeded(inputPath) {
    return new Promise(async (resolve, reject) => {
        const sizeMB = getFileSizeMB(inputPath);
        const ext = path.extname(inputPath).toLowerCase();
        const dir = path.dirname(inputPath);

        // 1. הגנה מפני קבצים מפלצתיים
        if (sizeMB > CONFIG.MAX_INPUT_SIZE_MB) {
            return reject(new Error(`File too large (${sizeMB.toFixed(2)}MB). Max limit is ${CONFIG.MAX_INPUT_SIZE_MB}MB.`));
        }
        
        // 2. קבצים קטנים - אין צורך בנגיעה (עד NO_COMPRESSION_LIMIT_MB)
        if (sizeMB <= CONFIG.NO_COMPRESSION_LIMIT_MB) {
            log('✨', `File size (${sizeMB.toFixed(2)}MB) is safe (≤${CONFIG.NO_COMPRESSION_LIMIT_MB}MB). Sending original.`);
            return resolve({ processedPath: inputPath, isTemp: false });
        }

        log('🔨', `File is large (${sizeMB.toFixed(2)}MB). Starting optimization...`);

        // ============================
        // 🎵 טיפול באודיו (MP3/WAV)
        // ============================
        if (ext === '.mp3' || ext === '.wav' || ext === '.m4a') {
            const tempName = `temp_audio_${Date.now()}.mp3`;
            const outputPath = path.join(dir, tempName);
            
            // החלטה על רמת דחיסה
            let targetBitrate = CONFIG.AUDIO_BITRATE_LIGHT; // ברירת מחדל: 128k
            
            if (sizeMB > CONFIG.AUDIO_TIER_1_LIMIT_MB) {
                targetBitrate = CONFIG.AUDIO_BITRATE_HEAVY; // מעל 70MB: יורדים ל-64k
                log('📉', `Audio > ${CONFIG.AUDIO_TIER_1_LIMIT_MB}MB. Using aggressive compression (${targetBitrate}).`);
            } else {
                log('🔉', `Audio ≤ ${CONFIG.AUDIO_TIER_1_LIMIT_MB}MB. Using light compression (${targetBitrate}).`);
            }

            ffmpeg(inputPath)
                .outputOptions([
                    `-b:a ${targetBitrate}`, 
                    '-map 0:a:0', // רק אודיו
                    '-ac 2'       // סטריאו
                ])
                .output(outputPath)
                .on('end', () => {
                    const newSize = getFileSizeMB(outputPath);
                    logSuccess(`Audio processed! ${sizeMB.toFixed(2)}MB -> ${newSize.toFixed(2)}MB`);
                    resolve({ processedPath: outputPath, isTemp: true });
                })
                .on('error', (err) => reject(err))
                .run();
        }
        
        // ============================
        // 🎬 טיפול בוידאו (MP4/MOV)
        // ============================
        else if (ext === '.mp4' || ext === '.mov' || ext === '.avi' || ext === '.mkv') {
            // שלב 1: בדיקת פורמט והמרה אם נדרש
            const formatCheck = await checkVideoFormat(inputPath);
            let videoToProcess = inputPath;
            let needsCleanup = false;
            
            if (formatCheck.needsConversion) {
                log('🔄', 'Video format not compatible, converting to H.264+AAC first...');
                const convertedName = `temp_converted_${Date.now()}.mp4`;
                const convertedPath = path.join(dir, convertedName);
                
                try {
                    await convertToCompatibleFormat(inputPath, convertedPath);
                    videoToProcess = convertedPath;
                    needsCleanup = true;
                    log('✅', 'Format conversion completed, proceeding with compression...');
                } catch (err) {
                    log('⚠️', `Format conversion failed, proceeding with original file: ${err.message}`);
                    // נמשיך עם הקובץ המקורי
                }
            }
            
            const tempName = `temp_video_${Date.now()}.mp4`;
            const outputPath = path.join(dir, tempName);
            
            log('🎬', `Compressing video to fit WhatsApp limits (target: ≤${CONFIG.NO_COMPRESSION_LIMIT_MB}MB)...`);

            // פונקציה רקורסיבית לדחיסה עד שהקובץ קטן מ-70MB
            // מספר סוגי המרה מראש: 3 רמות דחיסה
            const compressionLevels = [
                { crf: 28, scale: 'min(1280,iw)', name: 'Level 1 (CRF 28, 1280px)' },
                { crf: 32, scale: 'min(960,iw)', name: 'Level 2 (CRF 32, 960px)' },
                { crf: 35, scale: 'min(720,iw)', name: 'Level 3 (CRF 35, 720px)' }
            ];
            
            const compressVideo = (inputPath, outputPath, attempt = 1, maxAttempts = 3) => {
                // בחירת רמת דחיסה לפי ניסיון
                const level = compressionLevels[attempt - 1] || compressionLevels[compressionLevels.length - 1];
                const crf = level.crf;
                const scale = level.scale;
                
                log('📉', `Compression attempt ${attempt}/${maxAttempts}: ${level.name}`);

                ffmpeg(inputPath)
                    .outputOptions([
                        `-crf ${crf}`,
                        `-preset ${CONFIG.VIDEO_PRESET}`,
                        `-vf scale='${scale}':-2`, // הקטנה לפי ניסיון
                        '-c:v libx264',
                        '-c:a aac',
                        '-b:a 96k', // אודיו יותר דחוס
                        '-movflags +faststart' // קריטי לצפייה ישירה
                    ])
                    .output(outputPath)
                    .on('end', () => {
                        const newSize = getFileSizeMB(outputPath);
                        logSuccess(`Video processed (attempt ${attempt})! ${sizeMB.toFixed(2)}MB -> ${newSize.toFixed(2)}MB`);
                        
                        // בדיקה אם הקובץ קטן מ-NO_COMPRESSION_LIMIT_MB
                        if (newSize <= CONFIG.NO_COMPRESSION_LIMIT_MB) {
                            logSuccess(`✅ Video is now under ${CONFIG.NO_COMPRESSION_LIMIT_MB}MB limit!`);
                            // ניקוי קובץ המרה אם היה
                            if (needsCleanup && videoToProcess !== inputPath) {
                                fs.unlink(videoToProcess).catch(() => {});
                            }
                            resolve({ processedPath: outputPath, isTemp: true });
                        } else if (attempt < maxAttempts) {
                            // עדיין גדול - ננסה שוב עם דחיסה יותר אגרסיבית
                            log('⚠️', `Video still too large (${newSize.toFixed(2)}MB > ${CONFIG.NO_COMPRESSION_LIMIT_MB}MB), trying more aggressive compression...`);
                            const nextOutputPath = path.join(dir, `temp_video_${Date.now()}_attempt${attempt + 1}.mp4`);
                            // מחיקה של הקובץ הקודם
                            fs.unlink(outputPath).catch(() => {});
                            compressVideo(videoToProcess, nextOutputPath, attempt + 1, maxAttempts);
                        } else {
                            // הגענו למקסימום ניסיונות - נשלח את הקובץ הדחוס ביותר
                            log('⚠️', `Video still ${newSize.toFixed(2)}MB after ${maxAttempts} attempts. Sending best compressed version.`);
                            // ניקוי קובץ המרה אם היה
                            if (needsCleanup && videoToProcess !== inputPath) {
                                fs.unlink(videoToProcess).catch(() => {});
                            }
                            resolve({ processedPath: outputPath, isTemp: true });
                        }
                    })
                    .on('error', (err) => reject(err))
                    .run();
            };

            compressVideo(videoToProcess, outputPath);
        } 
        
        // ============================
        // ❓ אחר
        // ============================
        else {
            log('⚠️', 'Unknown file type, skipping compression.');
            resolve({ processedPath: inputPath, isTemp: false });
        }
    });
}

// ============================================
// 📤 לוגיקת השליחה (Sending Logic)
// ============================================

async function sendAsMedia(chat, filePath, caption) {
    const fileSizeMB = getFileSizeMB(filePath);
    log('📤', `Uploading: ${path.basename(filePath)} (${fileSizeMB.toFixed(2)}MB)`);
    
    try {
        // בדיקה אם ה-client עדיין פעיל
        if (!isReady || !client) {
            throw new Error('WhatsApp client not ready or disconnected');
        }
        
        const fileData = fsSync.readFileSync(filePath, { encoding: 'base64' });
        
        let mimetype = 'application/octet-stream';
        const ext = path.extname(filePath).toLowerCase();
        
        // מיפוי MIME
        if (ext === '.mp4') mimetype = 'video/mp4';
        else if (ext === '.mov') mimetype = 'video/quicktime';
        else if (ext === '.mp3') mimetype = 'audio/mpeg';
        else if (ext === '.wav') mimetype = 'audio/wav';
        else if (ext === '.jpg') mimetype = 'image/jpeg';
        else if (ext === '.png') mimetype = 'image/png';
        
        log('📋', `MIME type: ${mimetype}, File size: ${(fileData.length / 1024 / 1024).toFixed(2)}MB (base64)`);
        
        const media = new MessageMedia(mimetype, fileData, path.basename(filePath));
        
        const options = {
            caption: caption || ''
        };

        // --- התיקון כאן ---
        if (mimetype.startsWith('video/')) {
            // וידאו: אנחנו רוצים צפייה ישירה
            options.sendMediaAsDocument = false; 
            log('🎬', 'Sending video as media (direct playback)');
        } else if (mimetype.startsWith('audio/')) {
            // אודיו: חובה לשלוח כמסמך כדי למנוע קריסה בקבצים מעל 10MB
            options.sendMediaAsDocument = true;
            log('🎵', 'Sending audio as document');
        } else {
            log('📄', 'Sending as document');
        }
        // ------------------
        
        await chat.sendMessage(media, options);
        logSuccess(`File uploaded successfully! (${fileSizeMB.toFixed(2)}MB)`);
        return { success: true, method: 'media' };
        
    } catch (error) {
        const errorMsg = error.message || String(error);
        logError('Upload failed', error, { 
            file: path.basename(filePath), 
            sizeMB: fileSizeMB.toFixed(2),
            errorType: errorMsg.includes('detached') ? 'DETACHED_FRAME' : 
                      errorMsg.includes('Target closed') ? 'TARGET_CLOSED' : 
                      errorMsg.includes('BROWSER_CRASH') ? 'BROWSER_CRASH' : 'UNKNOWN'
        });
        
        if (errorMsg.includes('Target closed') || errorMsg.includes('detached Frame') || errorMsg === 't') {
            throw new Error('BROWSER_CRASH_FILE_TOO_LARGE');
        }
        throw error;
    }
}

async function deliverFile(fileInfo) {
    const { file_path, wa_chat_id, template_payload = '' } = fileInfo;
    let currentFilePath = file_path;
    let isTempFile = false;

    log('═'.repeat(60));
    log('📥', `Received: ${path.basename(file_path)}`);
    
    try {
        if (!isReady || !client) throw new Error('WhatsApp client not ready');

        // 🟢 שלב העיבוד (דחיסה חכמה) - לפני getChats כדי למנוע detached Frame
        // לוגיקה: עד NO_COMPRESSION_LIMIT_MB לא לדחוס, מעל לדחוס, אם העלאה נכשלת - לדחוס עוד
        const fileSizeMB = getFileSizeMB(file_path);
        log('ℹ️', `Original file size: ${fileSizeMB.toFixed(2)}MB`);
        
        // עד NO_COMPRESSION_LIMIT_MB - לא לדחוס
        if (fileSizeMB <= CONFIG.NO_COMPRESSION_LIMIT_MB) {
            currentFilePath = file_path;
            isTempFile = false;
            log('✨', `File size (${fileSizeMB.toFixed(2)}MB) is safe (≤${CONFIG.NO_COMPRESSION_LIMIT_MB}MB). No compression needed.`);
        } else {
            // מעל NO_COMPRESSION_LIMIT_MB - לדחוס
            log('⚠️', `File too large (${fileSizeMB.toFixed(2)}MB > ${CONFIG.NO_COMPRESSION_LIMIT_MB}MB), compressing to ≤${CONFIG.NO_COMPRESSION_LIMIT_MB}MB...`);
            const processedResult = await processMediaIfNeeded(file_path);
            currentFilePath = processedResult.processedPath;
            isTempFile = processedResult.isTemp;
        }
        
        const processedSizeMB = getFileSizeMB(currentFilePath);
        log('ℹ️', `Processed file size: ${processedSizeMB.toFixed(2)}MB`);

        // מציאת צ'אט עם retry logic
        let chat = null;
        let getChatsError = null;
        let resolvedChatId = wa_chat_id;
        
        // 1. בדיקה אם זה "הסטטוס שלי"
        if (wa_chat_id === "הסטטוס שלי") {
            resolvedChatId = 'status@broadcast';
            log('📱', 'Detected "הסטטוס שלי" - using status@broadcast');
        }
        // 2. בדיקה אם זה מספר בינלאומי (מתחיל ב-+ ואחריו ספרות)
        else if (/^\+[0-9]+$/.test(wa_chat_id)) {
            // הסרת ה-+ והוספת @c.us
            resolvedChatId = wa_chat_id.substring(1) + '@c.us';
            log('📞', `Detected international number: ${wa_chat_id} → ${resolvedChatId}`);
        }
        
        for (let retry = 0; retry < 3; retry++) {
            try {
                // בדיקה אם ה-client עדיין פעיל
                if (!isReady || !client) {
                    throw new Error('WhatsApp client disconnected');
                }
                
                log('🔍', `Finding chat '${resolvedChatId}' (attempt ${retry + 1}/3)...`);
                
                // אם זה ID ישיר (status@broadcast או מספר@c.us), ננסה getChatById
                if (resolvedChatId.includes('@')) {
                    try {
                        chat = await client.getChatById(resolvedChatId);
                        if (chat) {
                            logSuccess(`Chat found by ID: ${resolvedChatId}`);
                            break;
                        }
                    } catch (idError) {
                        log('⚠️', `Could not get chat by ID ${resolvedChatId}: ${idError.message}`);
                        // נמשיך עם החיפוש לפי שם
                    }
                }
                
                // חיפוש לפי שם (לוגיקה קיימת)
                const chats = await client.getChats();
                chat = chats.find(c => c.name === wa_chat_id) || 
                       chats.find(c => c.name && c.name.includes(wa_chat_id));
                
                if (chat) {
                    logSuccess(`Chat found: ${chat.name}`);
                    break;
                } else {
                    log('⚠️', `Chat '${wa_chat_id}' not found in ${chats.length} chats`);
                }
            } catch (e) {
                getChatsError = e;
                const errorMsg = e.message || String(e);
                
                // אם זה detached Frame, ננסה שוב אחרי המתנה
                if (errorMsg.includes('detached Frame') || errorMsg.includes('Target closed')) {
                    log('⚠️', `Frame detached during getChats (attempt ${retry + 1}/3), waiting...`);
                    if (retry < 2) {
                        await new Promise(r => setTimeout(r, 3000)); // המתנה של 3 שניות
                        continue;
                    } else {
                        logError('Failed to get chats after retries - browser may have crashed', e);
                        throw new Error('BROWSER_CRASH_DURING_GET_CHATS');
                    }
                } else {
                    // שגיאה אחרת - נזרוק אותה
                    throw e;
                }
            }
        }

        if (!chat) {
            // אם זה status@broadcast או מספר@c.us ולא מצאנו, ננסה ליצור chat object ישירות
            if (resolvedChatId.includes('@')) {
                try {
                    // ניסיון ליצור chat object ישירות מה-ID
                    chat = await client.getChatById(resolvedChatId);
                    if (chat) {
                        logSuccess(`Chat created from ID: ${resolvedChatId}`);
                    } else {
                        throw new Error(`Chat not found: ${wa_chat_id} (resolved: ${resolvedChatId})${getChatsError ? ` (${getChatsError.message})` : ''}`);
                    }
                } catch (idError) {
                    throw new Error(`Chat not found: ${wa_chat_id} (resolved: ${resolvedChatId})${getChatsError ? ` (${getChatsError.message})` : ''}`);
                }
            } else {
                throw new Error(`Chat not found: ${wa_chat_id}${getChatsError ? ` (${getChatsError.message})` : ''}`);
            }
        }

        // בדיקת מצב לפני שליחה
        log('ℹ️', `File size: ${processedSizeMB.toFixed(2)}MB, Client ready: ${isReady}`);
        
        // 🟢 שליחה עם retry ודחיסה נוספת אם נדרש
        let sent = false;
        let lastError = null;
        let currentFileForUpload = currentFilePath;
        let currentFileIsTemp = isTempFile;
        
        for (let i = 0; i < 3; i++) { // 3 ניסיונות (הוגדל מ-2)
            try {
                // בדיקה נוספת לפני כל ניסיון
                if (!isReady || !client) {
                    throw new Error('WhatsApp client disconnected during upload');
                }
                
                // בדיקה אם הקובץ גדול מ-NO_COMPRESSION_LIMIT_MB - אם כן, נדחוס עוד לפני העלאה
                const currentSizeMB = getFileSizeMB(currentFileForUpload);
                if (currentSizeMB > CONFIG.NO_COMPRESSION_LIMIT_MB && i > 0) {
                    log('⚠️', `File still too large (${currentSizeMB.toFixed(2)}MB > ${CONFIG.NO_COMPRESSION_LIMIT_MB}MB) after failed upload, compressing more...`);
                    const moreCompressedResult = await processMediaIfNeeded(currentFileForUpload);
                    if (moreCompressedResult && moreCompressedResult.processedPath) {
                        // מחיקת הקובץ הקודם אם הוא זמני
                        if (currentFileIsTemp && currentFileForUpload !== file_path) {
                            try {
                                fs.unlinkSync(currentFileForUpload);
                            } catch (e) {
                                // ignore
                            }
                        }
                        currentFileForUpload = moreCompressedResult.processedPath;
                        currentFileIsTemp = moreCompressedResult.isTemp;
                        const newSizeMB = getFileSizeMB(currentFileForUpload);
                        log('✅', `More compressed file ready: ${newSizeMB.toFixed(2)}MB`);
                    }
                }
                
                await sendAsMedia(chat, currentFileForUpload, template_payload);
                sent = true;
                break;
            } catch (e) {
                lastError = e;
                const errorMsg = e.message || String(e);
                log('⚠️', `Upload attempt ${i+1}/3 failed: ${errorMsg}`);
                
                // אם זה detached Frame או Target closed, אין טעם לנסות שוב
                if (errorMsg.includes('detached Frame') || errorMsg.includes('Target closed') || errorMsg.includes('BROWSER_CRASH')) {
                    log('🛑', 'Browser crashed - skipping retry');
                    break;
                }
                
                // אם הקובץ גדול מ-NO_COMPRESSION_LIMIT_MB, נדחוס עוד לפני הניסיון הבא
                const currentSizeMB = getFileSizeMB(currentFileForUpload);
                if (currentSizeMB > CONFIG.NO_COMPRESSION_LIMIT_MB && i < 2) {
                    log('🔄', `File too large (${currentSizeMB.toFixed(2)}MB > ${CONFIG.NO_COMPRESSION_LIMIT_MB}MB), will compress more before next attempt...`);
                }
                
                await new Promise(r => setTimeout(r, 3000)); // המתנה של 3 שניות (הוגדל מ-2)
            }
        }
        
        // עדכון currentFilePath אם השתנה
        if (sent && currentFileForUpload !== currentFilePath) {
            currentFilePath = currentFileForUpload;
            isTempFile = currentFileIsTemp;
        }

        if (!sent) {
            logError('All retry attempts failed', lastError, {
                file: path.basename(file_path),
                sizeMB: processedSizeMB.toFixed(2),
                attempts: 3
            });
            throw lastError;
        }

        logSuccess('File sent successfully!');
        return { success: true, delivered_via: 'wa_media' };

    } catch (error) {
        const errorMsg = error.message || String(error);
        const errorType = errorMsg.includes('BROWSER_CRASH_DURING_GET_CHATS') ? 'BROWSER_CRASH_GET_CHATS' :
                         errorMsg.includes('BROWSER_CRASH') ? 'BROWSER_CRASH' :
                         errorMsg.includes('detached') ? 'DETACHED_FRAME' :
                         errorMsg.includes('Target closed') ? 'TARGET_CLOSED' :
                         errorMsg.includes('not ready') ? 'CLIENT_NOT_READY' : 'UNKNOWN';
        
        logError('Delivery failed', error, {
            file: path.basename(file_path),
            chat: wa_chat_id,
            errorType: errorType
        });
        
        // אם זה browser crash, נסמן את ה-client כלא מוכן
        if (errorType.includes('BROWSER_CRASH') || errorType === 'DETACHED_FRAME') {
            log('⚠️', 'Marking client as not ready due to browser crash');
            isReady = false;
        }
        
        return { success: false, error: errorMsg };
        
    } finally {
        // 🟢 ניקוי
        if (isTempFile) {
            try {
                await fs.unlink(currentFilePath);
                log('🧹', `Cleaned up temp file`);
            } catch (e) { console.error('Cleanup failed', e); }
        }
    }
}

// ============================================
// 🔌 API Endpoints
// ============================================

app.get('/status', (req, res) => {
    res.json({
        ready: isReady,
        hasQR: !!qrCodeData,
        timestamp: new Date().toISOString()
    });
});

app.get('/qr', (req, res) => {
    if (qrCodeData) {
        res.json({ qr: qrCodeData, message: 'Scan this QR code with WhatsApp' });
    } else if (isReady) {
        res.json({ qr: null, message: 'Already authenticated' });
    } else {
        res.json({ qr: null, message: 'Initializing...' });
    }
});

app.post('/reset', async (req, res) => {
    log('🔄', 'Resetting WhatsApp client...');
    try {
        if (client) {
            await client.destroy();
            client = null;
        }
        isReady = false;
        qrCodeData = null;
        
        // המתנה קצרה לפני אתחול מחדש
        setTimeout(() => {
            initializeWhatsApp();
        }, 2000);
        
        res.json({ success: true, message: 'WhatsApp client reset, reinitializing...' });
    } catch (error) {
        logError('Error resetting client', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/send/enhanced', async (req, res) => {
    // Timeout ארוך לטובת דחיסת קבצים גדולים
    req.setTimeout(CONFIG.TIMEOUT_PROCESSING_SEC * 1000); 

    try {
        const result = await deliverFile(req.body);
        res.json(result);
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// הפעלה
app.listen(PORT, () => {
    console.log('\n' + '═'.repeat(60));
    console.log('📱 PRODUCTION WhatsApp Service running on port ' + PORT);
    console.log(`🌐 Server: http://localhost:${PORT}`);
    console.log('═'.repeat(60) + '\n');
    initializeWhatsApp();
});