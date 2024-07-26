import openai
from openai import OpenAI
import os
import logging
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

# Initialize OpenAI client
client = OpenAI()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Configure logging
logging.basicConfig(level=logging.INFO)

# Function to transcribe audio using the new OpenAI API
def transcribe_audio(audio_path):
    audio_file = open(audio_path, "rb")
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text"
    )
    audio_file.close()
    print(transcription)
    return transcription

# Function to translate medical jargon to layman's terms using OpenAI
def dejargonify(text):
    prompt = f"""
    You are a helpful assistant specialized in medical explanations. Your task is to read the following medical consultation text and translate it into very simple, easy-to-understand language for the patient. Also, provide some context to help the patient understand any medical terms or concepts mentioned.
    
    Medical Consultation Text: {text}

    Simplified Explanation for Patient:
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
    )
    explanation = response.choices[0].message.content.strip()
    return explanation

@app.route('/upload', methods=['POST'])
def upload_audio():
    try:
        if 'file' not in request.files:
            logging.error('No file part in the request')
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            logging.error('No selected file')
            return jsonify({'error': 'No selected file'}), 400

        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            logging.info(f'File saved to {filepath}')

            # Transcribe the audio
            transcribed_text = transcribe_audio(filepath)
            logging.info(f'Transcribed Text: {transcribed_text}')

            return jsonify({
                'transcribed_text': transcribed_text
            })
    except Exception as e:
        logging.error(f'Error processing file: {e}')
        return jsonify({'error': 'Error processing file'}), 500

@app.route('/simplify', methods=['POST'])
def simplify_text():
    try:
        data = request.get_json()
        text = data.get('text', '')
        if not text:
            logging.error('No text provided')
            return jsonify({'error': 'No text provided'}), 400

        # Get the simplified explanation
        simplified_text = dejargonify(text)
        logging.info(f'Simplified Text: {simplified_text}')

        return jsonify({
            'simplified_text': simplified_text
        })
    except Exception as e:
        logging.error(f'Error simplifying text: {e}')
        return jsonify({'error': 'Error simplifying text'}), 500

@app.route('/')
def index():
    return '''
    <!doctype html>
    <html>
    <head>
        <title>Medical Transcription and Simplification</title>
    </head>
    <body>
        <h1>Record your audio</h1>
        <button id="startRecording">Start Recording</button>
        <button id="stopRecording" disabled>Stop Recording</button>
        <audio id="audioPlayback" controls></audio>
        <br>
        <button id="transcribe" disabled>Transcribe</button>
        <button id="simplify" disabled>Simplify</button>
        <h2>Transcribed Text</h2>
        <div id="transcribedText"></div>
        <h2>Simplified Text</h2>
        <div id="simplifiedText"></div>
        <div id="debug"></div>
        <script>
            let mediaRecorder;
            let audioChunks = [];
            let audioBlob;
            const startButton = document.getElementById('startRecording');
            const stopButton = document.getElementById('stopRecording');
            const transcribeButton = document.getElementById('transcribe');
            const simplifyButton = document.getElementById('simplify');
            const audioPlayback = document.getElementById('audioPlayback');
            const transcribedTextDiv = document.getElementById('transcribedText');
            const simplifiedTextDiv = document.getElementById('simplifiedText');
            const debugDiv = document.getElementById('debug');

            startButton.addEventListener('click', startRecording);
            stopButton.addEventListener('click', stopRecording);
            transcribeButton.addEventListener('click', transcribeAudio);
            simplifyButton.addEventListener('click', simplifyText);

            function logDebug(message) {
                console.log(message);
                const messageElement = document.createElement('p');
                messageElement.textContent = message;
                debugDiv.appendChild(messageElement);
            }

            function startRecording() {
                logDebug('Requesting microphone access...');
                navigator.mediaDevices.getUserMedia({ audio: true })
                    .then(stream => {
                        logDebug('Microphone access granted');
                        mediaRecorder = new MediaRecorder(stream);
                        mediaRecorder.start();
                        audioChunks = [];

                        mediaRecorder.addEventListener('dataavailable', event => {
                            audioChunks.push(event.data);
                        });

                        startButton.disabled = true;
                        stopButton.disabled = false;
                        logDebug('Recording started');
                    })
                    .catch(error => {
                        logDebug('Microphone access denied: ' + error.message);
                        alert('Error accessing microphone: ' + error.message);
                    });
            }

            function stopRecording() {
                if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                    mediaRecorder.stop();
                    logDebug('Recording stopped');
                    mediaRecorder.addEventListener('stop', () => {
                        audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        const audioUrl = URL.createObjectURL(audioBlob);
                        audioPlayback.src = audioUrl;

                        transcribeButton.disabled = false;
                        simplifyButton.disabled = true;

                        startButton.disabled = false;
                        stopButton.disabled = true;
                    });
                } else {
                    logDebug('MediaRecorder not active or not defined');
                }
            }

            function transcribeAudio() {
                const formData = new FormData();
                formData.append('file', audioBlob, 'recording.wav');

                fetch('/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        logDebug(`Server returned ${response.status}`);
                        throw new Error('Server returned error');
                    }
                    return response.json();
                })
                .then(data => {
                    logDebug('Server response received');
                    transcribedTextDiv.textContent = data.transcribed_text;
                    simplifyButton.disabled = false;
                })
                .catch(error => {
                    logDebug('Error uploading file: ' + error.message);
                    alert('Error uploading file: ' + error.message);
                });
            }

            function simplifyText() {
                const transcribedText = transcribedTextDiv.textContent;
                fetch('/simplify', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ text: transcribedText })
                })
                .then(response => {
                    if (!response.ok) {
                        logDebug(`Server returned ${response.status}`);
                        throw new Error('Server returned error');
                    }
                    return response.json();
                })
                .then(data => {
                    logDebug('Simplified text received');
                    simplifiedTextDiv.textContent = data.simplified_text;
                })
                .catch(error => {
                    logDebug('Error simplifying text: ' + error.message);
                    alert('Error simplifying text: ' + error.message);
                });
            }
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
